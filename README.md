# ArchLens

ArchLens 是一个用于阅读和整理 CPU 架构、微架构论文与专利的项目。

## MinerU 依赖

本项目依赖 MinerU 文档提取技能。如果当前环境没有该技能，请先按照官方文档安装对应的 [Skill](https://mineru.net/ecosystem) 和 [CLI](https://mineru.net/ecosystem?tab=cli)。

安装 `mineru-open-api` CLI：

```bash
npm install -g mineru-open-api
```

验证安装：

```bash
mineru-open-api version
```

### MinerU API 配置

没有 API 也能使用 MinerU，不过只能提取文字内容，配置 API 后可以提取文档图片。需要先在 [API Token 管理页面](https://mineru.net/apiManage/token) 申请 Token，然后通过定义环境变量或用命令行进行授权。

定义环境变量 `MINERU_TOKEN`：

```bash
export MINERU_TOKEN="your-mineru-token"
```

用命令行授权：

```bash
mineru-open-api auth
```

验证 Token 是否有效：

```bash
mineru-open-api auth --verify
```

## 如何使用

用主流 Agent 接入该项目，把论文和专利分别保存在 `source-paper` 和 `source-patent` 目录下，直接在对话界面告诉 Agent 要总结的文章标题，例如：

```
帮我总结 Sridhar et al. - 2020 - Load Driven Branch Predictor (LDBP)
```

Agent 会进行文档提取并精读，最终的总结报告输出在目录 `reading-notes` 下。