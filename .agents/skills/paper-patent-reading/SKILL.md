---
name: paper-patent-reading
description: Use when reading, extracting, or summarizing a research paper or patent in this repository, especially PDFs under source-papers/ or source-patents/. It combines the repository's paper/patent prompts, MinerU extraction with preserved images, and a subagent-written Markdown note under reading-notes/.
---

# Paper and Patent Reading

Use this skill for the repository's paper and patent reading workflow. Follow the selected prompt for the content and presentation of the resulting note.

## Workflow Paths

- Paper PDFs: `source-papers/`
- Patent PDFs: `source-patents/`
- Paper prompt: `prompts/paper-read.md`
- Patent prompt: `prompts/patent-read.md`
- MinerU artifacts: `artifacts/<document-slug>/`
- Final notes: `reading-notes/<pdf-basename>.md`

## Workflow

### 1. Identify the document and prompt

Inspect the target PDF and its basename. Use `prompts/paper-read.md` for CPU architecture or microarchitecture papers and `prompts/patent-read.md` for patent analysis. Read the selected prompt completely before delegating the summary.

Choose a stable slug from the PDF basename and create `artifacts/<document-slug>/`. Keep all intermediate MinerU output in that directory.

### 2. Extract with MinerU

Use the `MinerU Document Extractor` skill.

Example:

```bash
mkdir -p artifacts/<document-slug>
mineru-open-api extract \
  "source-papers/<paper>.pdf" \
  -o "artifacts/<document-slug>/" \
  -f md,json \
  --model pipeline \
  --language en \
  --timeout 900
```

If the direct `extract` command cannot run because the CLI or MinerU token is unavailable, report that extraction is blocked and do not silently claim that image resources were produced. Use `flash-extract` only when a text-only fallback is acceptable.

### 3. Validate the intermediate artifact

Confirm that the output Markdown, and JSON when requested, exist. For image-preserving extraction:

- Confirm `artifacts/<document-slug>/images/` contains non-empty image files.
- Extract every `images/...` reference from the Markdown and verify that the referenced file exists relative to the Markdown file.
- Treat `<!-- image-->` placeholders without actual files as incomplete image extraction.

### 4. Delegate the reading note

Delegate the reading task with these inputs:

1. The complete selected prompt file.
2. The MinerU Markdown artifact and its image resources.
3. The source PDF for spot-checking ambiguous extraction.
4. The exact final output path under `reading-notes/`.

Tell the subagent to write the Markdown file directly, not merely return a draft, and follow the selected prompt completely.
