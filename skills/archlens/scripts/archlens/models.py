from __future__ import annotations

from copy import deepcopy
from typing import Any


def _require_string(data: dict[str, Any], key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Expected non-empty string for {key}")
    return value.strip()


def _optional_string(data: dict[str, Any], key: str) -> str | None:
    value = data.get(key)
    if value is None:
        return None
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _string_list(data: dict[str, Any], key: str) -> list[str]:
    value = data.get(key, [])
    if not isinstance(value, list):
        return []
    return [str(entry).strip() for entry in value if str(entry).strip()]


def validate_item_metadata(raw: dict[str, Any]) -> dict[str, Any]:
    metadata = deepcopy(raw)
    metadata.setdefault("itemKey", raw.get("key") or raw.get("id"))
    metadata.setdefault("parentItemKey", raw.get("parentItemKey") or raw.get("parentKey"))
    metadata.setdefault("title", raw.get("title") or raw.get("name") or metadata["itemKey"])
    metadata.setdefault("itemType", raw.get("itemType") or raw.get("type") or "unknown")
    metadata.setdefault("authorsOrInventors", [])
    metadata.setdefault("collectionKeys", [])
    metadata.setdefault("raw", raw)
    _require_string(metadata, "itemKey")
    _require_string(metadata, "title")
    _require_string(metadata, "itemType")
    metadata["authorsOrInventors"] = _string_list(metadata, "authorsOrInventors")
    metadata["collectionKeys"] = _string_list(metadata, "collectionKeys")
    metadata["year"] = _optional_string(metadata, "year")
    metadata["abstractNote"] = _optional_string(metadata, "abstractNote")
    metadata["pdfPath"] = _optional_string(metadata, "pdfPath")
    metadata["sourcePath"] = _optional_string(metadata, "sourcePath")
    metadata["sourceRelativePath"] = _optional_string(metadata, "sourceRelativePath")
    metadata["notePath"] = _optional_string(metadata, "notePath")
    metadata["storageMode"] = _optional_string(metadata, "storageMode")
    return metadata


def validate_prompt_pack(raw: dict[str, Any]) -> dict[str, Any]:
    data = deepcopy(raw)
    target = _require_string(data, "target")
    if target not in {"paper", "patent", "review", "visual"}:
        raise ValueError(f"Unsupported prompt pack target: {target}")
    data["id"] = _require_string(data, "id")
    data["name"] = _require_string(data, "name")
    data["language"] = _optional_string(data, "language") or "中文"
    data["systemPrompt"] = _optional_string(data, "systemPrompt") or "You are a helpful academic assistant."
    data["taskPrompt"] = _require_string(data, "taskPrompt")
    data["outputSchema"] = _require_string(data, "outputSchema")
    data["userOverlay"] = _optional_string(data, "userOverlay")
    return data


def validate_summary_card(raw: dict[str, Any]) -> dict[str, Any]:
    data = deepcopy(raw)
    doc_type = _require_string(data, "docType")
    if doc_type not in {"paper", "patent"}:
        raise ValueError(f"Unsupported docType: {doc_type}")
    data["title"] = _require_string(data, "title")
    data["coreProblem"] = _require_string(data, "coreProblem")
    data["coreIdea"] = _require_string(data, "coreIdea")
    for key in [
        "authorsOrInventors",
        "methodOrSolution",
        "keyEvidence",
        "limitations",
        "keywords",
        "citationHints",
        "dataset",
        "metrics",
        "experiments",
        "novelty",
        "futureWork",
        "independentClaims",
        "dependentClaims",
        "protectionScope",
        "implementationExamples",
        "noveltyVsPriorArt",
    ]:
        data[key] = _string_list(data, key)
    for key in [
        "year",
        "source",
        "patentNumber",
        "assignee",
        "filingDate",
        "publicationDate",
    ]:
        data[key] = _optional_string(data, key)
    return data


def validate_review_card(raw: dict[str, Any]) -> dict[str, Any]:
    data = deepcopy(raw)
    data["topic"] = _require_string(data, "topic")
    data["problem"] = _require_string(data, "problem")
    data["title"] = _require_string(data, "title")
    data["sourceItemKey"] = _require_string(
        {**data, "sourceItemKey": data.get("sourceItemKey") or data.get("zoteroItemKey")},
        "sourceItemKey",
    )
    data.pop("zoteroItemKey", None)
    doc_type = _require_string(data, "docType")
    if doc_type not in {"paper", "patent"}:
        raise ValueError(f"Unsupported docType: {doc_type}")
    for key in [
        "method",
        "data",
        "result",
        "strength",
        "weakness",
        "openQuestions",
        "evidenceSnippets",
    ]:
        data[key] = _string_list(data, key)
    return data


def validate_visual_brief(raw: dict[str, Any]) -> dict[str, Any]:
    data = deepcopy(raw)
    for key in ["title", "oneSentenceClaim", "visualMetaphor", "layoutStyle"]:
        data[key] = _require_string(data, key)
    for key in [
        "mainPipeline",
        "keyModules",
        "keyResults",
        "mustIncludeTerms",
        "avoidTerms",
        "preferredPalette",
    ]:
        data[key] = _string_list(data, key)
    return data


def validate_bundle(raw: dict[str, Any]) -> dict[str, Any]:
    data = deepcopy(raw)
    data["itemKey"] = _require_string(data, "itemKey")
    doc_type = _require_string(data, "docType")
    if doc_type not in {"paper", "patent"}:
        raise ValueError(f"Unsupported docType: {doc_type}")
    data["sourcePath"] = _optional_string(data, "sourcePath") or _optional_string(data, "pdfPath")
    data["sourceHash"] = _optional_string(data, "sourceHash") or _optional_string(data, "pdfHash")
    data["sourceType"] = _optional_string(data, "sourceType") or "pdf"
    data["parser"] = _optional_string(data, "parser") or "mineru"
    for key in ["sourcePath", "sourceHash", "metadataPath", "mineruDir", "fullMarkdownPath", "extractedAt"]:
        data[key] = _require_string(data, key)
    data["pdfPath"] = _optional_string(data, "pdfPath")
    data["pdfHash"] = _optional_string(data, "pdfHash")
    data["contentListPath"] = _optional_string(data, "contentListPath")
    return data
