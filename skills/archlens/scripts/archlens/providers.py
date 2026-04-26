from __future__ import annotations

import base64
import io
import json
import re
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path
from typing import Any

from .config import AgentConfig
from .local_mode import (
    make_local_item_key,
    note_path_for_source,
    resolve_source_path,
    source_relative_path,
)
from .mcp import McpClient
from .models import (
    validate_bundle,
    validate_item_metadata,
    validate_review_card,
    validate_summary_card,
    validate_visual_brief,
)
from .source_to_md import available_source_extractors, convert_source_to_markdown
from .store import ArtifactStore, sha256_bytes


def _http_json(
    url: str,
    payload: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    method: str | None = None,
) -> Any:
    body = None
    request_method = method or ("POST" if payload is not None else "GET")
    final_headers = dict(headers or {})
    if payload is not None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        final_headers.setdefault("Content-Type", "application/json")
    request = urllib.request.Request(url, data=body, headers=final_headers, method=request_method)
    with urllib.request.urlopen(request) as response:
        return json.loads(response.read().decode("utf-8"))


def _http_bytes(
    url: str,
    payload: bytes | None = None,
    headers: dict[str, str] | None = None,
    method: str = "GET",
) -> bytes:
    request = urllib.request.Request(url, data=payload, headers=headers or {}, method=method)
    with urllib.request.urlopen(request) as response:
        return response.read()


def _extract_json_object(text: str) -> dict[str, Any]:
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("Model response does not contain a JSON object")
    return json.loads(text[start : end + 1])


def _split_lines(markdown_text: str) -> list[str]:
    return [line.strip() for line in markdown_text.splitlines() if line.strip()]


def _is_noise_line(line: str) -> bool:
    normalized = line.strip()
    return (
        not normalized
        or normalized.startswith("![")
        or normalized.startswith("> Converted by")
        or normalized.startswith("http")
        or bool(re.fullmatch(r"#+\s*Page\s+\d+", normalized, flags=re.IGNORECASE))
        or bool(re.fullmatch(r"Page\s+\d+", normalized, flags=re.IGNORECASE))
        or bool(re.fullmatch(r"\d+", normalized))
        or "@" in normalized
    )


def _join_wrapped_lines(lines: list[str]) -> str:
    words: list[str] = []
    for line in lines:
        if _is_noise_line(line):
            continue
        clean = line.lstrip("#•*- ").strip()
        if not clean:
            continue
        if words and words[-1].endswith("-"):
            words[-1] = words[-1][:-1] + clean
        else:
            words.append(clean)
    return " ".join(words)


def _extract_between(lines: list[str], start: str, stops: set[str]) -> str:
    collecting = False
    captured: list[str] = []
    for line in lines:
        marker = line.strip().lower()
        if marker == start.lower():
            collecting = True
            continue
        if collecting and marker in {stop.lower() for stop in stops}:
            break
        if collecting:
            captured.append(line)
    return _join_wrapped_lines(captured)


def _split_sentences(text: str) -> list[str]:
    chunks = re.split(r"(?<=[.!?])\s+", text.strip())
    return [chunk.strip() for chunk in chunks if len(chunk.strip()) > 30]


def _extract_keywords(lines: list[str]) -> list[str]:
    for index, line in enumerate(lines):
        if line.strip().lower() == "keywords" and index + 1 < len(lines):
            return [
                item.strip()
                for item in lines[index + 1].replace(";", ",").split(",")
                if item.strip()
            ][:8]
    return []


def _normalize_people(raw: dict[str, Any]) -> list[str]:
    for key in ("authors", "creators", "inventors"):
        value = raw.get(key)
        if not isinstance(value, list):
            continue
        names: list[str] = []
        for entry in value:
            if isinstance(entry, str):
                if entry.strip():
                    names.append(entry.strip())
            elif isinstance(entry, dict):
                name = str(entry.get("name", "")).strip()
                if name:
                    names.append(name)
                else:
                    first = str(entry.get("firstName", "")).strip()
                    last = str(entry.get("lastName", "")).strip()
                    merged = f"{first} {last}".strip()
                    if merged:
                        names.append(merged)
        return names
    return []


def _pick_string(raw: dict[str, Any], keys: list[str]) -> str | None:
    for key in keys:
        value = raw.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _resolve_attachment_path(raw: dict[str, Any]) -> str | None:
    direct = _pick_string(raw, ["pdfPath", "path", "filePath", "attachmentPath", "localPath"])
    if direct:
        return direct
    for value in raw.values():
        if isinstance(value, dict):
            nested = _resolve_attachment_path(value)
            if nested:
                return nested
    return None


