from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
import uuid
from typing import Any

from dotenv import load_dotenv

MONDAY_API_URL = "https://api.monday.com/v2"
MONDAY_FILE_API_URL = "https://api.monday.com/v2/file"
DEFAULT_API_VERSION = "2026-07"
DEFAULT_TIMEOUT_S = 30


class MondayAPIError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        status: int | None = None,
        response: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.status = status
        self.response = response


def _get_api_key(env_var: str = "MONDAY_DOT_COM_API_KEY") -> str:
    if not os.getenv(env_var):
        load_dotenv()
    api_key = os.getenv(env_var)
    if not api_key:
        raise MondayAPIError(
            f"Missing {env_var}. Set it in your environment or in .env.",
        )
    return api_key


def _parse_json_response(raw: str, *, status: int | None = None) -> dict[str, Any]:
    try:
        parsed = json.loads(raw) if raw else {}
    except json.JSONDecodeError as e:
        raise MondayAPIError("Monday API returned non-JSON response.", status=status) from e

    if isinstance(parsed, dict) and parsed.get("errors"):
        raise MondayAPIError(
            "Monday API returned GraphQL errors.",
            status=status,
            response=parsed,
        )
    return parsed


def _urlopen_with_retries(
    req: urllib.request.Request,
    *,
    timeout_s: int,
    max_retries: int = 3,
) -> tuple[int | None, str]:
    last_error: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=timeout_s) as resp:
                status = getattr(resp, "status", None)
                raw = resp.read().decode("utf-8")
                return status, raw
        except urllib.error.HTTPError as e:
            raw = e.read().decode("utf-8") if e.fp is not None else ""
            if e.code in {429, 500, 502, 503, 504} and attempt < max_retries:
                time.sleep(0.5 * (2**attempt))
                last_error = e
                continue
            parsed: dict[str, Any] | None = None
            try:
                parsed = json.loads(raw) if raw else None
            except json.JSONDecodeError:
                parsed = None
            raise MondayAPIError(
                f"Monday API HTTP error: {e.code} {e.reason}",
                status=e.code,
                response=parsed or ({"raw": raw} if raw else None),
            ) from e
        except urllib.error.URLError as e:
            if attempt < max_retries:
                time.sleep(0.5 * (2**attempt))
                last_error = e
                continue
            raise MondayAPIError(f"Monday API connection error: {e.reason}") from e
    raise MondayAPIError(f"Monday API request failed after retries: {last_error}")


def monday_graphql(
    query: str,
    *,
    variables: dict[str, Any] | None = None,
    api_key: str | None = None,
    api_version: str | None = DEFAULT_API_VERSION,
    timeout_s: int = DEFAULT_TIMEOUT_S,
    max_retries: int = 3,
) -> dict[str, Any]:
    api_key = api_key or _get_api_key()
    payload: dict[str, Any] = {"query": query}
    if variables is not None:
        payload["variables"] = variables

    headers = {
        "Authorization": api_key,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    if api_version:
        headers["API-Version"] = api_version

    req = urllib.request.Request(
        MONDAY_API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    status, raw = _urlopen_with_retries(req, timeout_s=timeout_s, max_retries=max_retries)
    return _parse_json_response(raw, status=status)


def _build_multipart(
    *,
    fields: dict[str, str],
    file_field: str,
    filename: str,
    content_type: str,
    file_bytes: bytes,
) -> tuple[bytes, str]:
    boundary = f"----monday-{uuid.uuid4().hex}"
    lines: list[bytes] = []
    for name, value in fields.items():
        lines.append(f"--{boundary}\r\n".encode())
        lines.append(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode())
        lines.append(value.encode("utf-8"))
        lines.append(b"\r\n")

    lines.append(f"--{boundary}\r\n".encode())
    lines.append(
        (
            f'Content-Disposition: form-data; name="{file_field}"; '
            f'filename="{filename}"\r\n'
        ).encode()
    )
    lines.append(f"Content-Type: {content_type}\r\n\r\n".encode())
    lines.append(file_bytes)
    lines.append(b"\r\n")
    lines.append(f"--{boundary}--\r\n".encode())
    return b"".join(lines), boundary


def monday_file_upload(
    *,
    query: str,
    variables: dict[str, Any],
    file_bytes: bytes,
    filename: str,
    content_type: str = "application/octet-stream",
    file_var_name: str = "file",
    api_key: str | None = None,
    api_version: str | None = DEFAULT_API_VERSION,
    timeout_s: int = DEFAULT_TIMEOUT_S,
    max_retries: int = 3,
) -> dict[str, Any]:
    """Upload a file via Monday's multipart `/v2/file` endpoint."""
    api_key = api_key or _get_api_key()
    file_field = "image"
    variables_for_json = dict(variables)
    variables_for_json[file_var_name] = None

    body, boundary = _build_multipart(
        fields={
            "query": query,
            "variables": json.dumps(variables_for_json),
            "map": json.dumps({file_field: f"variables.{file_var_name}"}),
        },
        file_field=file_field,
        filename=filename,
        content_type=content_type,
        file_bytes=file_bytes,
    )
    headers = {
        "Authorization": api_key,
        "Content-Type": f"multipart/form-data; boundary={boundary}",
        "Accept": "application/json",
    }
    if api_version:
        headers["API-Version"] = api_version

    req = urllib.request.Request(
        MONDAY_FILE_API_URL,
        data=body,
        headers=headers,
        method="POST",
    )
    status, raw = _urlopen_with_retries(req, timeout_s=timeout_s, max_retries=max_retries)
    return _parse_json_response(raw, status=status)
