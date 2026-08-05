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
