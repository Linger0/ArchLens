from __future__ import annotations

import base64
from pathlib import Path
from typing import Any

from .config import AgentConfig
from .models import validate_review_card, validate_summary_card
from .prompt_packs import PromptPackManager
from .providers import ImageProvider, LlmClient, LocalFileGateway, MineruClient, ReferenceManagerGateway
from .renderers import (
    build_mindmap_markdown,
    render_image_summary_note,
    render_local_summary_note,
    render_mindmap_html,
    render_mindmap_note,
    render_mindmap_svg,
    render_summary_markdown,
)
from .store import ArtifactStore, sync_tree


def create_job_file(
    store: ArtifactStore,
    key: str,
    job_name: str,
    payload: dict[str, Any],
) -> Path:
    path = store.job_path(key, job_name)
    store.save_json(path, payload)
    return path


def detect_doc_type(item: dict[str, Any]) -> str:
    normalized = f"{item.get('itemType', '')} {item.get('title', '')}".lower()
    return "patent" if "patent" in normalized else "paper"


def inspect_artifacts(item_key: str, store: ArtifactStore) -> dict[str, str]:
    return {
        "metadata": str(store.metadata_path(item_key)),
        "mineruDir": str(store.mineru_dir(item_key)),
        "outputsDir": str(store.outputs_dir(item_key)),
        "jobsDir": str(store.jobs_dir(item_key)),
        "bundle": str(store.output_path(item_key, "bundle.json")),
        "summary": str(store.output_path(item_key, "summary.md")),
        "summaryCard": str(store.output_path(item_key, "summaryCard.json")),
        "reviewCard": str(store.output_path(item_key, "reviewCard.json")),
        "visualBrief": str(store.output_path(item_key, "visualBrief.json")),
        "mindmap": str(store.output_path(item_key, "mindmap.md")),
        "posterBase": str(store.outputs_dir(item_key) / "poster"),
    }


def sync_skill(config: AgentConfig) -> list[str]:
    target = config.codex_home / "skills" / "archlens"
    sync_tree(config.skill_root, target)
    return [str(target)]


def _execute_read_pipeline(
    item: dict[str, Any],
    doc_type: str,
    store: ArtifactStore,
    llm: LlmClient,
    prompts: PromptPackManager,
    bundle: dict[str, Any],
    write_back_policy: str,
) -> dict[str, Any]:
    item_metadata = dict(item)
    store.save_json(store.metadata_path(item["itemKey"]), item_metadata)
    markdown_text = store.load_text(Path(bundle["fullMarkdownPath"]))
    prompt_pack = prompts.resolve(doc_type)

    create_job_file(
        store,
        item["itemKey"],
        f"{doc_type}-deepread",
        {
            "itemKey": item["itemKey"],
            "docType": doc_type,
            "promptPackId": prompt_pack["id"],
            "artifactPaths": [
                str(store.metadata_path(item["itemKey"])),
                bundle["fullMarkdownPath"],
                str(store.output_path(item["itemKey"], "summaryCard.json")),
                str(store.output_path(item["itemKey"], "reviewCard.json")),
            ],
            "expectedOutputs": ["summary.md", "summaryCard.json", "reviewCard.json"],
            "writeBackPolicy": write_back_policy,
        },
    )

    summary_card = validate_summary_card(
        llm.generate_summary_card(doc_type, item_metadata, markdown_text, prompt_pack)
    )
    review_card = validate_review_card(
        llm.generate_review_card(item["itemKey"], summary_card)
    )
    summary_markdown = render_summary_markdown(summary_card)

    store.save_json(store.output_path(item["itemKey"], "summaryCard.json"), summary_card)
    store.save_json(store.output_path(item["itemKey"], "reviewCard.json"), review_card)
    summary_path = store.output_path(item["itemKey"], "summary.md")
    store.save_text(summary_path, summary_markdown)

    return {
        "item": item_metadata,
        "summaryCard": summary_card,
        "reviewCard": review_card,
        "summaryPath": str(summary_path),
        "summaryMarkdown": summary_markdown,
    }


