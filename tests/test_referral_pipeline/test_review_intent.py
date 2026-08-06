from __future__ import annotations

from referral_pipeline.review.intent import classify_reply_intent


def test_obvious_human_confirmation_is_classified_locally(monkeypatch) -> None:
    monkeypatch.setattr(
        "referral_pipeline.review.intent.requests.post",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("OpenAI should not be called")),
    )

    result = classify_reply_intent("Confirm")

    assert result.intent == "confirm"
    assert result.source == "local"


def test_correction_is_not_treated_as_confirmation(monkeypatch) -> None:
    monkeypatch.setattr(
        "referral_pipeline.review.intent.requests.post",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("OpenAI should not be called")),
    )

    result = classify_reply_intent("Please correct the phone number")

    assert result.intent == "correction"


def test_ambiguous_natural_language_uses_openai(monkeypatch) -> None:
    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "choices": [
                    {
                        "message": {
                            "content": '{"intent":"confirm","reason":"Clearly asks the workflow to proceed."}'
                        }
                    }
                ]
            }

    captured = {}
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(
        "referral_pipeline.review.intent.requests.post",
        lambda url, **kwargs: captured.update({"url": url, **kwargs}) or Response(),
    )

    result = classify_reply_intent("Everything is accurate; please move forward with both systems.")

    assert result.intent == "confirm"
    assert result.source == "openai"
    assert captured["headers"]["Authorization"] == "Bearer test-key"
    assert captured["json"]["response_format"]["type"] == "json_schema"


def test_openai_failure_fails_closed(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(
        "referral_pipeline.review.intent.requests.post",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(ValueError("bad response")),
    )

    result = classify_reply_intent("Maybe you can proceed")

    assert result.intent == "unclear"
