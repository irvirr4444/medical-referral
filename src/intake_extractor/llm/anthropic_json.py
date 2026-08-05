from __future__ import annotations

import json
import os
from typing import Any

from dotenv import load_dotenv


class AnthropicJsonError(RuntimeError):
    pass


def build_client(*, max_retries: int = 0, timeout_s: float | None = 600.0) -> Any:
    """Build a synchronous Anthropic client.

    Application code owns capacity retries. The SDK's hidden retries are disabled
    by default so attempt counts and delays stay deterministic.
    """
    if not os.getenv("ANTHROPIC_API_KEY"):
        load_dotenv()
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise AnthropicJsonError("ANTHROPIC_API_KEY is not set (env or .env)")

    from anthropic import Anthropic

    kwargs: dict[str, Any] = {"api_key": api_key, "max_retries": max_retries}
    if timeout_s is not None:
        kwargs["timeout"] = timeout_s
    return Anthropic(**kwargs)


def message_fix_json(parse_error: str) -> str:
    return (
        "Your previous response was not valid JSON and could not be parsed. "
        f"Parser error: {parse_error}\n"
        "Re-output the same content as a single strict JSON object only."
    )


def parse_json_from_message(message: Any) -> dict[str, Any]:
    content = getattr(message, "content", None)
    if not isinstance(content, list):
        raise AnthropicJsonError("Claude response did not contain a content list")

    text_parts: list[str] = []
    for block in content:
        btype = getattr(block, "type", None) or (block.get("type") if isinstance(block, dict) else None)
        if btype != "text":
            continue
        txt = getattr(block, "text", None) or (block.get("text") if isinstance(block, dict) else None)
        if isinstance(txt, str):
            text_parts.append(txt)

    if not text_parts:
        raise AnthropicJsonError("Claude response had no text blocks")

    raw = "\n".join(text_parts).strip()
    if raw.startswith("```"):
        raw = raw.strip("`")
        raw = raw.replace("json", "", 1).strip()
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise AnthropicJsonError(f"Failed to parse JSON output: {exc}") from None

    if not isinstance(parsed, dict):
        raise AnthropicJsonError("Claude output JSON was not an object")
    return parsed


def call_model_for_json(
    client: Any,
    *,
    model_name: str,
    max_tokens: int,
    system_prompt: str,
    user_content: list[dict[str, Any]],
    lead_text: str,
) -> dict[str, Any]:
    last_parse_error: str | None = None
    for attempt in (1, 2):
        current_lead = lead_text if attempt == 1 else message_fix_json(last_parse_error or "unknown")
        message = client.messages.create(
            model=model_name,
            max_tokens=max_tokens,
            system=system_prompt,
            messages=[{"role": "user", "content": [{"type": "text", "text": current_lead}] + user_content}],
        )
        try:
            return parse_json_from_message(message)
        except AnthropicJsonError as exc:
            last_parse_error = str(exc)
            if attempt == 2:
                raise
    raise AnthropicJsonError("Model failed to return valid JSON")