def available_local_pdf_extractors() -> list[str]:
    return available_source_extractors()


class ReferenceManagerGateway:
    def __init__(self, config: AgentConfig) -> None:
        self.config = config
        self.client = McpClient(
            config.reference_mcp_command,
            config.reference_mcp_args,
            config.workspace_root,
        )
        self.tool_names: set[str] = set()

    def connect(self) -> None:
        self.client.connect()
        self.tool_names = {tool.get("name", "") for tool in self.client.list_tools() if isinstance(tool, dict)}

    def close(self) -> None:
        self.client.close()

    def search_items(self, query: str) -> list[dict[str, Any]]:
        payload = self._call_tool_with_fallback(
            ["zotero_search_items"],
            [{"query": query}, {"q": query}, {"search": query}],
        )
        return [self._normalize_metadata(item) for item in self._as_array(payload)]

    def get_item_metadata(self, item_key: str) -> dict[str, Any]:
        payload = self._call_tool_with_fallback(
            ["zotero_get_item_metadata"],
            [{"itemKey": item_key}, {"key": item_key}],
        )
        return self._normalize_metadata(payload)

    def get_item_children(self, item_key: str) -> list[dict[str, Any]]:
        payload = self._call_tool_with_fallback(
            ["zotero_get_item_children"],
            [{"itemKey": item_key}, {"key": item_key}],
        )
        return [self._normalize_metadata(item) for item in self._as_array(payload)]

    def get_collection_items(self, collection_key: str) -> list[dict[str, Any]]:
        payload = self._call_tool_with_fallback(
            ["zotero_get_collection_items"],
            [{"collectionKey": collection_key}, {"key": collection_key}],
        )
        return [self._normalize_metadata(item) for item in self._as_array(payload)]

    def create_child_note(self, item_key: str, title: str, content: str) -> Any:
        return self._call_tool_with_fallback(
            ["zotero_create_note"],
            [
                {"itemKey": item_key, "title": title, "content": content},
                {"itemKey": item_key, "title": title, "note": content},
                {"parentItemKey": item_key, "title": title, "content": content},
            ],
        )

    def update_tags(self, item_key: str, item_type: str, tags: list[str]) -> Any:
        return self._call_tool_with_fallback(
            ["zotero_update_item"],
            [
                {"itemKey": item_key, "updates": {"tags": tags}},
                {"itemKey": item_key, "tags": tags},
                {"key": item_key, "itemType": item_type, "tags": tags},
            ],
        )

    def create_review_report(
        self, collection_key: str | None, anchor_item_key: str, title: str, content: str
    ) -> Any:
        if not collection_key:
            return self.create_child_note(anchor_item_key, title, content)
        try:
            return self._call_tool_with_fallback(
                ["zotero_create_note"],
                [
                    {"collectionKey": collection_key, "title": title, "content": content},
                    {"collectionKey": collection_key, "title": title, "note": content},
                ],
            )
        except Exception:
            return self.create_child_note(anchor_item_key, title, content)

    def resolve_primary_pdf(self, item_key: str) -> str:
        item = self.get_item_metadata(item_key)
        if item.get("pdfPath"):
            return str(item["pdfPath"])
        for child in self.get_item_children(item_key):
            if child.get("pdfPath"):
                return str(child["pdfPath"])
        raise RuntimeError(f"No PDF path found for reference item {item_key}")

    @staticmethod
    def _as_array(value: Any) -> list[dict[str, Any]]:
        if isinstance(value, list):
            return [entry for entry in value if isinstance(entry, dict)]
        if isinstance(value, dict):
            for key in ("items", "results"):
                nested = value.get(key)
                if isinstance(nested, list):
                    return [entry for entry in nested if isinstance(entry, dict)]
        return []

    @staticmethod
    def _normalize_metadata(raw: Any) -> dict[str, Any]:
        if not isinstance(raw, dict):
            raise ValueError("Unexpected reference metadata payload")
        normalized = dict(raw)
        normalized["itemKey"] = _pick_string(raw, ["key", "itemKey", "id"]) or ""
        normalized["parentItemKey"] = _pick_string(
            raw, ["parentItem", "parentItemKey", "parentKey"]
        )
        normalized["title"] = _pick_string(raw, ["title", "name"]) or normalized["itemKey"]
        normalized["itemType"] = _pick_string(raw, ["itemType", "type"]) or "unknown"
        normalized["authorsOrInventors"] = _normalize_people(raw)
        normalized["collectionKeys"] = [
            str(entry).strip()
            for entry in raw.get("collections", [])
            if str(entry).strip()
        ] if isinstance(raw.get("collections"), list) else []
        normalized["year"] = _pick_string(raw, ["year"]) or (
            _pick_string(raw, ["date"])[:4] if _pick_string(raw, ["date"]) else None
        )
        normalized["abstractNote"] = _pick_string(raw, ["abstractNote", "abstract", "summary"])
        normalized["pdfPath"] = _resolve_attachment_path(raw)
        normalized["raw"] = raw
        return validate_item_metadata(normalized)

    def _call_tool_with_fallback(
        self, tool_names: list[str], payloads: list[dict[str, Any]]
    ) -> Any:
        last_error: Exception | None = None
        for tool_name in tool_names:
            if tool_name not in self.tool_names:
                continue
            for payload in payloads:
                try:
                    return self.client.call_tool(tool_name, payload)
                except Exception as error:  # noqa: PERF203
                    last_error = error
        raise RuntimeError(
            str(last_error or f"No matching reference MCP tool found for {', '.join(tool_names)}")
        )


