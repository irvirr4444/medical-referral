from __future__ import annotations

from datetime import date

from drk_emr.common.patient_search import (
    SearchCandidate,
    candidates_from_in_page_fetch,
    dashboard_search_query,
    finalize_search_candidates,
    parse_name_cell,
    select_search_candidate,
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


def test_dashboard_search_query_uses_first_two_given_name_tokens() -> None:
    assert dashboard_search_query("Anita Rodriguez Hernandez") == "Anita Rodriguez"
    assert dashboard_search_query("Rodriguez Hernandez, Anita") == "Anita Rodriguez"
    assert dashboard_search_query("RODRIGUEZ HERNANDEZ, ANITA BERENICE") == "Anita Rodriguez"
    assert dashboard_search_query("Eliut Cruz Pagan") == "Eliut Cruz"
    assert dashboard_search_query("Gonzalez, Eric") == "Eric Gonzalez"
    assert dashboard_search_query("Zadran, Khojagul") == "Khojagul Zadran"
    assert dashboard_search_query("Frank Sardina") == "Frank Sardina"
    assert dashboard_search_query("Alva Butler") == "Alva Butler"


def test_parse_name_cell_reads_age_and_sex() -> None:
    parsed = parse_name_cell("Anita Rodriguez Active 45 y · F")
    assert parsed == {"name": "Anita Rodriguez", "status": "Active", "age": 45, "sex": "F"}
    parsed_male = parse_name_cell("Anita Rodriguez Active 83 y · M")
    assert parsed_male["age"] == 83
    assert parsed_male["sex"] == "M"


def _row(**overrides: object) -> SearchCandidate:
    values = {
        "patient_id": "",
        "display_name": "Anita Rodriguez",
        "source": "search_table",
        "row_index": 0,
    }
    values.update(overrides)
    return SearchCandidate(**values)  # type: ignore[arg-type]


def test_select_search_candidate_uses_dob_not_top_row() -> None:
    rows = (
        _row(row_index=0, age=100, sex="F", date_of_birth="1926-01-01"),
        _row(row_index=1, age=83, sex="M", date_of_birth="1943-02-02"),
        _row(row_index=2, age=45, sex="F", date_of_birth="05/17/1981"),
    )
    chosen = select_search_candidate(
        rows,
        name="Anita Rodriguez Hernandez",
        date_of_birth="1981-05-17",
    )
    assert chosen is not None
    assert chosen.row_index == 2
    assert chosen.age == 45


def test_select_search_candidate_can_use_age_when_dob_column_blank() -> None:
    rows = (
        _row(row_index=0, age=100, sex="F"),
        _row(row_index=1, age=83, sex="M"),
        _row(row_index=2, age=45, sex="F"),
    )
    chosen = select_search_candidate(
        rows,
        date_of_birth="1981-05-17",
        as_of=date(2026, 8, 18),
    )
    assert chosen is not None
    assert chosen.row_index == 2


def test_select_search_candidate_requires_identity_when_multiple_unmatched() -> None:
    rows = (
        _row(row_index=0, age=100, sex="F"),
        _row(row_index=1, age=83, sex="M"),
        _row(row_index=2, age=45, sex="F"),
    )
    assert select_search_candidate(rows, name="Anita Rodriguez") is None


def test_select_search_candidate_accepts_a_single_row() -> None:
    chosen = select_search_candidate([_row(display_name="Khojagul Zadran")], name="Zadran, Khojagul")
    assert chosen is not None
    assert chosen.display_name == "Khojagul Zadran"
