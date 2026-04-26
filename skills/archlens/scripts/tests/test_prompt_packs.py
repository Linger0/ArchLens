from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
import sys

CURRENT_DIR = Path(__file__).resolve().parent
SCRIPTS_ROOT = CURRENT_DIR.parent
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from archlens.prompt_packs import PromptPackManager
from archlens.store import write_json


class PromptPackManagerTest(unittest.TestCase):
    def test_prompt_manager_lists_and_sets_default(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            pack_dir = root / "packs"
            state_dir = root / "state"
            pack_dir.mkdir(parents=True, exist_ok=True)
            write_json(
                pack_dir / "paper.default.json",
                {
                    "id": "paper.default",
                    "name": "Paper",
                    "target": "paper",
                    "taskPrompt": "Read",
                    "outputSchema": "SummaryCard",
                },
            )
            manager = PromptPackManager(pack_dir, state_dir, "中文")
            self.assertEqual(len(manager.list()), 1)
            manager.set_default("paper", "paper.default")
            resolved = manager.resolve("paper")
            self.assertEqual(resolved["id"], "paper.default")


if __name__ == "__main__":
    unittest.main()
