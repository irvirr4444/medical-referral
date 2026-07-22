### Monday.com API notes (for this repo)

This project uses Monday.com via its **GraphQL API**, with a dedicated multipart endpoint for file uploads.

> **AI handoff:** Start with [`AGENTS.md`](AGENTS.md). It records the verified test
> status, persistent demo board, safety rules, and tomorrow's exact startup steps.

#### Verified status (2026-07-16)
- Unit tests: **4 passed**
- Live read-only tests: **3 passed**
- Live CRUD/update/subitem tests: **3 passed**
- Live file-upload tests: **1 passed**
- Webhook delivery: **not yet run** (requires a public callback URL)
- Persistent demo board: [`API Demo — keep (2026-07-16)`](https://shfa-squad.monday.com/boards/18422325133)

#### Core facts
- **GraphQL endpoint**: `POST https://api.monday.com/v2`
- **File upload endpoint**: `POST https://api.monday.com/v2/file` (multipart)
- **Auth header**: `Authorization: <MONDAY_DOT_COM_API_KEY>`
- **Body (GraphQL)**: JSON with `query` and optional `variables`
- **Optional version pin**: `API-Version: 2023-10`

#### Environment setup
- Put your key in `.env` as:
  - `MONDAY_DOT_COM_API_KEY=...`
- Never commit `.env`.
- If the key was pasted into chat/logs, **rotate it** in Monday and replace it locally.

#### Code layout
| Path | Purpose |
| --- | --- |
| `src/monday.com/monday_api.py` | GraphQL + file-upload helpers (`monday_graphql`, `monday_file_upload`) |
| `src/monday.com/monday_client.py` | CLI for ad-hoc queries |
| `src/monday.com/push_referral.py` | Extract one referral PDF and create/update a mapped Monday item |
| `src/monday.com/referral_board_config.py` | Typed config loader for board/group/column mapping |
| `src/monday.com/referral_board_config.example.json` | Example mapping for the current referral demo board |
| `src/monday.com/webhook_receiver.py` | Local webhook receiver for live webhook tests |
| `src/monday.com/tests/` | Unit + live endpoint smoke tests |
| `src/monday.com/readme.md` | This document |

Smoke test (prints `me`):

```bash
PYTHONPATH=src python3.11 src/monday.com/monday_client.py --pretty
```

---

### Quick-start: `curl`

Who am I:

```bash
curl -sS https://api.monday.com/v2 \
  -H "Authorization: $MONDAY_DOT_COM_API_KEY" \
  -H "Content-Type: application/json" \
  -H "API-Version: 2023-10" \
  --data '{"query":"{ me { id name email } }"}'
```

List boards:

```bash
curl -sS https://api.monday.com/v2 \
  -H "Authorization: $MONDAY_DOT_COM_API_KEY" \
  -H "Content-Type: application/json" \
  --data '{"query":"{ boards(limit: 5) { id name } }"}'
```

---

### Quick-start: Python

```python
from monday_api import monday_graphql, monday_file_upload

resp = monday_graphql("{ me { id name email } }")
print(resp["data"])
```

CLI:

```bash
PYTHONPATH=src python3.11 src/monday.com/monday_client.py \
  --pretty --data-only \
  --query '{ boards(limit: 5) { id name } }'
```

Referral push dry run:

```bash
PYTHONPATH=src python3.11 src/monday.com/push_referral.py \
  "samples/EC - REFERRAL FORM.pdf" \
  --config src/monday.com/referral_board_config.example.json \
  --input-mode image \
  --write-out-dir out/monday-smoke \
  --dry-run
```

Referral push live write:

```bash
PYTHONPATH=src python3.11 src/monday.com/push_referral.py \
  "samples/EC - REFERRAL FORM.pdf" \
  --config src/monday.com/referral_board_config.example.json \
  --input-mode image \
  --write-out-dir out/monday-smoke
```

Behavior summary:
- extracts via the main intake pipeline, then maps selected fields into Monday columns
- supports text or dropdown insurance columns via `insurance_provider_mode`
- upserts by attached PDF filename first, then exact item name fallback
- skips duplicate PDF uploads when the item already has that same file attached
- writes progress logs to `stderr` unless `--quiet` is used

---

### Test harness (field-ready for tomorrow)

Tests live under `src/monday.com/tests/`. Live write tests create a temporary board named like `[API-TEST] harness …` and **archive it on teardown**.

#### Prereqs
- `MONDAY_DOT_COM_API_KEY` in `.env` (token with board create/write access)
- For webhooks: a **public** callback URL (e.g. ngrok) pointing at the local receiver
- For files: write access + ability to create updates / file columns

#### Env flags

| Flag | Meaning |
| --- | --- |
| `MONDAY_LIVE_TEST=1` | Enable live network tests |
| `MONDAY_LIVE_WRITE_TEST=1` | Allow create/update/archive (temp board) |
| `MONDAY_LIVE_FILES_TEST=1` | Enable `/v2/file` upload tests |
| `MONDAY_LIVE_WEBHOOK_TEST=1` | Enable webhook create/trigger/delete |
| `MONDAY_WEBHOOK_PUBLIC_URL=…` | Public URL to `/webhook` (or base URL) |

#### Runbook (copy/paste)

Unit only (no network):

```bash
PYTHONPATH=src pytest -q src/monday.com/tests -k unit
```

Live read-only:

```bash
MONDAY_LIVE_TEST=1 PYTHONPATH=src pytest -q src/monday.com/tests -k live_readonly
```

Live writes (creates + archives temp board):

```bash
MONDAY_LIVE_TEST=1 MONDAY_LIVE_WRITE_TEST=1 PYTHONPATH=src pytest -q src/monday.com/tests -k live_write
```

Live files:

```bash
MONDAY_LIVE_TEST=1 MONDAY_LIVE_WRITE_TEST=1 MONDAY_LIVE_FILES_TEST=1 \
  PYTHONPATH=src pytest -q src/monday.com/tests -k files
```

Live webhooks:

```bash
# terminal 1
PYTHONPATH=src python3.11 src/monday.com/webhook_receiver.py --port 8000

# terminal 2 (example)
ngrok http 8000

# terminal 3
MONDAY_LIVE_TEST=1 MONDAY_LIVE_WRITE_TEST=1 MONDAY_LIVE_WEBHOOK_TEST=1 \
  MONDAY_WEBHOOK_PUBLIC_URL=https://<ngrok-host>/webhook \
  PYTHONPATH=src pytest -q src/monday.com/tests -k webhook
```

Full operational suite (everything except webhooks unless URL set):

```bash
MONDAY_LIVE_TEST=1 MONDAY_LIVE_WRITE_TEST=1 MONDAY_LIVE_FILES_TEST=1 \
  PYTHONPATH=src pytest -q src/monday.com/tests
```

---

### Endpoint test matrix

Each row is covered by automated tests under `src/monday.com/tests/`.

#### A) Read-only (`test_monday_api_live.py`, marker `live_readonly`)

| Endpoint | Purpose | Asserts |
| --- | --- | --- |
| `me` | Auth + identity | `id` present |
| `workspaces` | List workspaces | returns a list |
| `boards(limit:)` | List boards | returns a list |

```graphql
{ me { id name email } }
{ workspaces { id name kind } }
{ boards(limit: 5) { id name board_kind } }
```

#### B) CRUD write path (`test_endpoints_crud_live.py` + `temp_board` fixture, marker `live_write`)

| Endpoint | Purpose | Asserts / cleanup |
| --- | --- | --- |
| `create_board` | Temp board | id returned |
| `create_group` | Named group | id returned |
| `create_column` (`text`, `status`, `date`, `file`) | Columns for mapping | ids returned |
| `create_item` | Row create | id returned |
| `change_multiple_column_values` | Multi-field write | text/date read-back |
| `boards(ids:)` / `items(ids:)` | Read-back | values match |
| `archive_board` | Cleanup | teardown always |

Create board:

```graphql
mutation ($name: String!) {
  create_board(board_name: $name, board_kind: public) { id name }
}
```

Create group:

```graphql
mutation ($boardId: ID!, $groupName: String!) {
  create_group(board_id: $boardId, group_name: $groupName) { id }
}
```

Create column:

```graphql
mutation ($boardId: ID!, $title: String!, $type: ColumnType!) {
  create_column(board_id: $boardId, title: $title, column_type: $type) { id }
}
```

Create item:

```graphql
mutation ($boardId: ID!, $groupId: String!, $name: String!) {
  create_item(board_id: $boardId, group_id: $groupId, item_name: $name) { id }
}
```

Update columns (**`column_values` is a JSON string**):

```graphql
mutation ($boardId: ID!, $itemId: ID!, $values: JSON!) {
  change_multiple_column_values(
    board_id: $boardId, item_id: $itemId, column_values: $values
  ) { id }
}
```

Example variables:

```json
{
  "boardId": "123",
  "itemId": "456",
  "values": "{\"text_col_id\":\"hello\",\"date_col_id\":{\"date\":\"2026-07-16\"}}"
}
```

#### C) Updates (`test_endpoints_updates_live.py`)

| Endpoint | Purpose | Asserts |
| --- | --- | --- |
| `create_update` | Comment on item | id + body |
| `items { updates }` | Read-back | update visible |

```graphql
mutation ($itemId: ID!, $body: String!) {
  create_update(item_id: $itemId, body: $body) { id body }
}
```

#### D) Subitems (`test_endpoints_subitems_live.py`)

| Endpoint | Purpose | Asserts |
| --- | --- | --- |
| `create_subitem` | Child row | id + name |
| `items { subitems }` | Read-back | subitem listed |

```graphql
mutation ($parentId: ID!, $name: String!) {
  create_subitem(parent_item_id: $parentId, item_name: $name) { id name }
}
```

#### E) Files (`test_endpoints_files_live.py`, marker `files`)

Uses **`https://api.monday.com/v2/file`** via `monday_file_upload()`.

| Endpoint | Purpose | Asserts |
| --- | --- | --- |
| `add_file_to_update` | Attach file to update | asset id |
| `add_file_to_column` | Attach to files column | asset id |

```graphql
mutation ($file: File!, $updateId: ID!) {
  add_file_to_update(update_id: $updateId, file: $file) { id name }
}

mutation ($file: File!, $itemId: ID!, $columnId: String!) {
  add_file_to_column(item_id: $itemId, column_id: $columnId, file: $file) { id name }
}
```

#### F) Webhooks (`test_endpoints_webhooks_live.py`, marker `webhook`)

| Endpoint | Purpose | Asserts / cleanup |
| --- | --- | --- |
| `create_webhook` | Subscribe to `change_column_value` | id; challenge handled by receiver |
| column change | Trigger delivery | event appears at `GET /events` |
| `delete_webhook` | Cleanup | always in `finally` |

```graphql
mutation ($boardId: ID!, $url: String!) {
  create_webhook(board_id: $boardId, url: $url, event: change_column_value) { id }
}

mutation ($id: ID!) {
  delete_webhook(id: $id) { id }
}
```

Receiver routes (`webhook_receiver.py`):
- `POST /webhook` — accepts events; echoes Monday `challenge`
- `GET /events` — list received payloads
- `GET /clear` — clear store
- `GET /health` — liveness

---

### Unit tests (`test_monday_api_unit.py`, marker `unit`)

Mocked coverage (no network):
- successful GraphQL headers + JSON parse
- GraphQL `errors` → `MondayAPIError`
- HTTP 401 → `MondayAPIError` with parsed body
- multipart file upload posts to `/v2/file` with expected form parts

---

### Common cookbook (non-test reference)

#### Identity / users
```graphql
{ me { id name email } }
{ users { id name email } }
{ teams { id name } }
```

#### Workspaces / boards
```graphql
{ workspaces { id name kind } }
{ boards(limit: 10) { id name board_kind } }
```

#### Read columns / item values
```graphql
query ($boardId: [ID!]) {
  boards(ids: $boardId) { columns { id title type } }
}

query ($itemIds: [ID!]) {
  items(ids: $itemIds) { id name column_values { id text value } }
}
```

#### Archive cleanup
```graphql
mutation ($boardId: ID!) {
  archive_board(board_id: $boardId) { id }
}
```

---

### Official docs
- Monday API reference: https://developer.monday.com/api-reference/docs
- Assets / file uploads: https://developer.monday.com/api-reference/reference/assets-1
- Webhooks: https://developer.monday.com/api-reference/reference/webhooks