class LocalFileGateway:
    def __init__(self, config: AgentConfig, store: ArtifactStore, mineru: MineruClient) -> None:
        self.config = config
        self.store = store
        self.mineru = mineru

    def prepare_item(
        self, requested_path: str, explicit_doc_type: str | None = None
    ) -> tuple[dict[str, Any], str, Path]:
        source_path = resolve_source_path(requested_path, self.config.source_docs_dir)
        doc_type = self._detect_doc_type(source_path, explicit_doc_type)
        relative = source_relative_path(source_path, self.config.source_docs_dir)
        note_path = note_path_for_source(
            source_path, self.config.source_docs_dir, self.config.reading_notes_dir
        )
        item = validate_item_metadata(
            {
                "itemKey": make_local_item_key(source_path, self.config.source_docs_dir),
                "title": self._title_from_source_path(source_path),
                "itemType": doc_type,
                "authorsOrInventors": [],
                "collectionKeys": [],
                "pdfPath": self._workspace_path(source_path) if source_path.suffix.lower() == ".pdf" else None,
                "sourcePath": self._workspace_path(source_path),
                "sourceRelativePath": relative.as_posix() if relative else None,
                "notePath": self._workspace_path(note_path),
                "storageMode": "local",
                "raw": {"requestedPath": requested_path},
            }
        )
        return item, doc_type, source_path

    def extract_and_normalize(self, item_key: str, doc_type: str, source_path: str) -> dict[str, Any]:
        path = Path(source_path).resolve()
        source_bytes = path.read_bytes()
        source_hash = sha256_bytes(source_bytes)
        bundle_path = self.store.output_path(item_key, "bundle.json")
        if bundle_path.exists():
            existing = validate_bundle(self.store.load_json(bundle_path))
            if existing["sourceHash"] == source_hash and existing["docType"] == doc_type:
                return existing

        if path.suffix.lower() == ".pdf":
            return self._extract_pdf_bundle(item_key, doc_type, path, source_hash)

        conversion = convert_source_to_markdown(path)
        return self._write_local_bundle(
            item_key, doc_type, path, source_hash, conversion.markdown, conversion.parser, conversion.image_paths
        )

    def _extract_pdf_bundle(
        self, item_key: str, doc_type: str, source_path: Path, source_hash: str
    ) -> dict[str, Any]:
        mineru_error: Exception | None = None
        if self.config.mineru_api_key:
            try:
                return self.mineru.extract_and_normalize(item_key, doc_type, str(source_path))
            except Exception as error:  # noqa: PERF203
                mineru_error = error

        try:
            conversion = self._extract_pdf_markdown_locally(item_key, source_path)
            return self._write_local_bundle(
                item_key,
                doc_type,
                source_path,
                source_hash,
                conversion.markdown,
                conversion.parser,
                conversion.image_paths,
            )
        except Exception as fallback_error:
            if mineru_error is not None:
                raise RuntimeError(
                    f"MinerU extraction failed ({mineru_error}) and local PDF fallback also failed ({fallback_error})."
                ) from fallback_error
            raise RuntimeError(str(fallback_error)) from fallback_error

    def _write_local_bundle(
        self,
        item_key: str,
        doc_type: str,
        source_path: Path,
        source_hash: str,
        markdown_text: str,
        parser: str,
        image_paths: list[Path] | None = None,
    ) -> dict[str, Any]:
        full_markdown_path = self.store.mineru_dir(item_key) / "full.md"
        self.store.save_text(full_markdown_path, markdown_text)
        bundle = validate_bundle(
            {
                "itemKey": item_key,
                "docType": doc_type,
                "sourcePath": self._workspace_path(source_path),
                "sourceHash": source_hash,
                "sourceType": source_path.suffix.lower().lstrip(".") or "text",
                "metadataPath": str(self.store.metadata_path(item_key)),
                "mineruDir": str(self.store.mineru_dir(item_key)),
                "fullMarkdownPath": str(full_markdown_path),
                "contentListPath": None,
                "extractedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "parser": parser,
                "pdfPath": self._workspace_path(source_path) if source_path.suffix.lower() == ".pdf" else None,
                "pdfHash": source_hash if source_path.suffix.lower() == ".pdf" else None,
                "imagePaths": [self._workspace_path(path) for path in image_paths or []],
            }
        )
        self.store.save_json(self.store.output_path(item_key, "bundle.json"), bundle)
        return bundle

    def _extract_pdf_markdown_locally(self, item_key: str, source_path: Path) -> Any:
        return convert_source_to_markdown(source_path, self.store.mineru_dir(item_key) / "images")

    @staticmethod
    def _title_from_source_path(source_path: Path) -> str:
        title = source_path.stem.replace("_", " ").replace("-", " ").strip()
        return title or source_path.name

    @staticmethod
    def _detect_doc_type(source_path: Path, explicit_doc_type: str | None) -> str:
        if explicit_doc_type in {"paper", "patent"}:
            return explicit_doc_type
        probe = str(source_path).lower()
        return "patent" if ("patent" in probe or "专利" in probe) else "paper"

    def _workspace_path(self, path: Path) -> str:
        try:
            return path.resolve().relative_to(self.config.workspace_root.resolve()).as_posix()
        except ValueError:
            return path.as_posix()


