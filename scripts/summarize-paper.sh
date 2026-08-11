#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SOURCE_DIR="$ROOT_DIR/source-docs"
PROMPT_FILE="$ROOT_DIR/prompts/paper.md"
OUTPUT_DIR="$ROOT_DIR/reading-notes"
DEFAULT_CODEX_HOME="${CODEX_HOME:-$HOME/.codex}"

usage() {
  cat <<'EOF'
Usage:
  scripts/summarize-paper.sh [PDF_PATH]

Behavior:
  - If PDF_PATH is provided, summarize that PDF.
  - Otherwise, pick the most recently modified PDF under source-docs/.
  - Write the Markdown note to reading-notes/<pdf-basename>.md

Requirements:
  - codex CLI available in PATH
EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

if [[ ! -f "$PROMPT_FILE" ]]; then
  echo "Prompt file not found: $PROMPT_FILE" >&2
  exit 1
fi

if ! command -v codex >/dev/null 2>&1; then
  echo "codex CLI not found in PATH" >&2
  exit 1
fi

pick_latest_pdf() {
  local latest=""
  while IFS= read -r file; do
    latest="$file"
  done < <(find "$SOURCE_DIR" -maxdepth 1 -type f \( -iname '*.pdf' -o -iname '*.PDF' \) -printf '%T@ %p\n' | sort -n | awk '{ $1=""; sub(/^ /, ""); print }')
  printf '%s\n' "$latest"
}

PDF_PATH="${1:-}"
if [[ -z "$PDF_PATH" ]]; then
  PDF_PATH="$(pick_latest_pdf)"
fi

if [[ -z "$PDF_PATH" ]]; then
  echo "No PDF found. Put a PDF into $SOURCE_DIR or pass one explicitly." >&2
  exit 1
fi

if [[ ! -f "$PDF_PATH" ]]; then
  echo "PDF not found: $PDF_PATH" >&2
  exit 1
fi

mkdir -p "$OUTPUT_DIR"

PDF_ABS="$(cd "$(dirname "$PDF_PATH")" && pwd)/$(basename "$PDF_PATH")"
PDF_BASE="$(basename "$PDF_PATH")"
NOTE_NAME="${PDF_BASE%.*}.md"
OUTPUT_FILE="$OUTPUT_DIR/$NOTE_NAME"

PROMPT_TMP="$(mktemp)"
TMP_CODEX_HOME="$(mktemp -d /tmp/codex-home.XXXXXX)"
cleanup() {
  rm -f "$PROMPT_TMP"
  rm -rf "$TMP_CODEX_HOME"
}
trap cleanup EXIT

mkdir -p "$TMP_CODEX_HOME"
for name in auth.json config.toml version.json installation_id; do
  if [[ -f "$DEFAULT_CODEX_HOME/$name" ]]; then
    cp "$DEFAULT_CODEX_HOME/$name" "$TMP_CODEX_HOME/$name"
  fi
done

cat "$PROMPT_FILE" > "$PROMPT_TMP"
cat <<EOF >> "$PROMPT_TMP"

---

请基于仓库中的 PDF 文档 \`$PDF_ABS\` 完成总结。

输出要求：
1. 使用中文。
2. 采用 Markdown 结构化输出。
3. 严格基于原文证据；如果无法确认，明确写出“原文未说明”或“当前材料无法确认”。
4. 不要虚构数据、图表、章节或作者观点。
5. 直接输出最终可保存为笔记的正文，不要添加多余寒暄。
6. 如果需要说明输入来源，请在开头简短写明：当前摘要目标来自 \`source-docs/\` 自动选取或命令行显式指定。
EOF

echo "Summarizing $PDF_BASE ..."
CODEX_HOME="$TMP_CODEX_HOME" codex exec \
  --skip-git-repo-check \
  --sandbox workspace-write \
  --full-auto \
  --ephemeral \
  --output-last-message "$OUTPUT_FILE" \
  -C "$ROOT_DIR" \
  -i "$PDF_ABS" \
  - < "$PROMPT_TMP"

echo "Wrote $OUTPUT_FILE"
