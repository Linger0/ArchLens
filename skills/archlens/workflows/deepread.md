# Deep Read Workflow

## Local file

```bash
python3 skills/archlens/scripts/agent.py read local <path-under-source-docs>
python3 skills/archlens/scripts/agent.py read local <absolute-path>
python3 skills/archlens/scripts/agent.py read local <path> --doc-type patent
```

Outputs:

- `artifacts/items/<local-item-key>/outputs/summary.md`
- `artifacts/items/<local-item-key>/outputs/summaryCard.json`
- `artifacts/items/<local-item-key>/outputs/reviewCard.json`
- `artifacts/items/<local-item-key>/mineru/full.md`
- optional extracted images under `artifacts/items/<local-item-key>/mineru/images/`
- `reading-notes/.../*.md`

## Paper

```bash
python3 skills/archlens/scripts/agent.py read item <itemKey>
python3 skills/archlens/scripts/agent.py read search "<query>"
```

Outputs:

- `summary.md`
- `summaryCard.json`
- `reviewCard.json`
- Reference manager child note, when MCP is configured

## Patent

```bash
python3 skills/archlens/scripts/agent.py patent-read item <itemKey>
```

Outputs:

- Patent-oriented summary note
- Claim and protection scope fields in `summaryCard.json`
