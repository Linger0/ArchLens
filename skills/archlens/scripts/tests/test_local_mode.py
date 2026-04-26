from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
import sys

CURRENT_DIR = Path(__file__).resolve().parent
SCRIPTS_ROOT = CURRENT_DIR.parent
REPO_ROOT = CURRENT_DIR.parents[3]
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from archlens.config import AgentConfig
from archlens.local_mode import make_local_item_key, note_path_for_source
from archlens.prompt_packs import PromptPackManager
from archlens.providers import LlmClient, LocalFileGateway, MineruClient
from archlens.store import ArtifactStore
from archlens.workflows import read_local_file


def _build_config(root: Path) -> AgentConfig:
    skill_root = REPO_ROOT / "skills" / "archlens"
    return AgentConfig(
        workspace_root=root,
        skill_root=skill_root,
        artifacts_dir=root / "artifacts",
        state_dir=root / ".agent-state",
        source_docs_dir=root / "source-docs",
        reading_notes_dir=root / "reading-notes",
        prompt_pack_dir=skill_root / "templates" / "prompt-packs",
        codex_home=root / ".codex",
        default_language="中文",
        note_title_prefix="ArchLens",
        reference_mcp_command="reference-mcp",
        reference_mcp_args=[],
        mineru_api_url="https://mineru.net",
        mineru_api_key="",
        mineru_poll_interval_ms=100,
        mineru_timeout_ms=1000,
        llm_provider="mock",
        gemini_api_url="https://generativelanguage.googleapis.com",
        gemini_api_key="",
        gemini_model="gemini-2.5-pro",
        openai_compat_api_url="",
        openai_compat_api_key="",
        openai_compat_model="gpt-4.1",
        image_provider="local-svg",
        gemini_image_model="gemini-2.0-flash-preview-image-generation",
        openai_compat_image_model="gpt-image-1",
        image_canvas_width=1600,
        image_canvas_height=900,
    )


class LocalModeTest(unittest.TestCase):
    def test_note_path_mirrors_source_tree(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source_docs_dir = root / "source-docs"
            reading_notes_dir = root / "reading-notes"
            source_path = source_docs_dir / "ml" / "gnn" / "paper-one.pdf"

            note_path = note_path_for_source(source_path, source_docs_dir, reading_notes_dir)

            self.assertEqual(
                note_path,
                reading_notes_dir / "ml" / "gnn" / "paper-one.md",
            )
            self.assertTrue(make_local_item_key(source_path, source_docs_dir).startswith("local-paper-one-"))

    def test_external_source_paths_are_bucketed_under_external_notes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source_docs_dir = root / "source-docs"
            reading_notes_dir = root / "reading-notes"
            external_path = root / "downloads" / "outside-paper.md"

            note_path = note_path_for_source(external_path, source_docs_dir, reading_notes_dir)

            self.assertEqual(note_path.parent, reading_notes_dir / "_external")
            self.assertEqual(note_path.suffix, ".md")

    def test_read_local_markdown_writes_note_and_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config = _build_config(root)
            source_path = config.source_docs_dir / "ml" / "demo-paper.md"
            source_path.parent.mkdir(parents=True, exist_ok=True)
            source_path.write_text(
                "# Demo Paper\n\n- A new benchmark\n- A stronger encoder\n- Better results on graphs\n",
                encoding="utf-8",
            )

            store = ArtifactStore(config.artifacts_dir, config.state_dir)
            prompts = PromptPackManager(config.prompt_pack_dir, config.state_dir, config.default_language)
            mineru = MineruClient(config, store)
            llm = LlmClient(config)

            result = read_local_file("ml/demo-paper.md", None, config, store, mineru, llm, prompts)

            note_path = config.workspace_root / Path(result["notePath"])
            self.assertTrue(note_path.exists())
            self.assertEqual(note_path, config.reading_notes_dir / "ml" / "demo-paper.md")
            self.assertIn("Source:", note_path.read_text(encoding="utf-8"))

            item_key = result["item"]["itemKey"]
            self.assertTrue(store.output_path(item_key, "summary.md").exists())
            self.assertTrue(store.output_path(item_key, "summaryCard.json").exists())
            self.assertTrue(store.output_path(item_key, "reviewCard.json").exists())
            metadata = store.load_json(store.metadata_path(item_key))
            self.assertEqual(metadata["notePath"], "reading-notes/ml/demo-paper.md")

    def test_local_gateway_reads_plain_text_without_mineru(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config = _build_config(root)
            source_path = config.source_docs_dir / "txt" / "paper.txt"
            source_path.parent.mkdir(parents=True, exist_ok=True)
            source_path.write_text(
                "This is a plain text paper.\nIt has enough content for a local summary.",
                encoding="utf-8",
            )

            store = ArtifactStore(config.artifacts_dir, config.state_dir)
            mineru = MineruClient(config, store)
            gateway = LocalFileGateway(config, store, mineru)

            item, doc_type, source_path = gateway.prepare_item("txt/paper.txt")
            bundle = gateway.extract_and_normalize(item["itemKey"], doc_type, str(source_path))

            self.assertEqual(doc_type, "paper")
            self.assertEqual(bundle["parser"], "local-text")
            self.assertTrue(Path(bundle["fullMarkdownPath"]).exists())


if __name__ == "__main__":
    unittest.main()