def _execute_reference_read_workflow(
    item: dict[str, Any],
    doc_type: str,
    config: AgentConfig,
    gateway: ReferenceManagerGateway,
    store: ArtifactStore,
    mineru: MineruClient,
    llm: LlmClient,
    prompts: PromptPackManager,
) -> dict[str, Any]:
    pdf_path = gateway.resolve_primary_pdf(item["itemKey"])
    item_metadata = dict(item)
    item_metadata["pdfPath"] = pdf_path
    bundle = mineru.extract_and_normalize(item["itemKey"], doc_type, pdf_path)
    result = _execute_read_pipeline(
        item_metadata,
        doc_type,
        store,
        llm,
        prompts,
        bundle,
        "create child note and add AI-Read tag",
    )

    gateway.create_child_note(
        item["itemKey"],
        f"{config.note_title_prefix} {'论文精读' if doc_type == 'paper' else '专利精读'} - {item['title']}",
        result["summaryMarkdown"],
    )
    gateway.update_tags(item["itemKey"], item["itemType"], ["AI-Read"])
    result.pop("summaryMarkdown", None)
    return result


def read_item_by_key(
    item_key: str,
    config: AgentConfig,
    gateway: ReferenceManagerGateway,
    store: ArtifactStore,
    mineru: MineruClient,
    llm: LlmClient,
    prompts: PromptPackManager,
) -> dict[str, Any]:
    item = gateway.get_item_metadata(item_key)
    return _execute_reference_read_workflow(
        item, detect_doc_type(item), config, gateway, store, mineru, llm, prompts
    )


def read_by_search(
    query: str,
    config: AgentConfig,
    gateway: ReferenceManagerGateway,
    store: ArtifactStore,
    mineru: MineruClient,
    llm: LlmClient,
    prompts: PromptPackManager,
) -> dict[str, Any]:
    items = gateway.search_items(query)
    if not items:
        raise RuntimeError(f"No reference items matched query: {query}")
    if len(items) > 1:
        choices = "\n".join(f"- {item['itemKey']}: {item['title']}" for item in items[:10])
        raise RuntimeError(f"Search query matched multiple items. Please use item key.\n{choices}")
    return _execute_reference_read_workflow(
        items[0], detect_doc_type(items[0]), config, gateway, store, mineru, llm, prompts
    )


def patent_read_by_key(
    item_key: str,
    config: AgentConfig,
    gateway: ReferenceManagerGateway,
    store: ArtifactStore,
    mineru: MineruClient,
    llm: LlmClient,
    prompts: PromptPackManager,
) -> dict[str, Any]:
    item = gateway.get_item_metadata(item_key)
    return _execute_reference_read_workflow(
        item, "patent", config, gateway, store, mineru, llm, prompts
    )


def read_local_file(
    requested_path: str,
    explicit_doc_type: str | None,
    config: AgentConfig,
    store: ArtifactStore,
    mineru: MineruClient,
    llm: LlmClient,
    prompts: PromptPackManager,
) -> dict[str, Any]:
    local_gateway = LocalFileGateway(config, store, mineru)
    item, doc_type, source_path = local_gateway.prepare_item(requested_path, explicit_doc_type)
    bundle = local_gateway.extract_and_normalize(item["itemKey"], doc_type, str(source_path))
    result = _execute_read_pipeline(
        item,
        doc_type,
        store,
        llm,
        prompts,
        bundle,
        "write local markdown note into reading-notes",
    )

    source_label = item.get("sourceRelativePath") or item.get("sourcePath") or item["itemKey"]
    note_markdown = render_local_summary_note(result["summaryMarkdown"], source_label, item["itemKey"])
    note_path = Path(str(item["notePath"]))
    write_note_path = note_path if note_path.is_absolute() else config.workspace_root / note_path
    store.save_text(write_note_path, note_markdown)
    metadata = dict(item)
    metadata["notePath"] = note_path.as_posix()
    metadata["summaryPath"] = result["summaryPath"]
    store.save_json(store.metadata_path(item["itemKey"]), metadata)

    result["notePath"] = note_path.as_posix()
    result["mode"] = "local"
    result.pop("summaryMarkdown", None)
    return result


