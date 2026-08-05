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
- **Working version pin**: `API-Version: 2026-07`

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
  -H "API-Version: 2026-07" \
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

---

### Master Sheet discovery export (read-only)

Use this before designing a production mapping. It exports every Master Sheet row,
the schema-derived metadata, and each board directly connected by a relation column.
The output can contain PHI and belongs under the Git-ignored `tmp/` directory.

```powershell
$env:PYTHONPATH = 'src'
.\.venv\Scripts\python.exe src/monday.com/export_monday_boards.py `
  --board-id 5815942462 `
  --include-related `
  --output-dir tmp/monday-exports/master-sheet-$(Get-Date -Format yyyyMMdd)
```

The default exports each record's displayed Monday value (`text`) and type. Use
`--include-raw-values` only when relation/value internals are specifically needed;
it makes the snapshot much larger and more likely to run into API capacity waits.

Generate the workflow map and real-data examples after the export:

```powershell
$env:PYTHONPATH = 'src'
.\.venv\Scripts\python.exe src/monday.com/analyze_master_sheet_export.py `
  tmp/monday-exports/master-sheet-YYYYMMDD `
  --flow-file 'Flow written down and questions.md'
```

If an older export lacks `schema.json`, refresh only the lightweight schemas and metadata without downloading its rows again:

```powershell
$env:PYTHONPATH = 'src'
.\.venv\Scripts\python.exe src/monday.com/refresh_monday_export_metadata.py `
  tmp/monday-exports/master-sheet-YYYYMMDD
```

Generate PHI-free guides for sharing with technical stakeholders:

```powershell
$env:PYTHONPATH = 'src'
.\.venv\Scripts\python.exe src/monday.com/generate_master_sheet_guides.py `
  tmp/monday-exports/master-sheet-YYYYMMDD `
  --output-dir .
```

Outputs:
- `boards/<board-name>/records.json`: exported records for one board
- `boards/<board-name>/schema.json`: raw board schema and column settings
- `boards/<board-name>/metadata.json`: columns, allowed statuses, relation targets, and population rates
- `manifest.json`: accessible-board and record-count summary
- `flow_to_monday_map.md`: workflow-stage to Master Sheet column map
- `scenario_examples.json`: local real-record examples for intake, handoff, scheduling, seen, hold, and discharge

### Master Sheet operational reads (read-only)

Use these commands for narrow, operational questions without exporting a new
full-board JSON snapshot. They paginate the board and write timestamped JSON
and CSV reports under `tmp/monday-reports/` by default. The reports contain PHI
and are ignored by Git; do not move them into tracked folders.

Find patient candidates by name and DOB:

```powershell
$env:PYTHONPATH = 'src'
python src/monday.com/find_master_sheet_patient.py `
  --name 'BUTLER, ALVA' `
  --dob '10/04/1940' `
  --include-full-row
```

List a confirmed status value. Use `summary` first when the exact labels are
unknown; do not treat `not-equals Seen` as a reliable "not seen" population.

```powershell
python src/monday.com/list_master_sheet_status.py `
  --field visit_status `
  --equals 'Seen' `
  --all `
  --report-name seen-patients

