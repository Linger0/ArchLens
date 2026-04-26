from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any


def _encode(payload: dict[str, Any]) -> bytes:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    header = f"Content-Length: {len(body)}\r\n\r\n".encode("utf-8")
    return header + body


class McpClient:
    def __init__(self, command: str, args: list[str], cwd: Path) -> None:
        self.command = command
        self.args = args
        self.cwd = cwd
        self.process: subprocess.Popen[bytes] | None = None
        self.next_id = 1

    def connect(self) -> None:
        if self.process is not None:
            return
        self.process = subprocess.Popen(
            [self.command, *self.args],
            cwd=str(self.cwd),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        self.request(
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "archlens", "version": "0.1.0"},
            },
        )
        self.notify("notifications/initialized", {})

    def close(self) -> None:
        if self.process is not None:
            self.process.kill()
            self.process = None

    def list_tools(self) -> list[dict[str, Any]]:
        result = self.request("tools/list", {})
        tools = result.get("tools", [])
        return tools if isinstance(tools, list) else []

    def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        result = self.request("tools/call", {"name": name, "arguments": arguments})
        return self._extract_tool_payload(result)

    def request(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        if self.process is None or self.process.stdin is None or self.process.stdout is None:
            raise RuntimeError("MCP process is not connected")
        request_id = self.next_id
        self.next_id += 1
        payload = {"jsonrpc": "2.0", "id": request_id, "method": method, "params": params}
        self.process.stdin.write(_encode(payload))
        self.process.stdin.flush()
        response = self._read_message()
        if response.get("id") != request_id:
            raise RuntimeError(f"Unexpected MCP response id: {response.get('id')}")
        if "error" in response:
            raise RuntimeError(response["error"].get("message", "Unknown MCP error"))
        return response.get("result", {})

    def notify(self, method: str, params: dict[str, Any]) -> None:
        if self.process is None or self.process.stdin is None:
            raise RuntimeError("MCP process is not connected")
        payload = {"jsonrpc": "2.0", "method": method, "params": params}
        self.process.stdin.write(_encode(payload))
        self.process.stdin.flush()

    def _read_message(self) -> dict[str, Any]:
        assert self.process is not None and self.process.stdout is not None
        header = b""
        while b"\r\n\r\n" not in header:
            chunk = self.process.stdout.read(1)
            if not chunk:
                stderr = b""
                if self.process.stderr:
                    stderr = self.process.stderr.read() or b""
                raise RuntimeError(
                    f"MCP process closed unexpectedly. stderr={stderr.decode('utf-8', errors='ignore')}"
                )
            header += chunk
        header_text, remainder = header.split(b"\r\n\r\n", 1)
        content_length = None
        for line in header_text.decode("utf-8").split("\r\n"):
            if line.lower().startswith("content-length:"):
                content_length = int(line.split(":", 1)[1].strip())
                break
        if content_length is None:
            raise RuntimeError("Missing Content-Length in MCP response")
        body = remainder
        while len(body) < content_length:
            chunk = self.process.stdout.read(content_length - len(body))
            if not chunk:
                raise RuntimeError("Incomplete MCP message body")
            body += chunk
        return json.loads(body[:content_length].decode("utf-8"))

    @staticmethod
    def _extract_tool_payload(result: Any) -> Any:
        if isinstance(result, dict) and "structuredContent" in result:
            return result["structuredContent"]
        if isinstance(result, dict) and isinstance(result.get("content"), list):
            blocks = result["content"]
            texts = [
                block.get("text", "")
                for block in blocks
                if isinstance(block, dict) and isinstance(block.get("text"), str)
            ]
            combined = "\n".join(texts).strip()
            if not combined:
                return blocks
            try:
                return json.loads(combined)
            except json.JSONDecodeError:
                return combined
        return result
