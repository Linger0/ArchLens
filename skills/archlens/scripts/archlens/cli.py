from __future__ import annotations

import argparse
import json
import os
import shutil
from contextlib import contextmanager
from typing import Iterator

from .config import AgentConfig, load_config
from .prompt_packs import PromptPackManager
from .providers import (
    ImageProvider,
    LlmClient,
    MineruClient,
    ReferenceManagerGateway,
    available_local_pdf_extractors,
)
from .store import ArtifactStore
from .workflows import (
    generate_image_summary,
    generate_mindmap,
    inspect_artifacts,
    patent_read_by_key,
    read_local_file,
    read_by_search,
    read_item_by_key,
    sync_skill,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="agent", description="ArchLens Python skill CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("doctor")

    read_parser = subparsers.add_parser("read")
    read_sub = read_parser.add_subparsers(dest="mode", required=True)
    read_item = read_sub.add_parser("item")
    read_item.add_argument("item_key")
    read_search = read_sub.add_parser("search")
    read_search.add_argument("query")
    read_local = read_sub.add_parser("local")
    read_local.add_argument("path")
    read_local.add_argument("--doc-type", choices=["paper", "patent"], default=None)

    patent_parser = subparsers.add_parser("patent-read")
    patent_sub = patent_parser.add_subparsers(dest="mode", required=True)
    patent_item = patent_sub.add_parser("item")
    patent_item.add_argument("item_key")

    image_parser = subparsers.add_parser("image-summary")
    image_sub = image_parser.add_subparsers(dest="mode", required=True)
    image_item = image_sub.add_parser("item")
    image_item.add_argument("item_key")

    mindmap_parser = subparsers.add_parser("mindmap")
    mindmap_sub = mindmap_parser.add_subparsers(dest="mode", required=True)
    mindmap_item = mindmap_sub.add_parser("item")
    mindmap_item.add_argument("item_key")

    prompts_parser = subparsers.add_parser("prompts")
    prompts_sub = prompts_parser.add_subparsers(dest="mode", required=True)
    prompts_sub.add_parser("list")
    prompts_show = prompts_sub.add_parser("show")
    prompts_show.add_argument("prompt_pack_id")
    prompts_set_default = prompts_sub.add_parser("set-default")
    prompts_set_default.add_argument("target")
    prompts_set_default.add_argument("prompt_pack_id")

    skills_parser = subparsers.add_parser("skills")
    skills_sub = skills_parser.add_subparsers(dest="mode", required=True)
    skills_sub.add_parser("sync")

    artifacts_parser = subparsers.add_parser("artifacts")
    artifacts_sub = artifacts_parser.add_subparsers(dest="mode", required=True)
    artifacts_inspect = artifacts_sub.add_parser("inspect")
    artifacts_inspect.add_argument("item_key")

    return parser


@contextmanager
def _runtime(config: AgentConfig) -> Iterator[tuple[ArtifactStore, PromptPackManager, ReferenceManagerGateway, MineruClient, LlmClient, ImageProvider]]:
    store = ArtifactStore(config.artifacts_dir, config.state_dir)
    prompts = PromptPackManager(config.prompt_pack_dir, config.state_dir, config.default_language)
    gateway = ReferenceManagerGateway(config)
    gateway.connect()
    try:
        yield (
            store,
            prompts,
            gateway,
            MineruClient(config, store),
            LlmClient(config),
            ImageProvider(config),
        )
    finally:
        gateway.close()


def _doctor_payload(config: AgentConfig) -> dict[str, object]:
    return {
        "workspaceRoot": ".",
        "skillRoot": str(config.skill_root),
        "artifactsDir": str(config.artifacts_dir),
        "stateDir": str(config.state_dir),
        "sourceDocsDir": str(config.source_docs_dir),
        "sourceDocsDirExists": config.source_docs_dir.exists(),
        "readingNotesDir": str(config.reading_notes_dir),
        "readingNotesDirExists": config.reading_notes_dir.exists(),
        "promptPackDir": str(config.prompt_pack_dir),
        "codexHome": str(config.codex_home),
        "provider": config.llm_provider,
        "imageProvider": config.image_provider,
        "supportsLocalRead": True,
        "localPdfExtractors": available_local_pdf_extractors(),
        "referenceMcpCommandFound": bool(
            config.reference_mcp_command
            and (
                shutil.which(config.reference_mcp_command)
                or config.reference_mcp_command.startswith("/")
            )
        ),
        "hasMineruKey": bool(config.mineru_api_key),
        "referenceMcpCommand": " ".join(
            [config.reference_mcp_command, *config.reference_mcp_args]
        ).strip(),
    }


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    config = load_config()
    os.chdir(config.workspace_root)

    if args.command == "doctor":
        print(json.dumps(_doctor_payload(config), ensure_ascii=False, indent=2))
        return 0

    if args.command == "prompts":
        manager = PromptPackManager(config.prompt_pack_dir, config.state_dir, config.default_language)
        if args.mode == "list":
            print(json.dumps(manager.list(), ensure_ascii=False, indent=2))
            return 0
        if args.mode == "show":
            print(json.dumps(manager.show(args.prompt_pack_id), ensure_ascii=False, indent=2))
            return 0
        if args.mode == "set-default":
            manager.set_default(args.target, args.prompt_pack_id)
            print(f"Default prompt for {args.target} set to {args.prompt_pack_id}")
            return 0

    if args.command == "skills" and args.mode == "sync":
        print(json.dumps(sync_skill(config), ensure_ascii=False, indent=2))
        return 0

    if args.command == "artifacts" and args.mode == "inspect":
        store = ArtifactStore(config.artifacts_dir, config.state_dir)
        print(json.dumps(inspect_artifacts(args.item_key, store), ensure_ascii=False, indent=2))
        return 0

    if args.command == "read" and args.mode == "local":
        store = ArtifactStore(config.artifacts_dir, config.state_dir)
        prompts = PromptPackManager(config.prompt_pack_dir, config.state_dir, config.default_language)
        mineru = MineruClient(config, store)
        llm = LlmClient(config)
        result = read_local_file(args.path, args.doc_type, config, store, mineru, llm, prompts)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    with _runtime(config) as (store, prompts, gateway, mineru, llm, image_provider):
        if args.command == "read" and args.mode == "item":
            result = read_item_by_key(args.item_key, config, gateway, store, mineru, llm, prompts)
        elif args.command == "read" and args.mode == "search":
            result = read_by_search(args.query, config, gateway, store, mineru, llm, prompts)
        elif args.command == "patent-read" and args.mode == "item":
            result = patent_read_by_key(args.item_key, config, gateway, store, mineru, llm, prompts)
        elif args.command == "image-summary" and args.mode == "item":
            result = generate_image_summary(args.item_key, config, gateway, store, prompts, llm, image_provider)
        elif args.command == "mindmap" and args.mode == "item":
            result = generate_mindmap(args.item_key, config, gateway, store)
        else:
            parser.error("Unsupported command combination")
            return 2

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0