python src/monday.com/read_master_sheet.py summary --field scheduled_status
```

List the current intake marker:

```powershell
python src/monday.com/list_master_sheet_intake.py --stage 'In intake' --max-results 25
```

The shared CLI also supports `find`, `status`, `intake`, and `summary` subcommands.
Field aliases include `visit_status`, `scheduled_status`, `scheduling_complete`,
`case_manager`, `sent_to_cm`, `appointment_date`, and `stage`. Use
`python src/monday.com/read_master_sheet.py --help` for the complete list.
Use `--include-full-row` when the JSON report must include the complete Monday
item payload for each matched result. CSV reports then include that payload in
a `monday_item_json` column. Use `--all` only when the full matching set is
needed; otherwise reports are capped at 50 rows.

`find`, `status`, and `intake` use Monday's server-side filtering for fast
targeted reports. Patient lookup first retrieves a narrow partial-name candidate
set, then matches the complete normalized name and optional DOB locally. These
commands fetch only `--max-results` rows unless `--all` is specified; a capped
report records `"truncated": true`. `summary` intentionally scans the full board
to produce complete value counts, so it can take several minutes on the live
Master Sheet.

To build reports from an existing full local export without a new API request,
add its Master Sheet `records.json` path:

```powershell
python src/monday.com/list_master_sheet_status.py `
  --field visit_status `
  --not-equals 'Seen' `
  --all `
  --records-file tmp/monday-exports/wcw-master-sheet-export-2026-07-23/boards/master-sheet/records.json `
  --report-name not-seen-snapshot-20260723
```

### Advisory intake plans (no Monday or DRK writes)

`plan_referral_intake.py` turns a referral into an auditable action plan before
any system write is enabled. It validates the four-field intake threshold
(name, DOB, phone, address), identifies the remaining agency/clinical/insurance
gaps, and optionally checks for a name-plus-DOB duplicate.

All modes are non-mutating:

- `disabled`: no Monday call.
- `snapshot`: check a local Master Sheet `records.json` export.
- `live-readonly`: query Monday only to retrieve same-name candidates and
  confirm them locally by DOB.

Replay a known extraction against the saved snapshot without a new LLM call:

```powershell
$env:PYTHONPATH = 'src'
python src/monday.com/plan_referral_intake.py `
  --referral-json 'out/2026-07-17-run7-image-surgical/BUTLER, ALVA demo.json' `
  --monday-mode snapshot `
  --monday-records-file 'tmp/monday-exports/wcw-master-sheet-export-2026-07-23/boards/master-sheet/records.json'
```

Run extraction and planning from a PDF instead:

```powershell
python src/monday.com/plan_referral_intake.py `
  --pdf 'samples/BUTLER, ALVA demo.pdf' `
  --input-mode image `
  --monday-mode snapshot `
  --monday-records-file 'tmp/monday-exports/wcw-master-sheet-export-2026-07-23/boards/master-sheet/records.json'
```

Plans are saved beneath `tmp/intake-plans/`, which is ignored by Git because it
contains PHI. A duplicate requires exact normalized matches on patient name,
DOB, phone, and address. It still requires human review and never triggers an
automatic merge or record update. This planner does not import or invoke
`push_referral.py`.

### Master Sheet create preview (dry-run by default)

`push_master_sheet_plan.py` consumes an intake plan and builds a conservative
Master Sheet create request. It defaults to dry-run and does not call Monday in
that mode. It creates only when the plan is `ready_for_human_approval` and its
name-and-DOB duplicate check returned `no_candidates_found`; duplicate or
review-required plans are blocked, never updated.

The verified mapping creates an item with `Name`, `Patient DoB`, `Pt Phone`,
`Agency Phone Number`, and `Comments`. Existing Monday automation sets
`Stage = In intake`. The API user's direct write to `Date/Time Referral
Received` is currently restricted, so the inbox timestamp is preserved in
`Comments` and the item update instead. The writer can also link a **single exact** agency match to the
`Referring Agency` relation, route an approved partial referral to a configured
case manager, and create an item update containing the same intake context.

`Comments` is the explicit current destination for patient address, document
referral date, insurance, clinical information, requested services, and notes.
The Master Sheet has no dedicated columns for insurance, clinical information,
requested services, or a source PDF. Extracted facts therefore remain visible in
`Comments` and the item update rather than being silently dropped. The inbound
PDF remains in the local run artifacts for a future DRK integration and is not
uploaded to the Master Sheet.

Patient address is preserved in the update, but is not written to the Master
Sheet location column because that requires approved geocoding coordinates.
No agency relation is created for zero or multiple exact matches. The preview's
`mapping_notes` records these decisions instead of silently guessing.

```powershell
$env:PYTHONPATH = 'src'
python src/monday.com/push_master_sheet_plan.py `
  --plan 'tmp/intake-plans/example.intake-plan.json' `
  --agency-mode snapshot `
  --agency-records-file 'tmp/monday-exports/wcw-master-sheet-export-2026-07-23/boards/accounts/records.json' `
  --dry-run
