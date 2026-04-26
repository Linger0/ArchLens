#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import time
from pathlib import Path
from typing import Any


def _workspace_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _slugify(value: str) -> str:
    lowered = value.strip().lower()
    lowered = re.sub(r"[^a-z0-9]+", "-", lowered)
    return lowered.strip("-") or "review"


def _rel(path: Path, workspace_root: Path) -> str:
    try:
        return path.resolve().relative_to(workspace_root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _first_heading(markdown_text: str) -> str | None:
    for line in markdown_text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return None


def _load_item_row(workspace_root: Path, item_key: str) -> dict[str, str]:
    item_dir = workspace_root / "artifacts" / "items" / item_key
    review_card_path = item_dir / "outputs" / "reviewCard.json"
    summary_card_path = item_dir / "outputs" / "summaryCard.json"
    metadata_path = item_dir / "metadata.json"

    if review_card_path.exists():
        payload = _read_json(review_card_path)
        return {
            "source_ref": item_key,
            "title": str(payload.get("title", item_key)),
            "topic": str(payload.get("topic", "")),
            "method": " / ".join(payload.get("method", []) or []),
            "result": " / ".join(payload.get("result", []) or []),
            "notes": "",
        }

    if summary_card_path.exists():
        payload = _read_json(summary_card_path)
        return {
            "source_ref": item_key,
            "title": str(payload.get("title", item_key)),
            "topic": " / ".join(payload.get("keywords", [])[:3]),
            "method": " / ".join(payload.get("methodOrSolution", [])[:3]),
            "result": " / ".join(payload.get("keyEvidence", [])[:3]),
            "notes": "",
        }

    if metadata_path.exists():
        payload = _read_json(metadata_path)
        return {
            "source_ref": item_key,
            "title": str(payload.get("title", item_key)),
            "topic": "",
            "method": "",
            "result": "",
            "notes": "No reviewCard.json or summaryCard.json yet.",
        }

    raise FileNotFoundError(f"No artifacts found for item key: {item_key}")


def _load_note_row(workspace_root: Path, note_input: str) -> dict[str, str]:
    candidate = Path(note_input).expanduser()
    note_path = candidate if candidate.is_absolute() else workspace_root / "reading-notes" / candidate
    resolved = note_path.resolve()
    if not resolved.exists():
        raise FileNotFoundError(f"Review note not found: {resolved}")
    markdown_text = resolved.read_text(encoding="utf-8", errors="ignore")
    title = _first_heading(markdown_text) or resolved.stem
    return {
            "source_ref": _rel(resolved, workspace_root),
        "title": title,
        "topic": "",
        "method": "",
        "result": "",
        "notes": "Imported from local reading note.",
    }


def _write_matrix_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["source_ref", "title", "topic", "method", "result", "notes"],
        )
        writer.writeheader()
        writer.writerows(rows)


def _write_review_markdown(path: Path, title: str, rows: list[dict[str, str]], source_mode: str) -> None:
    lines = [
        f"# {title}",
        "",
        "## Scope",
        f"- Source mode: {source_mode}",
        f"- Generated at: {time.strftime('%Y-%m-%d %H:%M:%S')}",
        f"- Seed papers: {len(rows)}",
        "",
        "## Search Expansion TODO",
        "- Define search keywords and synonyms.",
        "- Add inclusion / exclusion criteria.",
        "- Decide whether to expand from reference manager collections, local notes, or both.",
        "",
        "## Comparison Matrix",
        "| Source | Title | Topic | Method | Result | Notes |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        lines.append(
            f"| {row['source_ref']} | {row['title']} | {row['topic']} | {row['method']} | {row['result']} | {row['notes']} |"
        )
    lines.extend(
        [
            "",
            "## Review Questions",
            "- What are the dominant methods?",
            "- Where do results disagree?",
            "- Which benchmarks or datasets are missing?",
            "",
            "## Next Step",
            "- Enrich this scaffold with more papers, clustering, and final narrative synthesis.",
            "",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="review-scaffold", description="Literature review scaffold CLI")
    subparsers = parser.add_subparsers(dest="mode", required=True)

    items = subparsers.add_parser("items")
    items.add_argument("item_keys", nargs="+")
    items.add_argument("--title", default="Literature Review Scaffold")

    notes = subparsers.add_parser("notes")
    notes.add_argument("note_paths", nargs="+")
    notes.add_argument("--title", default="Literature Review Scaffold")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    workspace_root = _workspace_root()

    if args.mode == "items":
        rows = [_load_item_row(workspace_root, item_key) for item_key in args.item_keys]
        source_mode = "artifacts"
    else:
        rows = [_load_note_row(workspace_root, note_path) for note_path in args.note_paths]
        source_mode = "reading-notes"

    review_id = f"{_slugify(args.title)}-{time.strftime('%Y%m%d-%H%M%S')}"
    review_dir = workspace_root / "artifacts" / "reviews" / review_id
    markdown_path = review_dir / "review-scaffold.md"
    csv_path = review_dir / "matrix.csv"

    _write_review_markdown(markdown_path, args.title, rows, source_mode)
    _write_matrix_csv(csv_path, rows)

    print(
        json.dumps(
            {
                "reviewId": review_id,
                "sourceMode": source_mode,
                "seedCount": len(rows),
                "markdownPath": _rel(markdown_path, workspace_root),
                "matrixCsvPath": _rel(csv_path, workspace_root),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
