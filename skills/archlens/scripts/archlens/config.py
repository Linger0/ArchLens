from __future__ import annotations

import os
import shlex
from dataclasses import dataclass
from pathlib import Path
from typing import Dict


def _parse_env_file(file_path: Path) -> Dict[str, str]:
    if not file_path.exists():
        return {}

    values: Dict[str, str] = {}
    for raw_line in file_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        values[key] = value
    return values


def _find_workspace_root(start: Path) -> Path:
    current = start
    while True:
        candidate = current / "doc" / "CodexStandaloneAgentDesign.md"
        if candidate.exists():
            return current
        if current.parent == current:
            return start
        current = current.parent


def _env_int(env: Dict[str, str], key: str, default: int) -> int:
    try:
        return int(env.get(key, str(default)))
    except ValueError:
        return default


def _env_value(env: Dict[str, str], key: str, default: str, legacy_key: str | None = None) -> str:
    if key in env:
        return env[key]
    if legacy_key and legacy_key in env:
        return env[legacy_key]
    return default


@dataclass(slots=True)
class AgentConfig:
    workspace_root: Path
    skill_root: Path
    artifacts_dir: Path
    state_dir: Path
    source_docs_dir: Path
    reading_notes_dir: Path
    prompt_pack_dir: Path
    codex_home: Path
    default_language: str
    note_title_prefix: str
    reference_mcp_command: str
    reference_mcp_args: list[str]
    mineru_api_url: str
    mineru_api_key: str
    mineru_poll_interval_ms: int
    mineru_timeout_ms: int
    llm_provider: str
    gemini_api_url: str
    gemini_api_key: str
    gemini_model: str
    openai_compat_api_url: str
    openai_compat_api_key: str
    openai_compat_model: str
    image_provider: str
    gemini_image_model: str
    openai_compat_image_model: str
    image_canvas_width: int
    image_canvas_height: int


def load_config(cwd: str | None = None) -> AgentConfig:
    current = Path(cwd or os.getcwd()).resolve()
    workspace_root = _find_workspace_root(current)
    if not (workspace_root / "doc" / "CodexStandaloneAgentDesign.md").exists():
        workspace_root = _find_workspace_root(Path(__file__).resolve())
    skill_root = Path("skills") / "archlens"
    env = {
        **_parse_env_file(workspace_root / ".env"),
        **{key: value for key, value in os.environ.items()},
    }
    codex_home = Path(env.get("CODEX_HOME", str(Path.home() / ".codex"))).expanduser()

    return AgentConfig(
        workspace_root=workspace_root,
        skill_root=skill_root,
        artifacts_dir=Path(_env_value(env, "ARCHLENS_ARTIFACTS_DIR", "artifacts")),
        state_dir=Path(_env_value(env, "ARCHLENS_STATE_DIR", ".agent-state")),
        source_docs_dir=Path(
            _env_value(env, "ARCHLENS_SOURCE_DOCS_DIR", "source-docs")
        ),
        reading_notes_dir=(
            Path(_env_value(env, "ARCHLENS_READING_NOTES_DIR", "reading-notes"))
        ),
        prompt_pack_dir=skill_root / "templates" / "prompt-packs",
        codex_home=codex_home,
        default_language=_env_value(env, "ARCHLENS_LANGUAGE", "中文"),
        note_title_prefix=_env_value(
            env, "ARCHLENS_NOTE_TITLE_PREFIX", "ArchLens"
        ),
        reference_mcp_command=_env_value(
            env, "ARCHLENS_REFERENCE_MCP_COMMAND", ""
        ),
        reference_mcp_args=shlex.split(
            _env_value(env, "ARCHLENS_REFERENCE_MCP_ARGS", "")
        ),
        mineru_api_url=env.get("MINERU_API_URL", "https://mineru.net").rstrip("/"),
        mineru_api_key=env.get("MINERU_API_KEY", ""),
        mineru_poll_interval_ms=_env_int(env, "MINERU_POLL_INTERVAL_MS", 5000),
        mineru_timeout_ms=_env_int(env, "MINERU_TIMEOUT_MS", 300000),
        llm_provider=_env_value(env, "ARCHLENS_PROVIDER", "mock"),
        gemini_api_url=env.get(
            "GEMINI_API_URL", "https://generativelanguage.googleapis.com"
        ).rstrip("/"),
        gemini_api_key=env.get("GEMINI_API_KEY", ""),
        gemini_model=env.get("GEMINI_MODEL", "gemini-2.5-pro"),
        openai_compat_api_url=env.get("OPENAI_COMPAT_API_URL", "").rstrip("/"),
        openai_compat_api_key=env.get("OPENAI_COMPAT_API_KEY", ""),
        openai_compat_model=env.get("OPENAI_COMPAT_MODEL", "gpt-4.1"),
        image_provider=_env_value(env, "ARCHLENS_IMAGE_PROVIDER", "local-svg"),
        gemini_image_model=env.get(
            "GEMINI_IMAGE_MODEL", "gemini-2.0-flash-preview-image-generation"
        ),
        openai_compat_image_model=env.get("OPENAI_COMPAT_IMAGE_MODEL", "gpt-image-1"),
        image_canvas_width=_env_int(env, "IMAGE_CANVAS_WIDTH", 1600),
        image_canvas_height=_env_int(env, "IMAGE_CANVAS_HEIGHT", 900),
    )
