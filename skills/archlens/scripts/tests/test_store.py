from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
import sys

CURRENT_DIR = Path(__file__).resolve().parent
SCRIPTS_ROOT = CURRENT_DIR.parent
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from archlens.store import ArtifactStore


class ArtifactStoreTest(unittest.TestCase):
    def test_artifact_store_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            store = ArtifactStore(root / "artifacts", root / ".agent-state")
            payload_path = store.output_path("ITEM123", "summaryCard.json")
            store.save_json(payload_path, {"title": "Demo"})
            self.assertEqual(store.load_json(payload_path), {"title": "Demo"})
            self.assertTrue(str(store.metadata_path("ITEM123")).endswith("metadata.json"))


if __name__ == "__main__":
    unittest.main()