class MineruClient:
    def __init__(self, config: AgentConfig, store: ArtifactStore) -> None:
        self.config = config
        self.store = store

    def extract_and_normalize(self, item_key: str, doc_type: str, pdf_path: str) -> dict[str, Any]:
        if not self.config.mineru_api_key:
            raise RuntimeError("MINERU_API_KEY is required for PDF extraction")
        pdf_bytes = Path(pdf_path).read_bytes()
        pdf_hash = sha256_bytes(pdf_bytes)
        bundle_path = self.store.output_path(item_key, "bundle.json")
        if bundle_path.exists():
            existing = validate_bundle(self.store.load_json(bundle_path))
            if existing["sourceHash"] == pdf_hash and existing["docType"] == doc_type:
                return existing

        upload_target = self._get_upload_url(Path(pdf_path).name)
        _http_bytes(upload_target["putUrl"], payload=pdf_bytes, method="PUT")
        zip_bytes = self._poll_and_download(upload_target["batchId"])
        bundle = self.normalize_zip_buffer(item_key, doc_type, pdf_path, pdf_hash, zip_bytes)
        self.store.save_json(bundle_path, bundle)
        return bundle

    def normalize_zip_buffer(
        self, item_key: str, doc_type: str, pdf_path: str, pdf_hash: str, zip_bytes: bytes
    ) -> dict[str, Any]:
        mineru_dir = self.store.mineru_dir(item_key)
        with zipfile.ZipFile(io.BytesIO(zip_bytes), "r") as archive:
            markdown_name = next((name for name in archive.namelist() if name.endswith(".md")), None)
            if markdown_name is None:
                raise RuntimeError("MinerU output does not contain a Markdown file")
            markdown_text = archive.read(markdown_name).decode("utf-8")
            full_markdown_path = mineru_dir / "full.md"
            self.store.save_text(full_markdown_path, markdown_text)

            content_list_path = None
            for name in archive.namelist():
                if name.endswith("content_list.json"):
                    content_list_path = mineru_dir / "content_list.json"
                    self.store.save_text(
                        content_list_path, archive.read(name).decode("utf-8")
                    )
                elif name.endswith("model.json"):
                    self.store.save_text(mineru_dir / "model.json", archive.read(name).decode("utf-8"))
                elif name.endswith("middle.json"):
                    self.store.save_text(mineru_dir / "middle.json", archive.read(name).decode("utf-8"))

        return validate_bundle(
            {
                "itemKey": item_key,
                "docType": doc_type,
                "sourcePath": self._workspace_path(Path(pdf_path)),
                "sourceHash": pdf_hash,
                "sourceType": "pdf",
                "pdfPath": self._workspace_path(Path(pdf_path)),
                "pdfHash": pdf_hash,
                "metadataPath": str(self.store.metadata_path(item_key)),
                "mineruDir": str(mineru_dir),
                "fullMarkdownPath": str(full_markdown_path),
                "contentListPath": str(content_list_path) if content_list_path else None,
                "extractedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "parser": "mineru",
            }
        )

    def _workspace_path(self, path: Path) -> str:
        try:
            return path.resolve().relative_to(self.config.workspace_root.resolve()).as_posix()
        except ValueError:
            return path.as_posix()

    def _get_upload_url(self, file_name: str) -> dict[str, str]:
        payload = _http_json(
            f"{self.config.mineru_api_url}/api/v4/file-urls/batch",
            payload={"files": [{"name": file_name}]},
            headers={"Authorization": f"Bearer {self.config.mineru_api_key}"},
        )
        data = payload.get("data", {}) if isinstance(payload, dict) else {}
        put_url = None
        urls = data.get("urls")
        if isinstance(data.get("file_urls"), list) and data["file_urls"]:
            put_url = data["file_urls"][0]
        elif isinstance(urls, list) and urls:
            put_url = urls[0]
        elif isinstance(urls, dict):
            put_url = urls.get(file_name)
        elif isinstance(data.get("items"), list) and data["items"]:
            item = data["items"][0]
            if isinstance(item, dict):
                put_url = item.get("url")
        elif isinstance(data.get("upload_url"), str):
            put_url = data["upload_url"]
        batch_id = data.get("batch_id")
        if not isinstance(put_url, str) or not put_url or not isinstance(batch_id, str):
            raise RuntimeError("MinerU batch response did not contain upload URL or batch id")
        return {"putUrl": put_url, "batchId": batch_id}

    def _poll_and_download(self, batch_id: str) -> bytes:
        deadline = time.time() + (self.config.mineru_timeout_ms / 1000.0)
        url = f"{self.config.mineru_api_url}/api/v4/extract-results/batch/{batch_id}"
        while time.time() < deadline:
            payload = _http_json(
                url,
                headers={"Authorization": f"Bearer {self.config.mineru_api_key}"},
            )
            data = payload.get("data", {}) if isinstance(payload, dict) else {}
            results = data.get("extract_result", [])
            first = results[0] if isinstance(results, list) and results else {}
            if isinstance(first, dict) and first.get("state") == "done" and first.get("full_zip_url"):
                return _http_bytes(str(first["full_zip_url"]))
            if isinstance(first, dict) and first.get("state") == "error":
                raise RuntimeError("MinerU extraction failed on the server side")
            time.sleep(self.config.mineru_poll_interval_ms / 1000.0)
        raise RuntimeError("MinerU extraction timed out")