```

The target mapping is [master_sheet_write_config.example.json](master_sheet_write_config.example.json).
`--apply --confirm-master-sheet-write` is the only way to invoke the create
mutation. Use it only with WCW's explicit approval and an unblocked preview.

### Outlook intake handoff

Outlook mailbox access, `.eml` parsing, idempotency, operator commands, and their
tests are documented under [`src/Outlook`](../Outlook/README.md), while cross-system
workflow ownership lives in [`src/referral_pipeline`](../referral_pipeline/README.md).
This folder retains Monday duplicate checks, agency lookup, and guarded writers.

### Master Sheet operational reads (read-only)

Use these commands for narrow, operational questions without exporting a new
full-board JSON snapshot. They paginate the board and write timestamped JSON
and CSV reports under `tmp/monday-reports/` by default. The reports contain PHI
and are ignored by Git; do not move them into tracked folders.

Find patient candidates by name and DOB:

```powershell
$env:PYTHONPATH = 'src'
python src/monday.com/find_master_sheet_patient.py `
  --name 'BUTLER, ALVA' `
  --dob '10/04/1940' `
  --include-full-row
```

List a confirmed status value. Use `summary` first when the exact labels are
unknown; do not treat `not-equals Seen` as a reliable "not seen" population.

```powershell
python src/monday.com/list_master_sheet_status.py `
  --field visit_status `
  --equals 'Seen' `
  --all `
  --report-name seen-patients

python src/monday.com/read_master_sheet.py summary --field scheduled_status
```

List the current intake marker:

```powershell
python src/monday.com/list_master_sheet_intake.py --stage 'In intake' --max-results 25
```

The shared CLI also supports `find`, `status`, `intake`, and `summary` subcommands.
Field aliases include `visit_status`, `scheduled_status`, `scheduling_complete`,
`case_manager`, `sent_to_cm`, `appointment_date`, and `stage`. Use
`python src/monday.com/read_master_sheet.py --help` for the complete list.
Use `--include-full-row` when the JSON report must include the complete Monday
item payload for each matched result. CSV reports then include that payload in
a `monday_item_json` column. Use `--all` only when the full matching set is
needed; otherwise reports are capped at 50 rows.

`find`, `status`, and `intake` use Monday's server-side filtering for fast
targeted reports. Patient lookup first retrieves a narrow partial-name candidate
set, then matches the complete normalized name and optional DOB locally. These
commands fetch only `--max-results` rows unless `--all` is specified; a capped
report records `"truncated": true`. `summary` intentionally scans the full board
to produce complete value counts, so it can take several minutes on the live
Master Sheet.

To build reports from an existing full local export without a new API request,
add its Master Sheet `records.json` path:

```powershell
python src/monday.com/list_master_sheet_status.py `
  --field visit_status `
  --not-equals 'Seen' `
  --all `
  --records-file tmp/monday-exports/wcw-master-sheet-export-2026-07-23/boards/master-sheet/records.json `
  --report-name not-seen-snapshot-20260723
```

### Advisory intake plans (no Monday or DRK writes)

`plan_referral_intake.py` turns a referral into an auditable action plan before
any system write is enabled. It validates the four-field intake threshold
(name, DOB, phone, address), identifies the remaining agency/clinical/insurance
gaps, and optionally checks for a name-plus-DOB duplicate.

All modes are non-mutating:

- `disabled`: no Monday call.
- `snapshot`: check a local Master Sheet `records.json` export.
- `live-readonly`: query Monday only to retrieve same-name candidates and
  confirm them locally by DOB.

Replay a known extraction against the saved snapshot without a new LLM call:

```powershell
$env:PYTHONPATH = 'src'
python src/monday.com/plan_referral_intake.py `
  --referral-json 'out/2026-07-17-run7-image-surgical/BUTLER, ALVA demo.json' `
  --monday-mode snapshot `
  --monday-records-file 'tmp/monday-exports/wcw-master-sheet-export-2026-07-23/boards/master-sheet/records.json'
```

