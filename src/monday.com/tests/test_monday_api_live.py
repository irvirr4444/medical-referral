from __future__ import annotations

import pytest

from monday_api import MondayAPIError, monday_graphql


pytestmark = [pytest.mark.live_readonly]


def test_live_me_smoke(live_enabled: None) -> None:
    try:
        resp = monday_graphql("{ me { id name email } }")
    except MondayAPIError as e:
        pytest.fail(f"Monday live call failed: {e}")

    me = resp.get("data", {}).get("me")
    assert me
    assert str(me.get("id", "")).strip()


def test_live_workspaces(live_enabled: None) -> None:
    resp = monday_graphql("{ workspaces { id name kind } }")
    workspaces = resp.get("data", {}).get("workspaces")
    assert isinstance(workspaces, list)


def test_live_boards_list(live_enabled: None) -> None:
    resp = monday_graphql("{ boards(limit: 5) { id name board_kind } }")
    boards = resp.get("data", {}).get("boards")
    assert isinstance(boards, list)
