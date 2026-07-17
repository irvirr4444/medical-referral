from __future__ import annotations

import pytest

from monday_api import monday_file_upload, monday_graphql


pytestmark = [pytest.mark.live_write, pytest.mark.files]


def test_live_file_upload_to_update(temp_board: dict, live_files_enabled: None) -> None:
    item_id = temp_board["item_id"]
    run_suffix = temp_board["run_suffix"]
    filename = f"api-test-{run_suffix}.txt"
    file_bytes = f"monday file upload smoke {run_suffix}\n".encode("utf-8")

    update = monday_graphql(
        """
        mutation ($itemId: ID!, $body: String!) {
          create_update(item_id: $itemId, body: $body) { id }
        }
        """,
        variables={"itemId": item_id, "body": f"file-host-update-{run_suffix}"},
    )["data"]["create_update"]
    update_id = update["id"]

    uploaded = monday_file_upload(
        query=(
            "mutation ($file: File!, $updateId: ID!) {"
            "  add_file_to_update(update_id: $updateId, file: $file) { id name }"
            "}"
        ),
        variables={"updateId": update_id},
        file_bytes=file_bytes,
        filename=filename,
        content_type="text/plain",
    )
    asset = uploaded["data"]["add_file_to_update"]
    assert asset["id"]
    assert filename in (asset.get("name") or filename)

    # Also exercise add_file_to_column when a files column exists.
    files_col = temp_board["columns"].get("files")
    if files_col:
        col_upload = monday_file_upload(
            query=(
                "mutation ($file: File!, $itemId: ID!, $columnId: String!) {"
                "  add_file_to_column(item_id: $itemId, column_id: $columnId, file: $file) {"
                "    id name"
                "  }"
                "}"
            ),
            variables={"itemId": item_id, "columnId": files_col},
            file_bytes=file_bytes,
            filename=f"col-{filename}",
            content_type="text/plain",
        )
        col_asset = col_upload["data"]["add_file_to_column"]
        assert col_asset["id"]
