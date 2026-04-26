# ArchLens Standalone Agent Design

ArchLens is a paper-reading project for computer architecture engineers. It is a standalone Codex skill project, not a plugin-first application.

## Direction

- Local files are the default input path.
- `source-docs/` stores original PDFs, Markdown, and text files.
- `reading-notes/` stores generated human-facing notes with a mirrored directory structure.
- `artifacts/` stores machine-readable bundles, extracted Markdown, images, summary cards, review cards, and job files.
- Reference manager MCP support is optional and should stay behind a neutral adapter.
- MinerU is optional. When it is not configured, ArchLens uses local source conversion.
- Image generation is optional. Local SVG output is always available as a lightweight fallback.

## Main Skills

```text
skills/archlens/
  SKILL.md
  scripts/
    agent.py
    image_gen.py
    source_to_md/
      pdf_to_md.py
    archlens/
      config.py
      source_to_md.py
      image_tools.py
      providers.py
      workflows.py

skills/archlens-literature-review/
  SKILL.md
  scripts/
    review_scaffold.py
```

## Core Workflow

1. Resolve a local source path from `source-docs/` or an absolute path supplied by the user.
2. Convert the source to Markdown with `source_to_md`.
3. Cache the normalized bundle under `artifacts/items/<item-key>/`.
4. Generate `summaryCard.json`, `reviewCard.json`, and `summary.md`.
5. Write the readable note under `reading-notes/`.

The default local command is:

```bash
python3 skills/archlens/scripts/agent.py read local <path-under-source-docs>
```

## Source Conversion

`source_to_md` should prefer deterministic local extraction before calling cloud services:

- PDF: PyMuPDF first, then `pdftotext`, then `pypdf`.
- Markdown: pass through.
- Text: wrap as Markdown.
- Embedded PDF images should be extracted when the backend supports it.

## Visual Tools

The image tool starts with a local SVG backend:

```bash
python3 skills/archlens/scripts/image_gen.py "branch predictor cold effects" -o artifacts/tmp/poster.svg
```

Future remote image providers should plug in behind the same script-level interface.

## Naming Rules

- Public names use `ArchLens`.
- Environment variables use `ARCHLENS_*`.
- Paths written to artifacts and notes should be relative to the repository whenever possible.
- Reference-manager-specific names should stay inside adapter internals only when required by external tool names.

## Literature Review

Multi-paper literature review is separate from the main deep-read skill. The current `archlens-literature-review` skill only scaffolds review matrices from existing `reviewCard.json`, `summaryCard.json`, or local notes.
