#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPTS_ROOT = Path(__file__).resolve().parents[1]
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from archlens.source_to_md import available_source_extractors, convert_source_to_markdown  # noqa: E402
from archlens.store import write_text  # noqa: E402


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="pdf_to_md", description="Convert a local paper PDF/TXT/MD source to Markdown")
    parser.add_argument("source", nargs="?")
    parser.add_argument("-o", "--output")
    parser.add_argument("--assets-dir")
    parser.add_argument("--list-extractors", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.list_extractors:
        print(json.dumps({"extractors": available_source_extractors()}, ensure_ascii=False, indent=2))
        return 0
    if not args.source or not args.output:
        parser.error("source and --output are required unless --list-extractors is used")

    assets_dir = Path(args.assets_dir) if args.assets_dir else None
    result = convert_source_to_markdown(Path(args.source), assets_dir)
    output_path = Path(args.output)
    write_text(output_path, result.markdown)
    print(
        json.dumps(
            {
                "source": args.source,
                "output": output_path.as_posix(),
                "parser": result.parser,
                "imagePaths": [path.as_posix() for path in result.image_paths],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
