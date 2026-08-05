# Referral pipeline orchestration

This package connects the system-specific adapters into one intake workflow:

```text
Outlook or saved .eml
        |
        v
PDF validation and idempotency
        |
        v
Canonical Anthropic Files API extraction (two passes)
        |
        v
Monday duplicate and agency checks
        |
        v
Master Sheet preview
        |
        v
Review email and sender-bound confirmation
        |
        v
Monday create, then audited DRK handoff
```

The normal operator entry point is the repository-root `run_pipeline.py`. Intake
does not write to Monday; an exact reply from the configured reviewer authorizes
the immutable artifact bundle.

## Commands

Process the newest Outlook message, build both destination drafts, and send a
review email:

```powershell
python run_pipeline.py outlook --send-review
```

After the reviewer replies with the command printed in that email:

```powershell
python run_pipeline.py approvals --execute
```

The manual exact-preview path remains available for debugging:

```powershell
python run_pipeline.py apply --confirm-master-sheet-write
```

Use `python run_pipeline.py outlook --help` for optional source, extraction,
lookup, output, and debugging flags.

## Responsibilities

- `cli.py`: operator commands, safe defaults, latest-run pointer, and guarded apply.
- `runner.py`: source polling, PDF materialization, idempotency, and batch execution.
- `service.py`: one accepted PDF through canonical Files API extraction, destination projections, planning, Monday preview, and optional create.
- `state.py`: local SQLite record of completed attachments.
- `review/`: deterministic summary rendering, token/sender gating, durable review state, and destination execution.

Every production intake writes `canonical-referral.json`, `inbox-intake.txt`, and
`drk-create-draft.json` from the same immutable extraction. Compatibility modules
may project that record into older schemas, but must not interpret the PDF again.

The Outlook and Monday folders contain adapters, not workflow ownership. A confirmed
review can create the Monday item and emits `drk-handoff.json` afterward. DRK's
duplicate check and form-filling tools remain separate, and automatic **Create
Patient** submission is intentionally unimplemented.
