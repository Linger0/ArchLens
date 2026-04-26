---
name: archlens-literature-review
description: Use only when the user explicitly wants a multi-paper literature review, comparison matrix, or review scaffold. This skill is optional and separate from single-paper deep reading. It currently scaffolds review inputs from existing artifacts or reading notes and generates comparison tables and TODO sections for later expansion.
---

# ArchLens Literature Review

This skill is intentionally separate from `archlens`.

Use it only when the user explicitly asks for:

- 多文献综述
- 论文对比表
- 综述选题脚手架
- 已读论文的矩阵整理

## Quick start

```bash
python3 skills/archlens-literature-review/scripts/review_scaffold.py items <itemKey1> <itemKey2>
python3 skills/archlens-literature-review/scripts/review_scaffold.py notes <path1> <path2>
```

## What this skill does today

- Reads existing `reviewCard.json` / `summaryCard.json` / local notes
- Builds a review scaffold under `artifacts/reviews/`
- Generates a Markdown review outline
- Generates a CSV comparison matrix

## What this skill does later

- Expand related literature retrieval
- Add better clustering and topic grouping
- Add stronger table synthesis and gap analysis

## Workflow

- Review scaffold usage: see [workflows/review.md](workflows/review.md)
