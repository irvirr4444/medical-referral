"""Deterministic Anthropic capacity retries, fallback models, and error classification."""

from __future__ import annotations

import json
import os
import random
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Sequence


DEFAULT_PRIMARY_MODEL = "claude-opus-5"
DEFAULT_FALLBACK_MODELS = ("claude-opus-4-8",)
DEFAULT_API_ATTEMPTS = 3
DEFAULT_BASE_DELAY_SECONDS = 30.0
DEFAULT_MAX_DELAY_SECONDS = 120.0


class CapacityExhaustedError(RuntimeError):
    """Raised when every model in the ordered chain exhausted capacity retries."""

    def __init__(self, message: str, *, models_attempted: Sequence[str], last_error: Exception | None = None) -> None:
        super().__init__(message)
        self.models_attempted = list(models_attempted)
        self.last_error = last_error


@dataclass(frozen=True)
class ModelCallAudit:
    model: str
    attempts: int
    fallback_used: bool


@dataclass
class ExtractionAudit:
    models_attempted: list[str] = field(default_factory=list)
    pass_models: list[str] = field(default_factory=list)
    fallback_used: bool = False

    def record_pass(self, model: str, *, primary_model: str) -> None:
        if model not in self.models_attempted:
            self.models_attempted.append(model)
        self.pass_models.append(model)
        if model != primary_model:
            self.fallback_used = True


def resolve_model_chain(*, primary: str | None = None, fallbacks: Sequence[str] | None = None) -> list[str]:
    selected_primary = (primary or os.getenv("ANTHROPIC_PDF_MODEL") or DEFAULT_PRIMARY_MODEL).strip()
    if fallbacks is None:
        raw = os.getenv("ANTHROPIC_PDF_FALLBACK_MODELS", ",".join(DEFAULT_FALLBACK_MODELS))
        fallback_values = [item.strip() for item in raw.split(",") if item.strip()]
    else:
        fallback_values = [item.strip() for item in fallbacks if item and item.strip()]
    chain: list[str] = []
    for model in (selected_primary, *fallback_values):
        if model and model not in chain:
            chain.append(model)
    if not chain:
        raise ValueError("At least one Anthropic model must be configured")
    return chain


def is_capacity_error(exc: Exception) -> bool:
    """Return whether an exception is a transient Anthropic capacity/overload failure."""
    status = getattr(exc, "status_code", None)
    if status in {429, 500, 502, 503, 504, 529}:
        return True
    if type(exc).__name__ in {"APIConnectionError", "APITimeoutError", "RateLimitError", "InternalServerError"}:
        return True
    body = _error_body(exc)
    if isinstance(body, dict):
        nested = body.get("error") if isinstance(body.get("error"), dict) else body
        error_type = str(nested.get("type") or "").lower()
        if error_type in {"overloaded_error", "rate_limit_error", "api_error"}:
            return True
        if "overloaded" in str(nested.get("message") or "").lower():
            return True
    message = str(exc).lower()
    return any(token in message for token in ("overloaded", "rate_limit", "temporarily unavailable"))


def is_permanent_api_error(exc: Exception) -> bool:
    status = getattr(exc, "status_code", None)
    if status in {400, 401, 403, 404, 413, 422}:
        return True
    if type(exc).__name__ in {"AuthenticationError", "PermissionDeniedError", "BadRequestError", "NotFoundError"}:
        return True
    return False


def retry_delay_seconds(
    exc: Exception,
    attempt: int,
    *,
    base_delay_seconds: float = DEFAULT_BASE_DELAY_SECONDS,
    max_delay_seconds: float = DEFAULT_MAX_DELAY_SECONDS,
    random_source: Callable[[], float] | None = None,
) -> float:
    """Full-jitter exponential backoff, capped and optional Retry-After honor."""
    response = getattr(exc, "response", None)
    headers = getattr(response, "headers", None)
    if headers is not None:
        retry_after = headers.get("retry-after")
        if retry_after:
            try:
                return min(max(float(retry_after), 0.5), max_delay_seconds)
            except ValueError:
                pass
    expo = min(base_delay_seconds * (2**attempt), max_delay_seconds)
    jitter = (random_source or random.random)()
    return max(0.5, expo * jitter)


def call_with_model_fallback(
    call: Callable[[str], Any],
    *,
    models: Sequence[str],
    api_attempts: int = DEFAULT_API_ATTEMPTS,
    sleep: Callable[[float], None] = time.sleep,
    random_source: Callable[[], float] | None = None,
    base_delay_seconds: float = DEFAULT_BASE_DELAY_SECONDS,
    max_delay_seconds: float = DEFAULT_MAX_DELAY_SECONDS,
    progress: Callable[[str], None] | None = None,
) -> tuple[Any, ModelCallAudit]:
    """Retry capacity errors per model, then advance through the fallback chain."""
    if not models:
        raise ValueError("models cannot be empty")
    if api_attempts < 1:
        raise ValueError("api_attempts must be at least 1")

    last_error: Exception | None = None
    attempted: list[str] = []
    primary = models[0]
    for model_index, model in enumerate(models):
        attempted.append(model)
        for attempt in range(api_attempts):
            try:
                if progress and (attempt or model_index):
                    progress(f"Anthropic retry model={model} attempt={attempt + 1}/{api_attempts}")
                result = call(model)
                return result, ModelCallAudit(
                    model=model,
                    attempts=attempt + 1,
                    fallback_used=model != primary,
                )
            except Exception as exc:
                last_error = exc
                if is_permanent_api_error(exc) or not is_capacity_error(exc):
                    raise
                is_last_attempt = attempt == api_attempts - 1
                is_last_model = model_index == len(models) - 1
                if is_last_attempt and is_last_model:
                    break
                if is_last_attempt:
                    if progress:
                        progress(f"Anthropic capacity exhausted for {model}; trying next fallback")
                    break
                delay = retry_delay_seconds(
                    exc,
                    attempt,
                    base_delay_seconds=base_delay_seconds,
                    max_delay_seconds=max_delay_seconds,
                    random_source=random_source,
                )
                if progress:
                    progress(f"Anthropic capacity error; sleeping {delay:.1f}s before retry")
                sleep(delay)

    raise CapacityExhaustedError(
        f"Anthropic capacity exhausted for models: {', '.join(attempted)}",
        models_attempted=attempted,
        last_error=last_error,
    ) from last_error


def _error_body(exc: Exception) -> Any:
    body = getattr(exc, "body", None)
    if isinstance(body, (dict, list)):
        return body
    if isinstance(body, str):
        try:
            return json.loads(body)
        except json.JSONDecodeError:
            return {"message": body}
    response = getattr(exc, "response", None)
    text = getattr(response, "text", None)
    if isinstance(text, str) and text.strip():
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {"message": text}
    return None
