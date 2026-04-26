---
name: archlens
description: Use when Codex should deep-read a computer architecture paper or patent from a local file or optional reference manager, normalize PDFs with MinerU or local extraction, generate structured summaries, and optionally create image summaries or mindmaps with Python scripts kept directly inside this skill. Do not use this skill for literature review synthesis; use the separate archlens-literature-review skill when the user explicitly asks for review work.
---

# ArchLens

This skill owns the end-to-end workflow for single-document deep reading.

## Quick start

Run the Python CLI directly:

```bash
python3 skills/archlens/scripts/agent.py doctor
python3 skills/archlens/scripts/agent.py read local demo.md
python3 skills/archlens/scripts/agent.py read item <itemKey>
```

## What this skill does

- Reads local files from `source-docs/` and writes notes into `reading-notes/`
- Searches an optional reference manager through MCP when configured
- Resolves item metadata, children, and PDF paths
- Sends PDFs to MinerU or uses local fallback extraction
- Generates `summaryCard.json`, `reviewCard.json`, `visualBrief.json`
- Writes notes back to the reference manager or to local Markdown files
- Produces one-image summaries and mindmaps

## Utility scripts

```bash
python3 skills/archlens/scripts/source_to_md/pdf_to_md.py source-docs/paper.pdf -o artifacts/tmp/paper.md --assets-dir artifacts/tmp/images
python3 skills/archlens/scripts/image_gen.py "branch predictor cold effects in microservices" -o artifacts/tmp/poster.svg
```

## Workflow selection

- **Paper / patent deep read**: see [workflows/deepread.md](workflows/deepread.md)
- **Image summary / mindmap**: see [workflows/derivatives.md](workflows/derivatives.md)
- **Literature review**: use the separate `skills/archlens-literature-review` scaffold skill only when requested

## References

- Artifact layout and outputs: [references/artifacts.md](references/artifacts.md)
- Prompt pack files: [references/prompt-packs.md](references/prompt-packs.md)

## Notes

- Prefer item-key based commands once the target is known.
- For local mode, place source files under `source-docs/`; the note tree mirrors that structure under `reading-notes/`.
- Use subagents for high-context interpretation, but keep I/O and write-back in the main agent.
- The runnable code lives in `scripts/`.
