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
