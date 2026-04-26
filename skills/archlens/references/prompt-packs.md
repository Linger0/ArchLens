# Prompt Packs

Prompt packs live under `templates/prompt-packs/`.

Built-in packs:

- `paper.default.json`
- `patent.default.json`
- `review.default.json`
- `visual.default.json`

Use:

```bash
python3 skills/archlens/scripts/agent.py prompts list
python3 skills/archlens/scripts/agent.py prompts show paper.default
python3 skills/archlens/scripts/agent.py prompts set-default paper paper.default
```
