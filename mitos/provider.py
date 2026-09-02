"""Day 1: translate neutral Mitos messages into provider wire messages.

The boundary keeps credentials out of source control, preserves opaque Gemini thought
signatures, normalizes responses, and retries only transient failures.
"""

from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Any
from urllib import error, parse, request

API_ROOT = "https://generativelanguage.googleapis.com/v1beta/models"
DEFAULT_MODEL = "gemini-3.1-pro-preview"

_ROOT = Path(r"C:\Users\saini\Downloads\HarnessEngineering")
_KEY_FILES = (_ROOT / "mitos.key.sh", _ROOT / "mitos-key.sh")
_KEY_PATTERN = re.compile(r"^\s*(?:export\s+)?MITOS_API_KEY\s*=\s*(.*?)\s*$")
_RETRYABLE = {429, 500, 502, 503}


def api_key() -> str:
    """Return a Mitos/Gemini key from the environment or local key script.

    Scripts are parsed, never executed; both workshop filenames are accepted.
    """
    for name in ("MITOS_API_KEY", "GEMINI_API_KEY"):
        if value := os.environ.get(name, "").strip():
            return value
    for path in _KEY_FILES:
        if not path.is_file():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            if match := _KEY_PATTERN.match(line):
                value = match.group(1).strip().strip("'\"")
                if value:
                    return value
    raise RuntimeError("set MITOS_API_KEY, GEMINI_API_KEY, or MITOS_API_KEY in mitos.key.sh")


def _to_wire(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    contents: list[dict[str, Any]] = []
    for message in messages:
        role = message["role"]
        if role == "user":
            contents.append({"role": "user", "parts": [{"text": message["text"]}]})
        elif role == "assistant":
            parts: list[dict[str, Any]] = []
            if message.get("text"):
                parts.append({"text": message["text"]})
            for call in message.get("tool_calls", []):
                part = {"functionCall": {"name": call["name"], "args": call["args"]}}
                # Gemini 3 requires the opaque signature to survive every round trip.
                if call.get("signature") is not None:
                    part["thoughtSignature"] = call["signature"]
                parts.append(part)
            contents.append({"role": "model", "parts": parts})
        elif role == "tool":
            response = {"name": message["name"], "response": {"result": message["text"]}}
            contents.append({"role": "user", "parts": [{"functionResponse": response}]})
        else:
            raise ValueError(f"unknown message role {role!r}")
    return contents


def complete(model: str, system: str, messages: list[dict[str, Any]],
             tools: list[dict[str, Any]]) -> dict[str, Any]:
    """Request one completion and return the provider-neutral response contract."""
    body: dict[str, Any] = {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": _to_wire(messages),
        "generationConfig": {"temperature": 0.4, "maxOutputTokens": 65536},
    }
    if tools:
        body["tools"] = [{"functionDeclarations": [tool["schema"] for tool in tools]}]
    quoted_model = parse.quote(model, safe="")
    url = f"{API_ROOT}/{quoted_model}:generateContent?key={parse.quote(api_key())}"
    payload = _post(url, body)
    parts = payload.get("candidates", [{}])[0].get("content", {}).get("parts", [])
    text_parts: list[str] = []
    tool_calls: list[dict[str, Any]] = []
    for part in parts:
        if part.get("thought"):
            continue
        if "text" in part:
            text_parts.append(part["text"])
        if call := part.get("functionCall"):
            tool_calls.append({"name": call["name"], "args": call.get("args", {}),
                               "signature": part.get("thoughtSignature")})
    usage = payload.get("usageMetadata", {})
    return {"text": "".join(text_parts), "tool_calls": tool_calls,
            "usage": {"input": int(usage.get("promptTokenCount", 0)),
                      "output": int(usage.get("candidatesTokenCount", 0))}}


def _post(url: str, body: dict[str, Any], retries: int = 5) -> dict[str, Any]:
    data = json.dumps(body).encode("utf-8")
    for attempt in range(retries):
        req = request.Request(url, data=data, headers={"Content-Type": "application/json"})
        try:
            with request.urlopen(req, timeout=600) as response:
                return json.loads(response.read().decode("utf-8"))
        except error.HTTPError as exc:
            details = exc.read().decode("utf-8", errors="replace")[:400]
            if exc.code not in _RETRYABLE or attempt == retries - 1:
                raise RuntimeError(f"HTTP {exc.code}: {details}") from exc
        except (error.URLError, TimeoutError) as exc:
            if attempt == retries - 1:
                raise RuntimeError(f"request failed after {retries} attempts: {exc}") from exc
        time.sleep((2**attempt) * 2)
    raise AssertionError("retry loop exited unexpectedly")