class LlmClient:
    def __init__(self, config: AgentConfig) -> None:
        self.config = config

    def generate_summary_card(
        self, doc_type: str, metadata: dict[str, Any], markdown_text: str, prompt_pack: dict[str, Any]
    ) -> dict[str, Any]:
        if self.config.llm_provider == "mock":
            return self._summarize_locally(doc_type, metadata, markdown_text)

        schema_hint = {
            "docType": "paper | patent",
            "title": "string",
            "authorsOrInventors": ["string"],
            "year": "string?",
            "source": "string?",
            "coreProblem": "string",
            "coreIdea": "string",
            "methodOrSolution": ["string"],
            "keyEvidence": ["string"],
            "limitations": ["string"],
            "keywords": ["string"],
            "citationHints": ["string"],
            "dataset": ["string"],
            "metrics": ["string"],
            "experiments": ["string"],
            "novelty": ["string"],
            "futureWork": ["string"],
            "patentNumber": "string?",
            "assignee": "string?",
            "filingDate": "string?",
            "publicationDate": "string?",
            "independentClaims": ["string"],
            "dependentClaims": ["string"],
            "protectionScope": ["string"],
            "implementationExamples": ["string"],
            "noveltyVsPriorArt": ["string"],
        }
        prompt = "\n\n".join(
            [
                prompt_pack["systemPrompt"],
                prompt_pack["taskPrompt"],
                f"语言：{prompt_pack['language']}",
                "输出要求：只返回一个 JSON 对象，不要使用 Markdown 代码块。字段必须符合 SummaryCard。",
                f"Schema hint:\n{json.dumps(schema_hint, ensure_ascii=False, indent=2)}",
                f"Metadata:\n{json.dumps(metadata, ensure_ascii=False, indent=2)}",
                f"Document markdown:\n{markdown_text}",
            ]
        )
        response_text = self._complete_text(prompt)
        return validate_summary_card(_extract_json_object(response_text))

    def generate_review_card(self, item_key: str, summary_card: dict[str, Any]) -> dict[str, Any]:
        return validate_review_card(
            {
                "topic": (summary_card.get("keywords") or [summary_card["title"]])[0],
                "problem": summary_card["coreProblem"],
                "method": summary_card.get("methodOrSolution", []),
                "data": summary_card.get("dataset", []),
                "result": summary_card.get("keyEvidence", []),
                "strength": summary_card.get("novelty", []) or summary_card.get("keyEvidence", []),
                "weakness": summary_card.get("limitations", []),
                "openQuestions": summary_card.get("futureWork", []) or ["需要补充更具体的开放问题"],
                "evidenceSnippets": summary_card.get("keyEvidence", []),
                "sourceItemKey": item_key,
                "docType": summary_card["docType"],
                "title": summary_card["title"],
            }
        )

    def generate_visual_brief(self, summary_card: dict[str, Any], prompt_pack: dict[str, Any]) -> dict[str, Any]:
        if self.config.llm_provider == "mock":
            return self._visual_brief_locally(summary_card)
        prompt = "\n\n".join(
            [
                prompt_pack["systemPrompt"],
                prompt_pack["taskPrompt"],
                f"语言：{prompt_pack['language']}",
                "输出要求：只返回一个 JSON 对象，不要使用 Markdown 代码块。字段必须符合 VisualBrief。",
                f"SummaryCard:\n{json.dumps(summary_card, ensure_ascii=False, indent=2)}",
            ]
        )
        response_text = self._complete_text(prompt)
        return validate_visual_brief(_extract_json_object(response_text))

    def generate_literature_review(self, review_cards: list[dict[str, Any]], prompt_pack: dict[str, Any]) -> str:
        if self.config.llm_provider == "mock":
            sections = [
                "# 文献综述",
                "## 主题概览",
                "\n".join(f"- {card['title']}: {card['problem']}" for card in review_cards),
                "## 论文矩阵",
                "\n".join(
                    f"- {card['title']} | 方法：{' / '.join(card['method'])} | 结果：{' / '.join(card['result'])}"
                    for card in review_cards
                ),
                "## 关键发现",
                "\n".join(f"- {item}" for card in review_cards for item in card["result"]),
                "## 未来方向",
                "\n".join(f"- {item}" for card in review_cards for item in card["openQuestions"]),
            ]
            return "\n\n".join(section for section in sections if section.strip())
        prompt = "\n\n".join(
            [
                prompt_pack["systemPrompt"],
                prompt_pack["taskPrompt"],
                f"语言：{prompt_pack['language']}",
                "请直接返回 Markdown。",
                f"Review cards:\n{json.dumps(review_cards, ensure_ascii=False, indent=2)}",
            ]
        )
        return self._complete_text(prompt)

    def _summarize_locally(
        self, doc_type: str, metadata: dict[str, Any], markdown_text: str
    ) -> dict[str, Any]:
        lines = _split_lines(markdown_text)
        abstract = _extract_between(lines, "Abstract", {"CCS Concepts", "Keywords", "ACM Reference Format"})
        sentences = _split_sentences(abstract) or _split_sentences(_join_wrapped_lines(lines[:120]))
        keywords = _extract_keywords(lines)
        bullet_candidates = [
            line.lstrip("-*#• ").strip()
            for line in lines
            if not _is_noise_line(line)
            and "→" not in line
            and (
                line.startswith("-")
                or line.startswith("*")
                or line.startswith("•")
            )
        ][:10]
        bullet_candidates = [line for line in bullet_candidates if line]
        evidence = [
            sentence
            for sentence in sentences
            if any(token in sentence.lower() for token in ["evaluation", "shows", "reduces", "improves", "achieves", "%", "kb"])
        ]
        first_paragraph = " ".join(sentences[:2]) or next(
            (line for line in lines if len(line) > 80 and not _is_noise_line(line)),
            metadata["title"],
        )
        core_idea = " ".join(sentences[2:5]) or (bullet_candidates[0] if bullet_candidates else metadata["title"])
        return validate_summary_card(
            {
                "docType": doc_type,
                "title": metadata["title"],
                "authorsOrInventors": metadata.get("authorsOrInventors", []),
                "year": metadata.get("year"),
                "source": metadata.get("sourceRelativePath")
                or metadata.get("sourcePath")
                or metadata["itemKey"],
                "coreProblem": first_paragraph or f"{metadata['title']} 的核心问题待进一步抽取",
                "coreIdea": core_idea,
                "methodOrSolution": bullet_candidates[:3] or sentences[2:5],
                "keyEvidence": evidence[:4] or sentences[5:8],
                "limitations": ["未启用远程模型时，当前结果来自本地启发式抽取"],
                "keywords": keywords or bullet_candidates[:5] or sentences[:3],
                "citationHints": [metadata["title"], *metadata.get("authorsOrInventors", [])],
                "dataset": [sentence for sentence in sentences if "suite" in sentence.lower() or "benchmark" in sentence.lower()][:3] if doc_type == "paper" else [],
                "metrics": [sentence for sentence in sentences if "mpki" in sentence.lower() or "%" in sentence or "kb" in sentence.lower()][:3] if doc_type == "paper" else [],
                "experiments": evidence[:3] if doc_type == "paper" else [],
                "novelty": (bullet_candidates[:3] or sentences[2:5]) if doc_type == "paper" else [],
                "futureWork": ["需要人工复核未来工作方向"] if doc_type == "paper" else [],
                "independentClaims": bullet_candidates[:3] if doc_type == "patent" else [],
                "dependentClaims": bullet_candidates[3:6] if doc_type == "patent" else [],
                "protectionScope": bullet_candidates[:3] if doc_type == "patent" else [],
                "implementationExamples": bullet_candidates[6:8] if doc_type == "patent" else [],
                "noveltyVsPriorArt": bullet_candidates[:3] if doc_type == "patent" else [],
            }
        )

    @staticmethod
    def _visual_brief_locally(summary_card: dict[str, Any]) -> dict[str, Any]:
        return validate_visual_brief(
            {
                "title": summary_card["title"],
                "oneSentenceClaim": summary_card["coreIdea"],
                "visualMetaphor": "工程结构图与权利要求边界叠加"
                if summary_card["docType"] == "patent"
                else "研究问题到解决方案的流程海报",
                "mainPipeline": summary_card.get("methodOrSolution", [])
                or [summary_card["coreProblem"], summary_card["coreIdea"]],
                "keyModules": summary_card.get("methodOrSolution", []),
                "keyResults": summary_card.get("keyEvidence", []),
                "mustIncludeTerms": summary_card.get("keywords", []),
                "avoidTerms": ["未经验证的夸张表达", "与原文不一致的术语"],
                "preferredPalette": ["#0f172a", "#1d4ed8", "#f59e0b"],
                "layoutStyle": "从左到右的科研信息图海报",
            }
        )

    def _complete_text(self, prompt: str) -> str:
        if self.config.llm_provider == "gemini":
            if not self.config.gemini_api_key:
                raise RuntimeError("GEMINI_API_KEY is not configured")
            payload = _http_json(
                f"{self.config.gemini_api_url}/v1beta/models/{self.config.gemini_model}:generateContent?key={self.config.gemini_api_key}",
                payload={
                    "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                },
            )
            parts = (
                payload.get("candidates", [{}])[0]
                .get("content", {})
                .get("parts", [])
                if isinstance(payload, dict)
                else []
            )
            return "\n".join(
                part.get("text", "") for part in parts if isinstance(part, dict)
            ).strip()

        if self.config.llm_provider == "openai-compat":
            if not self.config.openai_compat_api_url or not self.config.openai_compat_api_key:
                raise RuntimeError(
                    "OPENAI_COMPAT_API_URL and OPENAI_COMPAT_API_KEY are required"
                )
            endpoint = (
                self.config.openai_compat_api_url
                if self.config.openai_compat_api_url.endswith("/chat/completions")
                else f"{self.config.openai_compat_api_url}/v1/chat/completions"
            )
            payload = _http_json(
                endpoint,
                payload={
                    "model": self.config.openai_compat_model,
                    "temperature": 0.2,
                    "messages": [{"role": "user", "content": prompt}],
                },
                headers={"Authorization": f"Bearer {self.config.openai_compat_api_key}"},
            )
            choices = payload.get("choices", []) if isinstance(payload, dict) else []
            first = choices[0] if choices else {}
            message = first.get("message", {}) if isinstance(first, dict) else {}
            return str(message.get("content", "")).strip()

        raise RuntimeError(f"Unsupported LLM provider: {self.config.llm_provider}")


class ImageProvider:
    def __init__(self, config: AgentConfig) -> None:
        self.config = config

    def generate(self, visual_brief: dict[str, Any]) -> dict[str, Any]:
        if self.config.image_provider == "local-svg":
            svg = self._build_local_svg(visual_brief).encode("utf-8")
            return {"mimeType": "image/svg+xml", "extension": "svg", "content": svg}

        prompt = "\n".join(
            [
                visual_brief["title"],
                visual_brief["oneSentenceClaim"],
                f"Visual metaphor: {visual_brief['visualMetaphor']}",
                f"Pipeline: {' -> '.join(visual_brief.get('mainPipeline', []))}",
                f"Modules: {', '.join(visual_brief.get('keyModules', []))}",
                f"Results: {', '.join(visual_brief.get('keyResults', []))}",
                f"Must include: {', '.join(visual_brief.get('mustIncludeTerms', []))}",
                f"Avoid: {', '.join(visual_brief.get('avoidTerms', []))}",
                f"Layout: {visual_brief['layoutStyle']}",
            ]
        )

        if self.config.image_provider == "gemini":
            if not self.config.gemini_api_key:
                raise RuntimeError("GEMINI_API_KEY is not configured")
            payload = _http_json(
                f"{self.config.gemini_api_url}/v1beta/models/{self.config.gemini_image_model}:generateContent?key={self.config.gemini_api_key}",
                payload={
                    "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                    "generationConfig": {"responseModalities": ["TEXT", "IMAGE"]},
                },
            )
            parts = (
                payload.get("candidates", [{}])[0]
                .get("content", {})
                .get("parts", [])
                if isinstance(payload, dict)
                else []
            )
            for part in parts:
                if isinstance(part, dict) and isinstance(part.get("inlineData"), dict):
                    inline_data = part["inlineData"]
                    mime_type = str(inline_data.get("mimeType", "image/png"))
                    data = base64.b64decode(str(inline_data.get("data", "")))
                    extension = "svg" if mime_type.endswith("svg+xml") else mime_type.split("/")[-1]
                    return {"mimeType": mime_type, "extension": extension, "content": data}
            raise RuntimeError("Gemini image response did not include inline image data")

        if self.config.image_provider == "openai-compat":
            if not self.config.openai_compat_api_url or not self.config.openai_compat_api_key:
                raise RuntimeError(
                    "OPENAI_COMPAT_API_URL and OPENAI_COMPAT_API_KEY are required"
                )
            endpoint = (
                self.config.openai_compat_api_url
                if self.config.openai_compat_api_url.endswith("/images/generations")
                else f"{self.config.openai_compat_api_url}/v1/images/generations"
            )
            payload = _http_json(
                endpoint,
                payload={
                    "model": self.config.openai_compat_image_model,
                    "prompt": prompt,
                    "size": "1536x1024",
                },
                headers={"Authorization": f"Bearer {self.config.openai_compat_api_key}"},
            )
            data = payload.get("data", []) if isinstance(payload, dict) else []
            first = data[0] if data else {}
            if isinstance(first, dict) and isinstance(first.get("b64_json"), str):
                return {
                    "mimeType": "image/png",
                    "extension": "png",
                    "content": base64.b64decode(first["b64_json"]),
                }
            raise RuntimeError("OpenAI-compatible image response did not include b64_json")

        raise RuntimeError(f"Unsupported image provider: {self.config.image_provider}")

    def _build_local_svg(self, visual_brief: dict[str, Any]) -> str:
        colors = visual_brief.get("preferredPalette") or ["#0f172a", "#2563eb", "#f59e0b"]
        lines = [
            visual_brief["oneSentenceClaim"],
            *[f"{index + 1}. {entry}" for index, entry in enumerate(visual_brief.get("mainPipeline", [])[:4])],
            *[f"Result: {entry}" for entry in visual_brief.get("keyResults", [])[:3]],
        ]
        width = self.config.image_canvas_width
        height = self.config.image_canvas_height
        return f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="{colors[0]}"/>
      <stop offset="100%" stop-color="{colors[1] if len(colors) > 1 else colors[0]}"/>
    </linearGradient>
  </defs>
  <rect width="100%" height="100%" fill="url(#bg)"/>
  <rect x="60" y="60" width="{width - 120}" height="{height - 120}" rx="28" fill="rgba(255,255,255,0.08)" stroke="rgba(255,255,255,0.18)"/>
  <text x="100" y="150" fill="#ffffff" font-size="48" font-family="Georgia, serif">{self._escape_xml(visual_brief['title'])}</text>
  <text x="100" y="220" fill="#e2e8f0" font-size="28" font-family="Georgia, serif">{self._escape_xml(visual_brief['visualMetaphor'])}</text>
  {''.join(f'<text x="110" y="{320 + index * 68}" fill="#f8fafc" font-size="26" font-family="Arial, sans-serif">{self._escape_xml(line)}</text>' for index, line in enumerate(lines[:8]))}
  <text x="110" y="{height - 90}" fill="#fbbf24" font-size="22" font-family="Arial, sans-serif">Generated by ArchLens</text>
</svg>"""

    @staticmethod
    def _escape_xml(value: str) -> str:
        return (
            value.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&apos;")
        )
