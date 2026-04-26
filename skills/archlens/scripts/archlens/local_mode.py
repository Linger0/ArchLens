from __future__ import annotations

import re
from pathlib import Path

from .store import sha256_bytes


def resolve_source_path(raw_path: str, source_docs_dir: Path) -> Path:
    candidate = Path(raw_path).expanduser()
    path = candidate if candidate.is_absolute() else source_docs_dir / candidate
    resolved = path.resolve()
    if not resolved.exists():
        raise FileNotFoundError(
            f"Local source file not found: {resolved}. Put documents under {source_docs_dir} or pass an absolute path."
        )
    if resolved.is_dir():
        raise IsADirectoryError(f"Expected a file path, got a directory: {resolved}")
    return resolved


def source_relative_path(source_path: Path, source_docs_dir: Path) -> Path | None:
    try:
        return source_path.resolve().relative_to(source_docs_dir.resolve())
    except ValueError:
        return None


def make_local_item_key(source_path: Path, source_docs_dir: Path) -> str:
    relative = source_relative_path(source_path, source_docs_dir)
    identity = relative.as_posix() if relative else str(source_path.resolve())
    slug = _slugify_ascii(source_path.stem) or "document"
    digest = sha256_bytes(identity.encode("utf-8"))[:12]
    return f"local-{slug[:40]}-{digest}"


def note_path_for_source(source_path: Path, source_docs_dir: Path, reading_notes_dir: Path) -> Path:
    relative = source_relative_path(source_path, source_docs_dir)
    if relative is not None:
        return reading_notes_dir / relative.with_suffix(".md")

    slug = _slugify_ascii(source_path.stem) or "document"
    digest = sha256_bytes(str(source_path.resolve()).encode("utf-8"))[:12]
    return reading_notes_dir / "_external" / f"{slug[:40]}-{digest}.md"


def source_display_path(source_path: Path, source_docs_dir: Path) -> str:
    relative = source_relative_path(source_path, source_docs_dir)
    if relative is not None:
        return relative.as_posix()
    return str(source_path.resolve())


def _slugify_ascii(value: str) -> str:
    lowered = value.strip().lower()
    lowered = re.sub(r"[^a-z0-9]+", "-", lowered)
    return lowered.strip("-")
