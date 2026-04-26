# Literature Review Scaffold

This skill is a scaffold, not the final literature review engine.

## From existing deep-read artifacts

```bash
python3 skills/archlens-literature-review/scripts/review_scaffold.py items <itemKey1> <itemKey2>
```

The script looks for:

- `artifacts/items/<itemKey>/outputs/reviewCard.json`
- fallback: `artifacts/items/<itemKey>/outputs/summaryCard.json`
- fallback: `artifacts/items/<itemKey>/metadata.json`

## From local notes

```bash
python3 skills/archlens-literature-review/scripts/review_scaffold.py notes <note1.md> <note2.md>
```

Relative note paths are resolved from `reading-notes/`.

## Outputs

The scaffold is written to:

```text
artifacts/reviews/<review-id>/
  review-scaffold.md
  matrix.csv
```
