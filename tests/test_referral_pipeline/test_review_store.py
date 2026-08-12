from referral_pipeline.review.store import ReviewStore


def _add(store: ReviewStore) -> None:
    store.add(
        review_id="review_abc123_xyz987",
        token="abcdefghijklmnop",
        recipient="reviewer@example.test",
        artifact_digest="digest",
        canonical_path="canonical.json",
        intake_plan_path="plan.json",
        monday_preview_path="monday.json",
        drk_draft_path="drk.json",
        source_message_id="source-message",
        source_conversation_id="conversation-1",
    )


def test_confirmation_is_sender_bound_and_one_time(tmp_path) -> None:
    store = ReviewStore(tmp_path / "state.sqlite")
    _add(store)

    assert not store.confirm(
        review_id="review_abc123_xyz987",
        token="abcdefghijklmnop",
        sender="attacker@example.test",
        message_id="message-1",
    )
    assert store.confirm(
        review_id="review_abc123_xyz987",
        token="abcdefghijklmnop",
        sender="REVIEWER@example.test",
        message_id="message-2",
    )
    assert not store.confirm(
        review_id="review_abc123_xyz987",
        token="abcdefghijklmnop",
        sender="reviewer@example.test",
        message_id="message-3",
    )


def test_wrong_token_is_rejected(tmp_path) -> None:
    store = ReviewStore(tmp_path / "state.sqlite")
    _add(store)

    assert not store.confirm(
        review_id="review_abc123_xyz987",
        token="wrongwrongwrongwrong",
        sender="reviewer@example.test",
        message_id="message-1",
    )


def test_human_confirmation_is_bound_to_sender_thread_and_one_time(tmp_path) -> None:
    store = ReviewStore(tmp_path / "state.sqlite")
    _add(store)

    assert store.find_confirmable_for_reply(
        sender="attacker@example.test",
        conversation_id="conversation-1",
    ) is None
    assert store.find_confirmable_for_reply(
        sender="reviewer@example.test",
        conversation_id="wrong-thread",
    ) is None
    found = store.find_confirmable_for_reply(
        sender="REVIEWER@example.test",
        conversation_id="conversation-1",
    )
    assert found is not None
    assert store.confirm_by_context(
        review_id=found.review_id,
        sender="reviewer@example.test",
        conversation_id="conversation-1",
        message_id="reply-1",
    )
    assert not store.confirm_by_context(
        review_id=found.review_id,
        sender="reviewer@example.test",
        conversation_id="conversation-1",
        message_id="reply-2",
    )


def test_response_processing_atomically_records_correction_and_duplicate(tmp_path) -> None:
    store = ReviewStore(tmp_path / "state.sqlite")
    _add(store)

    result = store.process_response(
        review_id="review_abc123_xyz987",
        message_id="reply-correction",
        sender="reviewer@example.test",
        conversation_id="conversation-1",
        received_at="2026-08-06T10:00:00+00:00",
        text="Do not confirm; the phone number needs correction.",
        intent="correction",
        classifier_source="local",
        classifier_reason="explicit correction",
    )

    assert result == "needs_correction"
    assert store.get("review_abc123_xyz987").status == "needs_correction"
    assert store.response_exists("reply-correction")
    assert store.process_response(
        review_id="review_abc123_xyz987",
        message_id="reply-correction",
        sender="reviewer@example.test",
        conversation_id="conversation-1",
        received_at="2026-08-06T10:00:00+00:00",
        text="Do not confirm; the phone number needs correction.",
        intent="correction",
        classifier_source="local",
        classifier_reason="explicit correction",
    ) == "duplicate"


def test_partner_contact_confirmation_cannot_enter_destination_write_queue(tmp_path) -> None:
    store = ReviewStore(tmp_path / "state.sqlite")
    store.add(
        review_id="review_partner_contact",
        token="internal-token",
        recipient="reviewer@example.test",
        artifact_digest="digest",
        canonical_path="canonical.json",
        intake_plan_path="plan.json",
        monday_preview_path="monday.json",
        drk_draft_path="drk.json",
        source_message_id="source-message",
        source_conversation_id="conversation-1",
        purpose="partner_contact",
        workflow_case_id="case-123",
    )

    result = store.process_response(
        review_id="review_partner_contact",
        message_id="reply-contacted",
        sender="reviewer@example.test",
        conversation_id="conversation-1",
        received_at="2026-08-12T10:00:00+00:00",
        text="Confirm",
        intent="confirm",
        classifier_source="local",
        classifier_reason="exact confirmation",
    )

    review = store.get("review_partner_contact")
    assert result == "partner_contact_confirmed"
    assert review.status == "partner_contact_confirmed"
    assert review.purpose == "partner_contact"
    assert review.workflow_case_id == "case-123"
    assert store.confirmed() == []
    assert store.claim_for_monday_execution("review_partner_contact") == "wrong_purpose"


def test_find_active_returns_reusable_review(tmp_path) -> None:
    store = ReviewStore(tmp_path / "state.sqlite")
    store.add(
        review_id="review_abc123_xyz987",
        token="abcdefghijklmnop",
        recipient="reviewer@example.test",
        artifact_digest="digest",
        canonical_path="canonical.json",
        intake_plan_path="plan.json",
        monday_preview_path="monday.json",
        drk_draft_path="drk.json",
        source_message_id="source-message",
        email_subject="subject",
        email_html_body="<p>CONFIRMED review_abc123_xyz987 abcdefghijklmnop</p>",
        email_text_body="CONFIRMED review_abc123_xyz987 abcdefghijklmnop",
        email_content_type="HTML",
    )

    found = store.find_active(
        artifact_digest="digest",
        source_message_id="source-message",
        recipient="reviewer@example.test",
    )
    assert found is not None
    assert found.review_id == "review_abc123_xyz987"
    assert found.email_html_body is not None
    assert found.email_content_type == "HTML"


def test_store_migrates_legacy_plain_text_email_body(tmp_path) -> None:
    import sqlite3

    db = tmp_path / "state.sqlite"
    with sqlite3.connect(db) as connection:
        connection.execute(
            """
            CREATE TABLE referral_reviews (
                review_id TEXT PRIMARY KEY,
                recipient TEXT NOT NULL,
                status TEXT NOT NULL,
                token_hash TEXT NOT NULL,
                artifact_digest TEXT NOT NULL,
                canonical_path TEXT NOT NULL,
                intake_plan_path TEXT NOT NULL,
                monday_preview_path TEXT NOT NULL,
                drk_draft_path TEXT NOT NULL,
                source_message_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                confirmed_at TEXT,
                confirmation_message_id TEXT UNIQUE,
                monday_item_id TEXT,
                drk_status TEXT,
                error TEXT,
                email_subject TEXT,
                email_body TEXT
            )
            """
        )
        connection.execute(
            """
            INSERT INTO referral_reviews (
                review_id, recipient, status, token_hash, artifact_digest, canonical_path,
                intake_plan_path, monday_preview_path, drk_draft_path, source_message_id,
                created_at, email_subject, email_body
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "review_legacy",
                "reviewer@example.test",
                "awaiting_confirmation",
                "hash",
                "digest",
                "canonical.json",
                "plan.json",
                "monday.json",
                "drk.json",
                "source-message",
                "2026-08-05T00:00:00+00:00",
                "subject",
                "CONFIRMED review_legacy token",
            ),
        )

    store = ReviewStore(db)
    found = store.get("review_legacy")
    assert found.email_text_body == "CONFIRMED review_legacy token"
    assert found.email_content_type == "Text"
