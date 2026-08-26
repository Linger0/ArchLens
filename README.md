# ArchLens

ArchLens 是一个用于阅读和整理 CPU 架构、微架构论文与专利的项目。

仓库内的 agent skills 位于 `.agents/skills/`，该目录会作为默认 skills 目录加载。

## MinerU 依赖

本项目依赖 MinerU 文档提取技能。如果当前环境没有该技能，请先按照官方 [`SKILL.md`](https://github.com/opendatalab/MinerU-Ecosystem/blob/main/skills/SKILL.md) 安装。

安装 `mineru-open-api` CLI：

```bash
npm install -g mineru-open-api
```

验证安装：

```bash
mineru-open-api version
```

## MinerU API 配置

使用 MinerU 的完整提取功能前，需要先在 [API Token 管理页面](https://mineru.net/apiManage/token) 申请 Token，并在启动 agent 之前定义环境变量：

```bash
export MINERU_TOKEN="your-mineru-token"
```

agent 会继承启动它的父进程环境，因此应从设置了该变量的同一个终端启动 agent。如果希望每次启动终端都自动设置，可将配置写入 `~/.bashrc` 或 `~/.zshrc`，然后重新启动 agent：

```bash
# ~/.bashrc 或 ~/.zshrc
export MINERU_TOKEN="your-mineru-token"
```

可以在 agent 所在的执行环境中检查变量是否存在，并验证 Token（不会输出 Token 内容）：

```bash
test -n "$MINERU_TOKEN" && echo "MINERU_TOKEN is set"
mineru-open-api auth --verify
```

如果 agent 由服务管理器启动，请在对应的服务环境配置中设置 `MINERU_TOKEN`，而不是只在交互式终端中设置。不要将真实 Token 写入仓库或提交记录。

## 最小示例

```bash
mineru-open-api extract \
  "source-papers/example-paper.pdf" \
  -o "artifacts/example-paper/" \
  -f md,json
```
