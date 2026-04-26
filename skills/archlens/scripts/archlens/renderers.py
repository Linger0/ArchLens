from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _render_list(items: list[str]) -> str:
    return "\n".join(f"- {item}" for item in items) if items else "- 暂无"


def render_summary_markdown(summary_card: dict[str, Any]) -> str:
    sections = [
        f"# {summary_card['title']}",
        f"## 核心问题\n{summary_card['coreProblem']}",
        f"## 核心思想\n{summary_card['coreIdea']}",
        f"## 方法 / 方案\n{_render_list(summary_card.get('methodOrSolution', []))}",
        f"## 关键证据\n{_render_list(summary_card.get('keyEvidence', []))}",
        f"## 局限性\n{_render_list(summary_card.get('limitations', []))}",
        f"## 关键词\n{_render_list(summary_card.get('keywords', []))}",
    ]
    if summary_card["docType"] == "paper":
        sections.extend(
            [
                f"## 数据集\n{_render_list(summary_card.get('dataset', []))}",
                f"## 指标\n{_render_list(summary_card.get('metrics', []))}",
                f"## 实验\n{_render_list(summary_card.get('experiments', []))}",
                f"## 创新点\n{_render_list(summary_card.get('novelty', []))}",
                f"## 未来方向\n{_render_list(summary_card.get('futureWork', []))}",
            ]
        )
    else:
        sections.extend(
            [
                f"## 独立权利要求\n{_render_list(summary_card.get('independentClaims', []))}",
                f"## 从属权利要求\n{_render_list(summary_card.get('dependentClaims', []))}",
                f"## 保护范围\n{_render_list(summary_card.get('protectionScope', []))}",
                f"## 实施例\n{_render_list(summary_card.get('implementationExamples', []))}",
                f"## 对比现有技术\n{_render_list(summary_card.get('noveltyVsPriorArt', []))}",
            ]
        )
    return "\n\n".join(section for section in sections if section.strip()) + "\n"


def render_local_summary_note(summary_markdown: str, source_label: str, item_key: str) -> str:
    lines = summary_markdown.splitlines()
    if lines and lines[0].startswith("# "):
        head = lines[0]
        body = "\n".join(lines[1:]).lstrip("\n")
        return (
            f"{head}\n\n"
            f"> Source: `{source_label}`\n"
            f"> Local item key: `{item_key}`\n\n"
            f"{body}".rstrip()
            + "\n"
        )
    return (
        f"> Source: `{source_label}`\n"
        f"> Local item key: `{item_key}`\n\n"
        f"{summary_markdown.rstrip()}\n"
    )


def render_review_markdown(title: str, content: str) -> str:
    return f"# {title}\n\n{content.strip()}\n"


def render_image_summary_note(title: str, visual_brief: dict[str, Any], data_uri: str, artifact_path: Path) -> str:
    return f"""# {title}

![一图流总结]({data_uri})

## 一句话主张
{visual_brief['oneSentenceClaim']}

## 视觉隐喻
{visual_brief['visualMetaphor']}

## 主流程
{_render_list(visual_brief.get('mainPipeline', []))}

## 关键结果
{_render_list(visual_brief.get('keyResults', []))}

## Artifact
- {artifact_path}
"""


def build_mindmap_markdown(summary_card: dict[str, Any]) -> str:
    lines = [
        f"# {summary_card['title']}",
        "## 核心问题",
        f"- {summary_card['coreProblem']}",
        "## 核心思想",
        f"- {summary_card['coreIdea']}",
        "## 方法 / 方案",
        *[f"- {item}" for item in summary_card.get("methodOrSolution", [])],
        "## 关键证据",
        *[f"- {item}" for item in summary_card.get("keyEvidence", [])],
        "## 局限性",
        *[f"- {item}" for item in summary_card.get("limitations", [])],
    ]
    if summary_card["docType"] == "paper":
        lines.extend(["## 创新点", *[f"- {item}" for item in summary_card.get("novelty", [])]])
        lines.extend(["## 未来方向", *[f"- {item}" for item in summary_card.get("futureWork", [])]])
    else:
        lines.extend(["## 权利要求", *[f"- {item}" for item in summary_card.get("independentClaims", [])]])
        lines.extend(["## 保护范围", *[f"- {item}" for item in summary_card.get("protectionScope", [])]])
    return "\n".join(line for line in lines if line.strip())


def render_mindmap_html(markdown_text: str) -> str:
    return f"""<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="utf-8" />
    <title>Mindmap</title>
    <style>
      body {{ margin: 0; font-family: Arial, sans-serif; background: #f8fafc; color: #0f172a; }}
      .wrap {{ max-width: 980px; margin: 0 auto; padding: 32px; }}
      pre {{ white-space: pre-wrap; background: #ffffff; border-radius: 16px; padding: 24px; box-shadow: 0 10px 30px rgba(15, 23, 42, 0.08); }}
    </style>
  </head>
  <body>
    <div class="wrap">
      <h1>Mindmap Markdown</h1>
      <pre>{markdown_text}</pre>
      <script>
        window.__mindmapMarkdown = {json.dumps(markdown_text, ensure_ascii=False)};
      </script>
    </div>
  </body>
</html>"""


def render_mindmap_svg(markdown_text: str) -> str:
    lines = [line.strip() for line in markdown_text.splitlines() if line.strip()]
    width = 1500
    height = max(900, len(lines) * 70 + 120)
    nodes = []
    for index, line in enumerate(lines):
        depth = 0
        content = line
        if line.startswith("## "):
            depth = 1
            content = line[3:]
        elif line.startswith("- "):
            depth = 2
            content = line[2:]
        elif line.startswith("# "):
            depth = 0
            content = line[2:]
        nodes.append((depth, content, 100 + index * 60))
    parts = [f'<rect width="100%" height="100%" fill="#f8fafc"/>']
    for index, (depth, content, y) in enumerate(nodes):
        x = 80 + depth * 260
        if index > 0:
            prev_depth, _, prev_y = nodes[index - 1]
            prev_x = 80 + prev_depth * 260
            parts.append(
                f'<line x1="{prev_x}" y1="{prev_y}" x2="{x}" y2="{y}" stroke="#94a3b8" stroke-width="2"/>'
            )
        parts.append(
            f'<rect x="{x - 16}" y="{y - 28}" width="220" height="48" rx="14" fill="#eff6ff" stroke="#2563eb"/>'
        )
        parts.append(
            f'<text x="{x}" y="{y + 4}" font-size="20" font-family="Arial, sans-serif" fill="#0f172a">{_escape_xml(content)}</text>'
        )
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
  {' '.join(parts)}
</svg>"""


def render_mindmap_note(title: str, mindmap_markdown: str, html_path: Path, svg_path: Path) -> str:
    return f"""# {title}

## 导图 Markdown

```markmap
{mindmap_markdown}
```

## Artifact
- HTML: {html_path}
- SVG: {svg_path}
"""


def render_review_cards_matrix(cards: list[dict[str, Any]]) -> str:
    header = "| Title | Topic | Method | Result |\n| --- | --- | --- | --- |"
    rows = [
        f"| {card['title']} | {card['topic']} | {' / '.join(card['method'])} | {' / '.join(card['result'])} |"
        for card in cards
    ]
    return "\n".join([header, *rows])


def _escape_xml(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )
