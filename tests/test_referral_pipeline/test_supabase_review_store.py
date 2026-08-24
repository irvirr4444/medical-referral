from __future__ import annotations

import hashlib

from referral_pipeline.review.supabase_store import SupabaseReviewStore


class Response:
    def __init__(self, payload, *, status_code: int = 200):
        self.payload = payload
        self.status_code = status_code
        self.ok = status_code < 400
        self.text = str(payload)

    def json(self):
        return self.payload


class Session:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def _call(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        return self.responses.pop(0)

    def get(self, url, **kwargs):
        return self._call("GET", url, **kwargs)

    def post(self, url, **kwargs):
        return self._call("POST", url, **kwargs)

    def patch(self, url, **kwargs):
        return self._call("PATCH", url, **kwargs)


def _row(**overrides):
    row = {
        "review_id": "review-1",
        "recipient": "sender@example.test",
        "status": "awaiting_confirmation",
        "artifact_digest": "a" * 64,
        "source_message_id": "source-1",
        "source_conversation_id": "conversation-1",
        "created_at": "2026-08-06T10:00:00+00:00",
        "canonical_referral": {"patient": {"name": "Jane"}},
        "intake_plan": {"outcome": "ready"},
        "monday_preview": {"blocked": False},
        "drk_draft": {"payload": {}},
    }
    row.update(overrides)
    return row


def test_add_persists_correlated_json_snapshots() -> None:
    session = Session([Response([_row()])])
    store = SupabaseReviewStore(
        url="https://project.supabase.co",
        service_key="secret",
        session=session,
    )

    review = store.add(
        review_id="review-1",
        token="unused",
        recipient="Sender@Example.test",
        artifact_digest="a" * 64,
        canonical_path="canonical.json",
        intake_plan_path="plan.json",
        monday_preview_path="monday.json",
        drk_draft_path="drk.json",
        source_message_id="source-1",
        source_conversation_id="conversation-1",
        source_attachment_sha256="b" * 64,
        canonical_referral={"patient": {"name": "Jane"}},
        intake_plan={"outcome": "ready"},
        monday_preview={"blocked": False},
        drk_draft={"payload": {}},
    )

    payload = session.calls[0][2]["json"]
    assert payload["recipient"] == "sender@example.test"
    assert payload["source_conversation_id"] == "conversation-1"
    assert payload["review_purpose"] == "destination_write"
    assert payload["canonical_referral"]["patient"]["name"] == "Jane"
    assert review.monday_preview == {"blocked": False}


def test_partner_contact_review_persists_scope_and_workflow_case() -> None:
    session = Session(
        [Response([_row(review_purpose="partner_contact", workflow_case_id="case-123")])]
    )
    store = SupabaseReviewStore(
        url="https://project.supabase.co",
        service_key="secret",
        session=session,
    )

    review = store.add(
        review_id="review-1",
        token="unused",
        recipient="reviewer@example.test",
        artifact_digest="a" * 64,
        canonical_path="canonical.json",
        intake_plan_path="plan.json",
        monday_preview_path="monday.json",
        drk_draft_path="drk.json",
        source_message_id="source-1",
        source_conversation_id="conversation-1",
        canonical_referral={},
        intake_plan={},
        monday_preview={},
        drk_draft={},
        purpose="partner_contact",
        workflow_case_id="case-123",
    )

    payload = session.calls[0][2]["json"]
    assert payload["review_purpose"] == "partner_contact"
    assert payload["workflow_case_id"] == "case-123"
    assert review.purpose == "partner_contact"
    assert review.workflow_case_id == "case-123"


def test_response_ledger_hashes_body_and_never_stores_raw_text() -> None:
    session = Session([Response([{"id": "response-1"}])])
    store = SupabaseReviewStore(
        url="https://project.supabase.co",
        service_key="secret",
        session=session,
    )

    assert store.record_response(
        review_id="review-1",
        message_id="reply-1",
        sender="Sender@Example.test",
        conversation_id="conversation-1",
        received_at="2026-08-06T10:01:00+00:00",
        text="Please confirm this referral",
        intent="confirm",
        classifier_source="local",
        classifier_reason="exact confirmation",
    )

    payload = session.calls[0][2]["json"]
    assert "text" not in payload
    assert payload["body_sha256"] == hashlib.sha256(
        b"Please confirm this referral"
    ).hexdigest()


def test_confirmation_uses_conditional_sender_and_thread_update() -> None:
    session = Session([Response([_row(status="confirmed")])])
    store = SupabaseReviewStore(
        url="https://project.supabase.co",
        service_key="secret",
        session=session,
    )

    assert store.confirm_by_context(
        review_id="review-1",
        sender="Sender@Example.test",
        conversation_id="conversation-1",
        message_id="reply-1",
    )

    params = session.calls[0][2]["params"]
    assert params["status"] == "eq.awaiting_confirmation"
    assert params["recipient"] == "eq.sender@example.test"
    assert params["source_conversation_id"] == "eq.conversation-1"


def test_response_processing_uses_atomic_rpc() -> None:
    session = Session([Response("confirmed")])
    store = SupabaseReviewStore(
        url="https://project.supabase.co",
        service_key="secret",
        session=session,
    )

    result = store.process_response(
        review_id="review-1",
        message_id="reply-1",
        sender="sender@example.test",
        conversation_id="conversation-1",
        received_at="2026-08-06T10:01:00+00:00",
        text="Confirm",
        intent="confirm",
        classifier_source="local",
        classifier_reason="exact confirmation",
    )

    assert result == "confirmed"
    method, url, call = session.calls[0]
    assert method == "POST"
    assert url.endswith("/rest/v1/rpc/process_review_response")
    assert call["json"]["p_body_sha256"] == hashlib.sha256(b"Confirm").hexdigest()


def test_dry_run_audit_is_persisted_without_destination_state() -> None:
    session = Session([Response([_row(status="dry_run_completed")])])
    store = SupabaseReviewStore(
        url="https://project.supabase.co",
        service_key="secret",
        session=session,
    )
    result = {"status": "dry_run_completed", "writes_performed": False}

    store.record_dry_run("review-1", result=result)

    method, _, call = session.calls[0]
    assert method == "PATCH"
    assert call["params"]["status"] == "in.(confirmed,dry_run_completed)"
    assert call["json"]["last_dry_run_result"] == result
    assert call["json"]["drk_status"] == "pending_draft"
    assert "monday_item_id" not in call["json"]


def test_monday_execution_claim_uses_atomic_rpc() -> None:
    session = Session([Response("claimed")])
    store = SupabaseReviewStore(
        url="https://project.supabase.co",
        service_key="secret",
        session=session,
    )

    assert store.claim_for_monday_execution("review-1") == "claimed"

    method, url, call = session.calls[0]
    assert method == "POST"
    assert url.endswith("/rest/v1/rpc/claim_review_for_monday_execution")
    assert call["json"] == {"p_review_id": "review-1"}