def generate_image_summary(
    item_key: str,
    config: AgentConfig,
    gateway: ReferenceManagerGateway,
    store: ArtifactStore,
    prompts: PromptPackManager,
    llm: LlmClient,
    image_provider: ImageProvider,
) -> dict[str, Any]:
    summary_card = validate_summary_card(store.load_json(store.output_path(item_key, "summaryCard.json")))
    item = gateway.get_item_metadata(item_key)
    prompt_pack = prompts.resolve("visual")
    create_job_file(
        store,
        item_key,
        "image-summary",
        {
            "itemKey": item_key,
            "docType": summary_card["docType"],
            "promptPackId": prompt_pack["id"],
            "artifactPaths": [
                str(store.output_path(item_key, "summaryCard.json")),
                str(store.output_path(item_key, "visualBrief.json")),
            ],
            "expectedOutputs": ["visualBrief.json", "poster.*"],
            "writeBackPolicy": "create child note with embedded image data URI",
        },
    )

    visual_brief = llm.generate_visual_brief(summary_card, prompt_pack)
    store.save_json(store.output_path(item_key, "visualBrief.json"), visual_brief)

    image_artifact = image_provider.generate(visual_brief)
    image_path = store.output_path(item_key, f"poster.{image_artifact['extension']}")
    store.save_binary(image_path, image_artifact["content"])

    data_uri = f"data:{image_artifact['mimeType']};base64,{base64.b64encode(image_artifact['content']).decode('ascii')}"
    note = render_image_summary_note(
        f"{config.note_title_prefix} 一图流总结 - {item['title']}",
        visual_brief,
        data_uri,
        image_path,
    )
    gateway.create_child_note(item_key, f"{config.note_title_prefix} 一图流总结 - {item['title']}", note)

    return {
        "visualBriefPath": str(store.output_path(item_key, "visualBrief.json")),
        "imagePath": str(image_path),
    }


def generate_mindmap(
    item_key: str,
    config: AgentConfig,
    gateway: ReferenceManagerGateway,
    store: ArtifactStore,
) -> dict[str, Any]:
    summary_card = validate_summary_card(store.load_json(store.output_path(item_key, "summaryCard.json")))
    item = gateway.get_item_metadata(item_key)
    create_job_file(
        store,
        item_key,
        "mindmap",
        {
            "itemKey": item_key,
            "docType": summary_card["docType"],
            "promptPackId": "derived-from-summary-card",
            "artifactPaths": [str(store.output_path(item_key, "summaryCard.json"))],
            "expectedOutputs": ["mindmap.md", "mindmap.html", "mindmap.svg"],
            "writeBackPolicy": "create child note with markmap markdown and artifact paths",
        },
    )
    mindmap_markdown = build_mindmap_markdown(summary_card)
    mindmap_path = store.output_path(item_key, "mindmap.md")
    html_path = store.output_path(item_key, "mindmap.html")
    svg_path = store.output_path(item_key, "mindmap.svg")
    store.save_text(mindmap_path, mindmap_markdown)
    store.save_text(html_path, render_mindmap_html(mindmap_markdown))
    store.save_text(svg_path, render_mindmap_svg(mindmap_markdown))

    note = render_mindmap_note(
        f"{config.note_title_prefix} 思维导图 - {item['title']}",
        mindmap_markdown,
        html_path,
        svg_path,
    )
    gateway.create_child_note(item_key, f"{config.note_title_prefix} 思维导图 - {item['title']}", note)
    return {
        "mindmapPath": str(mindmap_path),
        "htmlPath": str(html_path),
        "svgPath": str(svg_path),
    }
