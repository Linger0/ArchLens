# ArchLens Agent Instructions

## Project

ArchLens is a paper and patent reading project. Its outputs are Markdown notes generated from source documents, with separate workflows for research papers and patents.

## Layout

- `source-papers/`: source PDFs for research papers.
- `source-patents/`: source PDFs for patents.
- `prompts/paper-read.md`: prompt for paper reading.
- `prompts/patent-read.md`: prompt for patent reading.
- `artifacts/`: MinerU intermediate Markdown, JSON, images, and other extraction resources.
- `reading-notes/`: final Markdown reading notes.
- `skills/`: repository-local skills.
- `skills/paper-patent-reading/SKILL.md`: workflow for MinerU extraction, subagent reading, and note generation.

## Working Rules

- Read the relevant prompt before analyzing a source document and preserve its body.
- Keep MinerU intermediate results under `artifacts/` and preserve image resources referenced by extracted Markdown.
- Write final notes under `reading-notes/` using the source PDF basename.
