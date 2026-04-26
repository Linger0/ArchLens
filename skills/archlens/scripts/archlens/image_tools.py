from __future__ import annotations

import html
import textwrap
from pathlib import Path
from typing import Any

from .store import write_binary


def visual_brief_from_prompt(prompt: str) -> dict[str, Any]:
    clean = " ".join(prompt.split())
    return {
        "title": clean[:80] or "ArchLens Visual Summary",
        "oneSentenceClaim": clean or "Visual summary generated from a paper note.",
        "visualMetaphor": "computer architecture pipeline and evidence map",
        "mainPipeline": [clean] if clean else [],
        "keyModules": [],
        "keyResults": [],
        "mustIncludeTerms": [],
        "avoidTerms": [],
        "preferredPalette": ["#101820", "#2f7dd1", "#c9a227", "#f3f6f8"],
        "layoutStyle": "technical one-page architecture reading poster",
    }


def generate_local_svg(visual_brief: dict[str, Any], width: int = 1600, height: int = 900) -> bytes:
    title = _escape(str(visual_brief.get("title", "ArchLens Visual Summary")))
    claim = _escape(str(visual_brief.get("oneSentenceClaim", "")))
    pipeline = [str(item) for item in visual_brief.get("mainPipeline", []) if str(item).strip()]
    modules = [str(item) for item in visual_brief.get("keyModules", []) if str(item).strip()]
    results = [str(item) for item in visual_brief.get("keyResults", []) if str(item).strip()]
    palette = [str(item) for item in visual_brief.get("preferredPalette", []) if str(item).strip()]
    palette = [*palette, "#101820", "#2f7dd1", "#c9a227", "#f3f6f8"][:4]
    bg, blue, gold, paper = palette
    left_x = 90
    top_y = 90
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        f'<rect width="100%" height="100%" fill="{_escape(bg)}"/>',
        f'<rect x="44" y="44" width="{width - 88}" height="{height - 88}" rx="8" fill="{_escape(paper)}"/>',
        f'<rect x="44" y="44" width="18" height="{height - 88}" fill="{_escape(gold)}"/>',
        f'<text x="{left_x}" y="{top_y}" font-family="Georgia, serif" font-size="48" fill="{_escape(bg)}">{title}</text>',
    ]
    parts.extend(_text_lines(claim, left_x, top_y + 70, 34, 76, bg))

    card_y = top_y + 180
    parts.extend(_section("Pipeline", pipeline, left_x, card_y, 430, blue, bg))
    parts.extend(_section("Key Modules", modules, left_x + 500, card_y, 430, gold, bg))
    parts.extend(_section("Evidence", results, left_x + 1000, card_y, 420, blue, bg))
    parts.append(f'<text x="{left_x}" y="{height - 84}" font-family="Arial, sans-serif" font-size="22" fill="{_escape(bg)}">ArchLens architecture paper visual brief</text>')
    parts.append("</svg>")
    return "\n".join(parts).encode("utf-8")


def write_local_svg(output_path: Path, visual_brief: dict[str, Any], width: int = 1600, height: int = 900) -> None:
    write_binary(output_path, generate_local_svg(visual_brief, width, height))


def _section(title: str, items: list[str], x: int, y: int, width: int, accent: str, text_color: str) -> list[str]:
    rows = items[:6] or ["Pending model-generated detail"]
    parts = [
        f'<rect x="{x}" y="{y}" width="{width}" height="500" rx="8" fill="#ffffff" stroke="{_escape(accent)}" stroke-width="3"/>',
        f'<text x="{x + 28}" y="{y + 54}" font-family="Arial, sans-serif" font-size="28" font-weight="700" fill="{_escape(text_color)}">{_escape(title)}</text>',
    ]
    cursor = y + 105
    for index, item in enumerate(rows, start=1):
        parts.append(f'<circle cx="{x + 36}" cy="{cursor - 8}" r="9" fill="{_escape(accent)}"/>')
        parts.extend(_text_lines(f"{index}. {item}", x + 58, cursor, 20, 36, text_color, width=34))
        cursor += 72
    return parts


def _text_lines(
    value: str,
    x: int,
    y: int,
    font_size: int,
    line_height: int,
    color: str,
    width: int = 74,
) -> list[str]:
    lines = textwrap.wrap(value, width=width) or [""]
    return [
        f'<text x="{x}" y="{y + index * line_height}" font-family="Arial, sans-serif" font-size="{font_size}" fill="{_escape(color)}">{_escape(line)}</text>'
        for index, line in enumerate(lines[:5])
    ]


def _escape(value: str) -> str:
    return html.escape(value, quote=True)
