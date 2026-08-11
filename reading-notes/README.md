# Reading Notes Workflow

## 目录约定

- `source-docs/`: 放待总结的论文 PDF
- `prompts/paper.md`: 总结用的固定 prompt
- `reading-notes/`: 生成的 Markdown 笔记
- `scripts/summarize-paper.sh`: 自动化入口脚本

## 用法

默认总结 `source-docs/` 里最近修改的 PDF：

```bash
scripts/summarize-paper.sh
```

显式指定某个 PDF：

```bash
scripts/summarize-paper.sh source-docs/your-paper.pdf
```

输出文件会写到：

```text
reading-notes/<pdf文件名>.md
```

## 说明

这个流程会调用本机 `codex` CLI，并将目标 PDF 作为输入附件，再套用 `prompts/paper.md` 生成结构化中文摘要。

额外依赖：

- 本机 `codex` 已可用并已登录
- 当前环境允许 `codex` 访问其上游响应服务
