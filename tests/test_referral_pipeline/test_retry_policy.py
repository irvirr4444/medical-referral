from __future__ import annotations

from Outlook.graph import OutlookGraphError
from referral_pipeline.retry_policy import classify_retry


class MondayAPIError(RuntimeError):
    def __init__(self, *, status=None, response=None):
        super().__init__("Monday API failed")
        self.status = status
        self.response = response


def test_outlook_service_failure_is_retryable() -> None:
    decision = classify_retry(OutlookGraphError("temporary", status_code=503))

    assert decision is not None
    assert decision.error_kind == "outlook_transient"


def test_outlook_permission_failure_is_terminal() -> None:
    assert classify_retry(OutlookGraphError("forbidden", status_code=403)) is None


def test_monday_rate_limit_is_retryable() -> None:
    decision = classify_retry(MondayAPIError(status=429))

    assert decision is not None
    assert decision.error_kind == "monday_transient"


def test_monday_complexity_error_is_retryable() -> None:
    decision = classify_retry(
        MondayAPIError(response={"errors": [{"message": "Complexity budget exhausted"}]})
    )

    assert decision is not None
    assert decision.error_kind == "monday_transient"


def test_validation_error_is_terminal() -> None:
    assert classify_retry(ValueError("patient date is malformed")) is None
