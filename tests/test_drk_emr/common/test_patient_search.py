from __future__ import annotations

from drk_emr.common.patient_search import (
    SearchCandidate,
    candidates_from_in_page_fetch,
    finalize_search_candidates,
)


def test_finalize_fails_closed_when_rows_exist_without_ids() -> None:
    candidates, error = finalize_search_candidates(
        candidates=[],
        result_count=1,
        row_count=1,
        stable=True,
        open_unique=False,
    )
    assert candidates == []
    assert error == "unable_to_resolve_candidate_ids"


def test_finalize_opens_unique_row_for_profile_lookup() -> None:
    opened = SearchCandidate(patient_id="55125", display_name="Alva Butler", source="search_open")
    candidates, error = finalize_search_candidates(
        candidates=[],
        result_count=1,
        row_count=1,
        stable=True,
        open_unique=True,
        open_unique_fn=lambda: opened,
    )
    assert error is None
    assert candidates == [opened]


def test_in_page_search_fetch_reads_patient_ids() -> None:
    class Driver:
        def execute_async_script(self, _script: str, query: str) -> dict:
            assert query == "Alva Butler"
            return {
                "patients": [
                    {
                        "id": 55125,
                        "name": "Alva Butler",
                        "dateOfBirth": "1940-10-04T00:00:00",
                        "mrn": "1087998220",
                    }
                ]
            }

    matches = candidates_from_in_page_fetch(Driver(), query="Alva Butler")
    assert len(matches) == 1
    assert matches[0].patient_id == "55125"
    assert matches[0].display_name == "Alva Butler"
