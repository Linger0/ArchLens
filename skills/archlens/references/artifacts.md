# Artifact Layout

The repository also keeps human-facing local files in:

```text
source-docs/      original local papers / patents
reading-notes/    generated Markdown notes, mirroring source-docs/
```

The Python skill writes cached artifacts to:

```text
artifacts/
  items/
    <item-key>/
      metadata.json
      jobs/
      mineru/
        full.md
        images/
        content_list.json
        model.json
        middle.json
      outputs/
        bundle.json
        summary.md
        summaryCard.json
        reviewCard.json
        visualBrief.json
        poster.svg|png
        mindmap.md
        mindmap.html
        mindmap.svg
```

Use `python3 skills/archlens/scripts/agent.py artifacts inspect <itemKey>` to inspect paths.

For local reads, `metadata.json` stores:

- `sourcePath`
- `sourceRelativePath`
- `notePath`
- `storageMode=local`
