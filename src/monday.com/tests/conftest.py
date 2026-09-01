from __future__ import annotations

import os
import sys
import time
import uuid
from collections.abc import Iterator
from pathlib import Path

import pytest

from referral_pipeline.integrations.monday.transport import MondayAPIError, monday_graphql

# Ensure `src/monday.com` sibling modules are importable when running pytest against this folder.
_MONDAY_DIR = Path(__file__).resolve().parents[1]
if str(_MONDAY_DIR) not in sys.path:
    sys.path.insert(0, str(_MONDAY_DIR))


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "live_readonly: live Monday.com read-only API tests")
    config.addinivalue_line("markers", "live_write: live Monday.com write API tests (creates+archives)")
    config.addinivalue_line("markers", "files: live Monday.com file upload tests")
    config.addinivalue_line("markers", "webhook: live Monday.com webhook tests")
    config.addinivalue_line("markers", "unit: mocked unit tests (no network)")


def _env_enabled(name: str) -> bool:
    return os.getenv(name) == "1"


@pytest.fixture(scope="session")
def run_suffix() -> str:
    return f"{int(time.time())}-{uuid.uuid4().hex[:8]}"


@pytest.fixture(scope="session")
def monday_api_key_present() -> None:
    if not os.getenv("MONDAY_DOT_COM_API_KEY"):
        from dotenv import load_dotenv

        load_dotenv()
    if not os.getenv("MONDAY_DOT_COM_API_KEY"):
        pytest.skip("MONDAY_DOT_COM_API_KEY not set")


@pytest.fixture(scope="session")
def live_enabled(monday_api_key_present: None) -> None:
    if not _env_enabled("MONDAY_LIVE_TEST"):
        pytest.skip("Set MONDAY_LIVE_TEST=1 to run live Monday.com API tests.")


@pytest.fixture(scope="session")
def live_write_enabled(live_enabled: None) -> None:
    if not _env_enabled("MONDAY_LIVE_WRITE_TEST"):
        pytest.skip("Set MONDAY_LIVE_WRITE_TEST=1 to run live write tests.")


@pytest.fixture(scope="session")
def live_files_enabled(live_write_enabled: None) -> None:
    if not _env_enabled("MONDAY_LIVE_FILES_TEST"):
        pytest.skip("Set MONDAY_LIVE_FILES_TEST=1 to run live file upload tests.")


@pytest.fixture(scope="session")
def live_webhook_enabled(live_write_enabled: None) -> None:
    if not _env_enabled("MONDAY_LIVE_WEBHOOK_TEST"):
        pytest.skip("Set MONDAY_LIVE_WEBHOOK_TEST=1 to run live webhook tests.")
    if not os.getenv("MONDAY_WEBHOOK_PUBLIC_URL"):
        pytest.skip("Set MONDAY_WEBHOOK_PUBLIC_URL to a public callback URL (e.g. ngrok).")


@pytest.fixture(scope="session")
def temp_board(live_write_enabled: None, run_suffix: str) -> Iterator[dict]:
    """Create a temporary board with common columns; archive on teardown."""
    board_name = f"[API-TEST] harness {run_suffix}"
    try:
        created = monday_graphql(
            """
            mutation ($name: String!) {
              create_board(board_name: $name, board_kind: public) {
                id
                name
              }
            }
            """,
            variables={"name": board_name},
        )
    except MondayAPIError as e:
        pytest.fail(f"create_board failed: {e}")

    board = created["data"]["create_board"]
    board_id = board["id"]

    # Ensure a named group exists for create_item.
    group = monday_graphql(
        """
        mutation ($boardId: ID!, $groupName: String!) {
          create_group(board_id: $boardId, group_name: $groupName) { id title }
        }
        """,
        variables={"boardId": board_id, "groupName": f"test-group-{run_suffix}"},
    )["data"]["create_group"]

    # Create columns we rely on in write tests.
    columns: dict[str, str] = {}
    for title, col_type, key in (
        ("API Text", "text", "text"),
        ("API Status", "status", "status"),
        ("API Date", "date", "date"),
        ("API Files", "file", "files"),
    ):
        col = monday_graphql(
            """
            mutation ($boardId: ID!, $title: String!, $type: ColumnType!) {
              create_column(board_id: $boardId, title: $title, column_type: $type) {
                id
                title
                type
              }
            }
            """,
            variables={"boardId": board_id, "title": title, "type": col_type},
        )["data"]["create_column"]
        columns[key] = col["id"]

    # Seed one item for update/subitem/file/webhook tests.
    item = monday_graphql(
        """
        mutation ($boardId: ID!, $groupId: String!, $name: String!) {
          create_item(board_id: $boardId, group_id: $groupId, item_name: $name) { id name }
        }
        """,
        variables={
            "boardId": board_id,
            "groupId": group["id"],
            "name": f"seed-item-{run_suffix}",
        },
    )["data"]["create_item"]

    ctx = {
        "board_id": board_id,
        "board_name": board["name"],
        "group_id": group["id"],
        "columns": columns,
        "item_id": item["id"],
        "run_suffix": run_suffix,
    }
    try:
        yield ctx
    finally:
        try:
            monday_graphql(
                """
                mutation ($boardId: ID!) {
                  archive_board(board_id: $boardId) { id }
                }
                """,
                variables={"boardId": board_id},
            )
        except MondayAPIError:
            # Best-effort cleanup; leave failure visible in logs via pytest warnings.
            pass
