from __future__ import annotations

import io
import json
import urllib.error
from typing import Any
from unittest.mock import patch

import pytest

from referral_pipeline.integrations.monday import transport


pytestmark = pytest.mark.unit


class _FakeHTTPResponse:
    def __init__(self, body: str, *, status: int = 200) -> None:
        self._body = body.encode("utf-8")
        self.status = status

    def read(self) -> bytes:
        return self._body

    def __enter__(self) -> "_FakeHTTPResponse":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


def test_monday_graphql_success_sets_headers_and_parses_json() -> None:
    captured: dict[str, Any] = {}

    def fake_urlopen(req, timeout: int):  # type: ignore[no-untyped-def]
        captured["url"] = req.full_url
        captured["headers"] = {k.lower(): v for k, v in req.header_items()}
        captured["timeout"] = timeout
        payload = {"data": {"me": {"id": "1"}}}
        return _FakeHTTPResponse(json.dumps(payload), status=200)

    with patch("referral_pipeline.integrations.monday.transport._get_api_key", return_value="KEY"), patch(
        "urllib.request.urlopen",
        side_effect=fake_urlopen,
    ):
        resp = transport.monday_graphql(
            "{ me { id } }",
            variables={"x": 1},
            api_version="2023-10",
            timeout_s=7,
        )

    assert resp["data"]["me"]["id"] == "1"
    assert captured["url"] == transport.MONDAY_API_URL
    assert captured["timeout"] == 7
    assert captured["headers"]["authorization"] == "KEY"
    assert captured["headers"]["content-type"] == "application/json"
    assert captured["headers"]["accept"] == "application/json"
    assert captured["headers"]["api-version"] == "2023-10"


def test_monday_graphql_graphql_errors_raise() -> None:
    def fake_urlopen(req, timeout: int):  # type: ignore[no-untyped-def]
        payload = {"errors": [{"message": "nope"}]}
        return _FakeHTTPResponse(json.dumps(payload), status=200)

    with patch("referral_pipeline.integrations.monday.transport._get_api_key", return_value="KEY"), patch(
        "urllib.request.urlopen",
        side_effect=fake_urlopen,
    ):
        with pytest.raises(transport.MondayAPIError) as e:
            transport.monday_graphql("{ me { id } }")

    assert "GraphQL errors" in str(e.value)
    assert isinstance(e.value.response, dict)
    assert e.value.response.get("errors")


def test_monday_graphql_http_error_parses_json_body() -> None:
    def fake_urlopen(req, timeout: int):  # type: ignore[no-untyped-def]
        body = json.dumps({"error": "bad"})
        fp = io.BytesIO(body.encode("utf-8"))
        raise urllib.error.HTTPError(
            url=req.full_url,
            code=401,
            msg="Unauthorized",
            hdrs=None,
            fp=fp,
        )

    with patch("referral_pipeline.integrations.monday.transport._get_api_key", return_value="KEY"), patch(
        "urllib.request.urlopen",
        side_effect=fake_urlopen,
    ):
        with pytest.raises(transport.MondayAPIError) as e:
            transport.monday_graphql("{ me { id } }")

    assert e.value.status == 401
    assert isinstance(e.value.response, dict)
    assert e.value.response.get("error") == "bad"


def test_monday_file_upload_builds_multipart_and_posts_to_file_endpoint() -> None:
    captured: dict[str, Any] = {}

    def fake_urlopen(req, timeout: int):  # type: ignore[no-untyped-def]
        captured["url"] = req.full_url
        captured["headers"] = {k.lower(): v for k, v in req.header_items()}
        captured["body"] = req.data
        captured["timeout"] = timeout
        payload = {"data": {"add_file_to_update": {"id": "asset-1"}}}
        return _FakeHTTPResponse(json.dumps(payload), status=200)

    with patch("referral_pipeline.integrations.monday.transport._get_api_key", return_value="KEY"), patch(
        "urllib.request.urlopen",
        side_effect=fake_urlopen,
    ):
        resp = transport.monday_file_upload(
            query=(
                "mutation ($file: File!, $updateId: ID!) {"
                " add_file_to_update(update_id: $updateId, file: $file) { id } }"
            ),
            variables={"updateId": "99"},
            file_bytes=b"hello",
            filename="hello.txt",
            content_type="text/plain",
        )

    assert resp["data"]["add_file_to_update"]["id"] == "asset-1"
    assert captured["url"] == transport.MONDAY_FILE_API_URL
    assert captured["headers"]["authorization"] == "KEY"
    assert "multipart/form-data" in captured["headers"]["content-type"]
    body = captured["body"]
    assert isinstance(body, (bytes, bytearray))
    assert b"hello.txt" in body
    assert b"add_file_to_update" in body
    assert b'"updateId": "99"' in body or b'"updateId":"99"' in body
