from __future__ import annotations

import pytest

import patient_profile.sources as sources


def test_reader_operation_restarts_dead_session_once(monkeypatch: pytest.MonkeyPatch) -> None:
    readers = [object(), object()]
    invalidations: list[bool] = []
    calls: list[object] = []

    monkeypatch.setattr(sources, "_drk_reader", lambda: readers[len(calls)])
    monkeypatch.setattr(sources, "_invalidate_reader", lambda: invalidations.append(True))

    def operation(reader: object) -> str:
        calls.append(reader)
        if len(calls) == 1:
            raise RuntimeError("Message: invalid session id")
        return "ok"

    assert sources._with_reader_retry(operation) == "ok"
    assert calls == readers
    assert invalidations == [True]


def test_reader_operation_does_not_retry_regular_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    reader = object()
    calls: list[object] = []
    monkeypatch.setattr(sources, "_drk_reader", lambda: reader)

    def operation(current: object) -> str:
        calls.append(current)
        raise RuntimeError("DRK search returned no summary")

    with pytest.raises(RuntimeError, match="no summary"):
        sources._with_reader_retry(operation)
    assert calls == [reader]
