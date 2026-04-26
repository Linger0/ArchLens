# ArchLens

ArchLens 是一个面向计算机体系结构工程师的论文 / 专利精读 Agent。

当前核心入口在 [skills/archlens](skills/archlens/SKILL.md)，多文献综述能力单独放在 [skills/archlens-literature-review](skills/archlens-literature-review/SKILL.md)。

## 这个项目适合做什么

- 对单篇论文做结构化精读，输出 Markdown 笔记和结构化卡片
- 对专利做专利导向的精读，补充权利要求和保护范围字段
- 从本地 PDF / Markdown / TXT 启动阅读流程，不依赖外部文献库也能工作
- 在接入 reference manager MCP 后，按 `itemKey` 检索条目、读取 PDF、回写子笔记
- 为已读条目生成一图流总结和思维导图
- 为后续综述工作沉淀 `summaryCard.json`、`reviewCard.json` 等中间产物

## 核心特点

- 本地优先：默认从 `source-docs/` 读取原始文档，把结果写入 `reading-notes/`
- 渐进增强：本地模式可单独运行，MCP、MinerU、远程模型都不是必需项
- 可审计：中间产物统一落到 `artifacts/`，便于追踪、复查和复用
- 输出分层：同时保留面向人的 Markdown 笔记和面向机器的 JSON / job 文件
- 低门槛启动：默认 `mock` 文本模型和 `local-svg` 图片模式可直接跑通流程

## 能力边界

ArchLens 目前更像一个可运行的 skill 仓库，而不是完整产品。它已经覆盖单篇精读主链路，但多文献综述仍以脚手架为主，适合在已有卡片产物基础上继续扩展。

## 快速开始

### 1. 准备环境

- 建议 Python `3.10+`
- 本地精读 Markdown / TXT 时，不需要额外依赖
- 本地精读 PDF 时，建议至少准备以下能力之一：
  - `PyMuPDF`
  - `pdftotext`
  - `pypdf`
  - 或配置 `MINERU_API_KEY` 走 MinerU 云端解析

### 2. 配置 `.env`

复制示例配置：

```bash
cp .env.example .env
```

默认配置已经可以跑通一个“本地 smoke test”：

- `ARCHLENS_PROVIDER=mock`
- `ARCHLENS_IMAGE_PROVIDER=local-svg`

这意味着：

- 文本总结会使用本地启发式抽取，而不是远程大模型
- 图片总结会生成本地 SVG，而不是调用图像模型

如果你要获得更像正式产出的精读结果，建议再补充：

- `GEMINI_API_KEY`，并把 `ARCHLENS_PROVIDER` 设为 `gemini`
- 或 `OPENAI_COMPAT_API_URL` / `OPENAI_COMPAT_API_KEY`，并把 `ARCHLENS_PROVIDER` 设为 `openai-compat`
- `ARCHLENS_REFERENCE_MCP_COMMAND` 与 `ARCHLENS_REFERENCE_MCP_ARGS`，用于接入 reference manager
- `MINERU_API_KEY`，用于云端 PDF 解析

### 3. 先做一次自检

```bash
python3 skills/archlens/scripts/agent.py doctor
python3 skills/archlens/scripts/agent.py prompts list
```

`doctor` 会输出当前 workspace、目录、provider、是否检测到本地 PDF 提取器、是否配置了 MinerU / MCP 等状态。

### 4. 跑通本地精读

把论文、专利或笔记原文放到 `source-docs/`，然后执行：

```bash
python3 skills/archlens/scripts/agent.py read local demo.md
python3 skills/archlens/scripts/agent.py read local papers/foo.pdf
python3 skills/archlens/scripts/agent.py read local patents/bar.pdf --doc-type patent
```

如果文件位于 `source-docs/ml/gnn/paper1.pdf`，生成的可读笔记默认会写到：

```text
reading-notes/ml/gnn/paper1.md
```

## 典型工作流

### 本地单篇精读

适合先在仓库内跑通流程，不依赖外部文献库。

```bash
python3 skills/archlens/scripts/agent.py read local <path-under-source-docs>
python3 skills/archlens/scripts/agent.py read local <absolute-path>
python3 skills/archlens/scripts/agent.py read local <path> --doc-type patent
```

### 通过 reference manager 精读

在配置 MCP 后，可以直接按条目读取：

```bash
python3 skills/archlens/scripts/agent.py read item <itemKey>
python3 skills/archlens/scripts/agent.py read search "graph neural network"
python3 skills/archlens/scripts/agent.py patent-read item <itemKey>
```

默认行为包括：

- 读取条目元数据和主 PDF
- 生成 `summary.md`、`summaryCard.json`、`reviewCard.json`
- 回写 child note
- 给源条目打上 `AI-Read` 标签

