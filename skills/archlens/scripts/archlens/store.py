from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write_text(path: Path, content: str) -> None:
    ensure_dir(path.parent)
    path.write_text(content, encoding="utf-8")


def read_json(path: Path) -> Any:
    return json.loads(read_text(path))


def write_json(path: Path, payload: Any) -> None:
    write_text(path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


def write_binary(path: Path, payload: bytes) -> None:
    ensure_dir(path.parent)
    path.write_bytes(payload)


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


@dataclass(slots=True)
class ArtifactStore:
    artifacts_dir: Path
    state_dir: Path

    def __post_init__(self) -> None:
        ensure_dir(self.artifacts_dir)
        ensure_dir(self.state_dir)

    def item_dir(self, item_key: str) -> Path:
        return self.artifacts_dir / "items" / item_key

    def metadata_path(self, item_key: str) -> Path:
        return self.item_dir(item_key) / "metadata.json"

    def mineru_dir(self, item_key: str) -> Path:
        return self.item_dir(item_key) / "mineru"

    def outputs_dir(self, item_key: str) -> Path:
        return self.item_dir(item_key) / "outputs"

    def jobs_dir(self, item_key: str) -> Path:
        return self.item_dir(item_key) / "jobs"

    def output_path(self, item_key: str, file_name: str) -> Path:
        return self.outputs_dir(item_key) / file_name

    def job_path(self, item_key: str, job_name: str) -> Path:
        return self.jobs_dir(item_key) / f"{job_name}.json"

    def exists(self, path: Path) -> bool:
        return path.exists()

    def save_json(self, path: Path, payload: Any) -> None:
        write_json(path, payload)

    def load_json(self, path: Path) -> Any:
        return read_json(path)

    def save_text(self, path: Path, content: str) -> None:
        write_text(path, content)

    def load_text(self, path: Path) -> str:
        return read_text(path)

    def save_binary(self, path: Path, payload: bytes) -> None:
        write_binary(path, payload)


def sync_tree(source: Path, target: Path) -> None:
    ensure_dir(target.parent)
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(source, target)