Run extraction and planning from a PDF instead:

```powershell
python src/monday.com/plan_referral_intake.py `
  --pdf 'samples/BUTLER, ALVA demo.pdf' `
  --input-mode image `
  --monday-mode snapshot `
  --monday-records-file 'tmp/monday-exports/wcw-master-sheet-export-2026-07-23/boards/master-sheet/records.json'
```

Plans are saved beneath `tmp/intake-plans/`, which is ignored by Git because it
contains PHI. A duplicate requires exact normalized matches on patient name,
DOB, phone, and address. It still requires human review and never triggers an
automatic merge or record update. This planner does not import or invoke
`push_referral.py`.

### Master Sheet create preview (dry-run by default)

`push_master_sheet_plan.py` consumes an intake plan and builds a conservative
Master Sheet create request. It defaults to dry-run and does not call Monday in
that mode. It creates only when the plan is `ready_for_human_approval` and its
name-and-DOB duplicate check returned `no_candidates_found`; duplicate or
review-required plans are blocked, never updated.

The verified mapping creates an item with `Name`, `Patient DoB`, `Pt Phone`,
`Pt Email`, `Date/Time Referral Received`, agency contact/phone/email,
`POS`, explicit `Wx Order Included? = YES`, `Comments`, and
`Stage = In intake`. It can also link a **single exact** account match to each
of the `Referring Agency` and `Current HH/Hospice` relations, route an approved
partial referral to a configured case manager, and create an item update
containing the same intake context. `Sent By` is a People column: writing it
requires both `columns.sent_by` and an exact label-to-Monday-person-ID entry in
`sent_by_people`; an unconfigured label remains preserved in `Comments`.

`Comments` is the explicit fallback destination for patient address, document
referral date, insurance, clinical information, current agency details without
an exact account match, unsupported status values, requested services, and notes.
The Master Sheet has no dedicated columns for insurance, clinical information,
requested services, or a source PDF. Extracted facts therefore remain visible in
`Comments` and the item update rather than being silently dropped. The inbound
PDF remains in the local run artifacts for a future DRK integration and is not
uploaded to the Master Sheet.

`referral_pipeline.service.process_inbound_pdf(...)` defaults to the repository's
single two-call canonical extractor using the Anthropic Files API. Pass `sent_by`
explicitly; it is operational metadata and is never inferred from the PDF. The
pipeline writes the complete `canonical-referral.json`, projects it to the planner
record, performs the configured
duplicate and agency lookups, builds the exact Master Sheet column payload, and
only calls `create_item` when apply mode and explicit confirmation are both set.
Monday and DRK never independently interpret the PDF.

Patient address is preserved in the update, but is not written to the Master
Sheet location column because that requires approved geocoding coordinates.
No agency relation is created for zero or multiple exact matches. The preview's
`mapping_notes` records these decisions instead of silently guessing.

```powershell
$env:PYTHONPATH = 'src'
python src/monday.com/push_master_sheet_plan.py `
  --plan 'tmp/intake-plans/example.intake-plan.json' `
  --agency-mode snapshot `
  --agency-records-file 'tmp/monday-exports/wcw-master-sheet-export-2026-07-23/boards/accounts/records.json' `
  --dry-run
```

The target mapping is [master_sheet_write_config.example.json](master_sheet_write_config.example.json).
`--apply --confirm-master-sheet-write` is the only way to invoke the create
mutation. Use it only with WCW's explicit approval and an unblocked preview.

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