### 派生产物

在已有 `summaryCard.json` 的前提下，可继续生成视觉摘要或思维导图：

```bash
python3 skills/archlens/scripts/agent.py image-summary item <itemKey>
python3 skills/archlens/scripts/agent.py mindmap item <itemKey>
```

### 多文献综述脚手架

综述能力故意独立在另一个 skill 中，避免和单篇精读主链路耦合：

```bash
python3 skills/archlens-literature-review/scripts/review_scaffold.py items <itemKey1> <itemKey2>
```

## 输出目录约定

仓库里默认有三类核心目录：

```text
source-docs/      原始论文 / 专利 / Markdown / TXT
reading-notes/    面向人的精读笔记输出
artifacts/        缓存、结构化卡片、作业描述和派生产物
```

`artifacts/` 下的典型布局如下：

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
        poster.svg | poster.png
        mindmap.md
        mindmap.html
        mindmap.svg
```

可以通过下面的命令定位某个条目的产物路径：

```bash
python3 skills/archlens/scripts/agent.py artifacts inspect <itemKey>
```

## 常用命令

```bash
python3 skills/archlens/scripts/agent.py doctor
python3 skills/archlens/scripts/agent.py prompts list
python3 skills/archlens/scripts/agent.py prompts show <promptPackId>
python3 skills/archlens/scripts/agent.py prompts set-default <target> <promptPackId>
python3 skills/archlens/scripts/agent.py skills sync
python3 skills/archlens/scripts/agent.py read local <path-under-source-docs>
python3 skills/archlens/scripts/agent.py read item <itemKey>
python3 skills/archlens/scripts/agent.py read search "<query>"
python3 skills/archlens/scripts/agent.py patent-read item <itemKey>
python3 skills/archlens/scripts/agent.py image-summary item <itemKey>
python3 skills/archlens/scripts/agent.py mindmap item <itemKey>
python3 skills/archlens/scripts/agent.py artifacts inspect <itemKey>
```

## 关键配置项

下面这些环境变量最常用：

| 变量 | 作用 |
| --- | --- |
| `ARCHLENS_PROVIDER` | 文本模型提供方，支持 `mock`、`gemini`、`openai-compat` |
| `ARCHLENS_IMAGE_PROVIDER` | 图片提供方，支持 `local-svg`、`gemini`、`openai-compat` |
| `ARCHLENS_LANGUAGE` | Prompt Pack 默认输出语言 |
| `ARCHLENS_SOURCE_DOCS_DIR` | 原始文档目录 |
| `ARCHLENS_READING_NOTES_DIR` | 精读笔记输出目录 |
| `ARCHLENS_ARTIFACTS_DIR` | 结构化产物目录 |
| `ARCHLENS_REFERENCE_MCP_COMMAND` | reference manager MCP 命令 |
| `ARCHLENS_REFERENCE_MCP_ARGS` | reference manager MCP 参数 |
| `MINERU_API_KEY` | MinerU 云端 PDF 解析密钥 |
| `GEMINI_API_KEY` | Gemini 文本 / 图片模型密钥 |
| `OPENAI_COMPAT_API_URL` | OpenAI-compatible 接口地址 |
| `OPENAI_COMPAT_API_KEY` | OpenAI-compatible 接口密钥 |

完整示例见 [.env.example](.env.example)。

## PDF 解析策略

PDF 解析采用“可选云端增强，本地兜底”的策略：

1. 如果配置了 `MINERU_API_KEY`，会先尝试 MinerU
2. 如果 MinerU 未配置，或解析失败，则回退到本地提取器
3. 本地提取器按 `PyMuPDF`、`pdftotext`、`pypdf` 的顺序尝试
4. 如果都不可用，会报错并提示安装本地提取器或配置 MinerU

这套策略可以让你按需求选择：

- 想要零外部依赖：读 `.md` / `.txt`
- 想要本地 PDF：安装至少一个 PDF 提取器
- 想要更强的 PDF 结构化效果：启用 MinerU

## 仓库结构

```text
skills/archlens/                    单篇精读主 skill
skills/archlens-literature-review/  多文献综述脚手架
doc/                                设计文档
source-docs/                        原始输入目录
reading-notes/                      笔记输出目录
```

## 相关文档

- [skills/archlens/SKILL.md](skills/archlens/SKILL.md)
- [skills/archlens/workflows/deepread.md](skills/archlens/workflows/deepread.md)
- [skills/archlens/workflows/derivatives.md](skills/archlens/workflows/derivatives.md)
- [skills/archlens/references/artifacts.md](skills/archlens/references/artifacts.md)
- [doc/CodexStandaloneAgentDesign.md](doc/CodexStandaloneAgentDesign.md)
