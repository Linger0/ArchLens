from __future__ import annotations

from pathlib import Path
from typing import Any

from .models import validate_prompt_pack
from .store import ensure_dir, read_json, write_json


class PromptPackManager:
    def __init__(self, prompt_pack_dir: Path, state_dir: Path, default_language: str) -> None:
        self.prompt_pack_dir = prompt_pack_dir
        self.state_dir = state_dir
        self.default_language = default_language
        self.defaults_path = state_dir / "prompt-defaults.json"
        ensure_dir(state_dir)

    def list(self) -> list[dict[str, Any]]:
        packs: list[dict[str, Any]] = []
        for path in sorted(self.prompt_pack_dir.glob("*.json")):
            packs.append(validate_prompt_pack(read_json(path)))
        return packs

    def show(self, pack_id: str) -> dict[str, Any]:
        for pack in self.list():
            if pack["id"] == pack_id:
                return pack
        raise ValueError(f"Unknown prompt pack: {pack_id}")

    def set_default(self, target: str, pack_id: str) -> None:
        pack = self.show(pack_id)
        if pack["target"] != target:
            raise ValueError(f"Prompt pack {pack_id} targets {pack['target']}, not {target}")
        defaults = self._read_defaults()
        defaults[target] = pack_id
        write_json(self.defaults_path, {"defaults": defaults})

    def resolve(self, target: str, explicit_pack_id: str | None = None, user_overlay: str | None = None) -> dict[str, Any]:
        defaults = self._read_defaults()
        pack_id = explicit_pack_id or defaults.get(target)
        pack = self.show(pack_id) if pack_id else next(
            (candidate for candidate in self.list() if candidate["target"] == target),
            None,
        )
        if not pack:
            raise ValueError(f"No prompt pack found for target {target}")
        resolved = dict(pack)
        resolved["language"] = resolved.get("language") or self.default_language
        if user_overlay:
            resolved["userOverlay"] = user_overlay
        return resolved

    def _read_defaults(self) -> dict[str, str]:
        if not self.defaults_path.exists():
            return {}
        payload = read_json(self.defaults_path)
        defaults = payload.get("defaults", {})
        if not isinstance(defaults, dict):
            return {}
        return {str(key): str(value) for key, value in defaults.items()}
