#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPTS_ROOT = Path(__file__).resolve().parent
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from archlens.image_tools import visual_brief_from_prompt, write_local_svg  # noqa: E402


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="image_gen", description="Generate a local SVG visual summary from prompt or VisualBrief JSON")
    parser.add_argument("prompt", nargs="?", default="")
    parser.add_argument("-o", "--output", default="artifacts/image-gen/poster.svg")
    parser.add_argument("--visual-brief")
    parser.add_argument("--backend", default="local-svg", choices=["local-svg"])
    parser.add_argument("--width", type=int, default=1600)
    parser.add_argument("--height", type=int, default=900)
    parser.add_argument("--list-backends", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.list_backends:
        print(json.dumps({"backends": ["local-svg"]}, ensure_ascii=False, indent=2))
        return 0

    if args.visual_brief:
        visual_brief = json.loads(Path(args.visual_brief).read_text(encoding="utf-8"))
    else:
        visual_brief = visual_brief_from_prompt(args.prompt)

    output_path = Path(args.output)
    write_local_svg(output_path, visual_brief, args.width, args.height)
    print(
        json.dumps(
            {
                "backend": args.backend,
                "output": output_path.as_posix(),
                "mimeType": "image/svg+xml",
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
