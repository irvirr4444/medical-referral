# Monday.com AI handoff

Read `src/monday.com/readme.md` before changing or calling the Monday.com integration.

## Current state (2026-07-16)

- Monday GraphQL calls work against the current account.
- File uploads work through `https://api.monday.com/v2/file`.
- Tested successfully:
  - 4 mocked unit tests
  - 3 live read-only tests (`me`, `workspaces`, `boards`)
  - 3 live write tests (board/group/column/item CRUD, updates, subitems)
  - 1 live file-upload test
- Webhook code exists but delivery has not been tested because it needs a public callback URL.
- Live write tests create temporary `[API-TEST] harness ...` boards and archive them during teardown.

## Persistent visible demo board

- Name: `API Demo — keep (2026-07-16)`
- Board ID: `18422325133`
- URL: https://shfa-squad.monday.com/boards/18422325133
- Do not archive or delete it unless the user explicitly asks.
- It demonstrates creating/editing/deleting items, status changes, groups, columns, an update, a subitem, and moving an item.

## Tomorrow's starting procedure

1. Replace `MONDAY_DOT_COM_API_KEY` in the local `.env` with the good-account key.
2. Never print, commit, or copy the key into source/docs.
3. Confirm identity:

   ```bash
   PYTHONPATH=src python3.11 src/monday.com/monday_client.py --pretty
   ```

4. Run read-only tests:

   ```bash
   MONDAY_LIVE_TEST=1 PYTHONPATH=src pytest -q src/monday.com/tests -k live_readonly
   ```

5. Run write and file tests:

   ```bash
   MONDAY_LIVE_TEST=1 MONDAY_LIVE_WRITE_TEST=1 MONDAY_LIVE_FILES_TEST=1 \
     PYTHONPATH=src pytest -q src/monday.com/tests
   ```

6. For webhooks, follow the ngrok/public callback procedure in `src/monday.com/readme.md`.
7. Before building the referral workflow, query the target board's groups and columns. Do not assume IDs from the demo board.
8. Map `ReferralIntake` fields from `src/intake_extractor/schema.py` to the target board's actual column IDs.

## Important implementation files

- `src/referral_pipeline/integrations/monday/transport.py`: reusable GraphQL and multipart file-upload transport
- `src/monday.com/monday_client.py`: command-line GraphQL client
- `src/monday.com/push_referral.py`: referral extractor -> Monday item bridge with upsert behavior
- `src/monday.com/referral_board_config.py`: board/group/column mapping config loader
- `src/monday.com/referral_board_config.example.json`: example config for the current referral board
- `src/monday.com/tests/`: unit and live endpoint tests
- `src/monday.com/webhook_receiver.py`: webhook challenge/event receiver
- `src/monday.com/readme.md`: complete endpoint cookbook and runbook

## Safety

- The project handles PHI. Do not put real patient data into test boards, logs, fixtures, or comments.
- Tests must use synthetic data.
- Obtain explicit approval before writing to a production board.
- Prefer temporary test boards with cleanup when validating mutations.
- A successful API response is not enough: verify important writes by reading the object back.

