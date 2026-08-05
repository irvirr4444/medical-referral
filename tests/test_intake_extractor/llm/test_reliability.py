from __future__ import annotations

from intake_extractor.llm.reliability import (
    CapacityExhaustedError,
    call_with_model_fallback,
    is_capacity_error,
    is_permanent_api_error,
    resolve_model_chain,
    retry_delay_seconds,
)


class _StatusError(Exception):
    def __init__(self, status_code: int, body=None, message: str = "error") -> None:
        super().__init__(message)
        self.status_code = status_code
        self.body = body


def test_capacity_error_detects_streamed_http_200_overload() -> None:
    error = _StatusError(200, body={"type": "error", "error": {"type": "overloaded_error", "message": "Overloaded"}})
    assert is_capacity_error(error)
    assert not is_permanent_api_error(error)


def test_capacity_error_detects_explicit_529() -> None:
    assert is_capacity_error(_StatusError(529, message="Overloaded"))


def test_permanent_auth_errors_are_not_retried() -> None:
    assert is_permanent_api_error(_StatusError(401, message="unauthorized"))
    assert not is_capacity_error(_StatusError(401, message="unauthorized"))


def test_retry_delay_uses_full_jitter_and_retry_after() -> None:
    class _Headers(dict):
        pass

    class _Response:
        headers = _Headers({"retry-after": "12"})

    error = _StatusError(429, message="rate limited")
    error.response = _Response()
    assert retry_delay_seconds(error, 0, random_source=lambda: 1.0) == 12.0
    assert 0.5 <= retry_delay_seconds(_StatusError(529), 0, base_delay_seconds=30, random_source=lambda: 0.5) <= 30


def test_model_fallback_advances_after_capacity_exhaustion() -> None:
    calls: list[str] = []
    sleeps: list[float] = []

    def call(model: str):
        calls.append(model)
        if model == "claude-opus-5":
            raise _StatusError(529, body={"error": {"type": "overloaded_error", "message": "Overloaded"}})
        return f"ok:{model}"

    result, audit = call_with_model_fallback(
        call,
        models=["claude-opus-5", "claude-opus-4-8"],
        api_attempts=2,
        sleep=sleeps.append,
        random_source=lambda: 0.0,
    )

    assert result == "ok:claude-opus-4-8"
    assert calls == ["claude-opus-5", "claude-opus-5", "claude-opus-4-8"]
    assert audit.fallback_used is True
    assert len(sleeps) == 1


def test_model_fallback_raises_when_all_models_exhausted() -> None:
    def call(_model: str):
        raise _StatusError(529, body={"error": {"type": "overloaded_error", "message": "Overloaded"}})

    try:
        call_with_model_fallback(call, models=["claude-opus-5", "claude-opus-4-8"], api_attempts=1, sleep=lambda _d: None)
        raise AssertionError("expected CapacityExhaustedError")
    except CapacityExhaustedError as error:
        assert error.models_attempted == ["claude-opus-5", "claude-opus-4-8"]


def test_resolve_model_chain_defaults_and_deduplicates(monkeypatch) -> None:
    monkeypatch.delenv("ANTHROPIC_PDF_MODEL", raising=False)
    monkeypatch.delenv("ANTHROPIC_PDF_FALLBACK_MODELS", raising=False)
    assert resolve_model_chain() == ["claude-opus-5", "claude-opus-4-8"]
    assert resolve_model_chain(primary="claude-opus-5", fallbacks=["claude-opus-5", "claude-opus-4-8"]) == [
        "claude-opus-5",
        "claude-opus-4-8",
    ]
