from intake_extractor.eval.evaluate import (
    _normalize_date,
    _normalize_phone,
    _score_requested_services,
)


def _svc(service: str, frequency: str | None = None, instructions: str | None = None) -> dict:
    return {"service": service, "frequency": frequency, "instructions": instructions}


def test_duplicate_service_labels_are_not_overwritten() -> None:
    expected = [
        _svc("Skilled Nursing", frequency="2x/week"),
        _svc("Skilled Nursing", frequency="1x/week"),
    ]
    actual = [
        _svc("Skilled Nursing", frequency="2x/week"),
        _svc("Skilled Nursing", frequency="1x/week"),
    ]

    score, detail = _score_requested_services(expected, actual)

    assert score == 1.0
    assert "missing=[]" in detail
    assert "extra=[]" in detail
    assert "matched=2/2" in detail


def test_one_to_one_matching_with_similar_services() -> None:
    expected = [
        _svc("Physical Therapy", frequency="3x/week"),
        _svc("Occupational Therapy", frequency="2x/week"),
    ]
    # Reordered + near-duplicate wording; each gold row still binds to one predicted row.
    actual = [
        _svc("Occupational Therapy services", frequency="2x/week"),
        _svc("Physical Therapy evaluation", frequency="3x/week"),
    ]

    score, detail = _score_requested_services(expected, actual)

    assert score > 0.8
    assert "missing=[]" in detail
    assert "extra=[]" in detail
    assert "matched=2/2" in detail


def test_extra_predicted_services_reduce_score() -> None:
    expected = [_svc("Wound Care")]
    actual = [_svc("Wound Care"), _svc("Home Health")]

    score, detail = _score_requested_services(expected, actual)

    assert score < 1.0
    assert "Home Health" in detail
    assert "extra=" in detail


def test_missing_predicted_services_reduce_score() -> None:
    expected = [_svc("Wound Care"), _svc("Physical Therapy")]
    actual = [_svc("Wound Care")]

    score, detail = _score_requested_services(expected, actual)

    assert score < 1.0
    assert "Physical Therapy" in detail
    assert "missing=" in detail


def test_frequency_and_instructions_mismatch_partial_credit() -> None:
    expected = [_svc("Skilled Nursing", frequency="2x/week", instructions="Wound checks")]
    perfect_actual = [_svc("Skilled Nursing", frequency="2x/week", instructions="Wound checks")]
    mismatched_actual = [_svc("Skilled Nursing", frequency="1x/month", instructions="Medication teaching")]

    perfect_score, _ = _score_requested_services(expected, perfect_actual)
    partial_score, detail = _score_requested_services(expected, mismatched_actual)

    assert perfect_score == 1.0
    # Service matched, so this is not a full miss, but attachments reduce the score.
    assert 0.7 <= partial_score < 1.0
    assert "missing=[]" in detail
    assert "extra=[]" in detail
    assert "matched=1/1" in detail


def test_empty_lists_score_perfect() -> None:
    score, detail = _score_requested_services([], [])
    assert score == 1.0
    assert "empty" in detail


def test_normalize_date_handles_common_formats() -> None:
    assert _normalize_date("3/6/26") == "2026-03-06"
    assert _normalize_date("02/09/1964") == "1964-02-09"
    assert _normalize_date("07/08/2026") == "2026-07-08"
    assert _normalize_date(None) is None


def test_normalize_phone_digit_only() -> None:
    assert _normalize_phone("(626) 379-1461") == "6263791461"
    assert _normalize_phone("18189389143") == "18189389143"
    assert _normalize_phone("626.379.1461") == "6263791461"
    assert _normalize_phone(None) is None
