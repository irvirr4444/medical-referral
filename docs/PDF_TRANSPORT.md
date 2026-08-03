# Anthropic PDF transport policy

## Decision

`files-api` is the primary transport for high-accuracy PDF extraction. `inline`
remains fully supported as an explicit fallback.

This choice changes only how the same native PDF reaches Anthropic. It does not
change the model, prompts, structured-output schemas, number of extraction
passes, adjudication rules, Monday adapter, or DRK adapter.

## Files API primary path

With `files-api`, the extractor:

1. uploads the original PDF once;
2. references the returned Anthropic file ID in every extraction and
   adjudication request;
3. runs the same identity/referral, clinical, and insurance pipelines;
4. deletes the temporary Anthropic file in a `finally` block after success or
   failure; and
5. records `"pdf_transport": "files-api"` in `_manifest.json`.

The extraction fails if temporary-file deletion fails. This prevents a
successful result from hiding an unresolved remote-PHI cleanup problem.

## Inline fallback path

With `inline`, every model request contains the original PDF as base64 data.
There is no Anthropic Files API upload or file ID to delete.

Inline requests are limited to 23 MB by this implementation. The limit leaves
room for base64 expansion and JSON request overhead under Anthropic's request
size limit.

Use inline when:

- Files API is unavailable for the account or model;
- upload or file-reference operations repeatedly fail;
- temporary remote file creation is prohibited by the deployment policy; or
- a controlled comparison requires the inline transport.

## Selection

Default environment configuration:

```dotenv
ANTHROPIC_PDF_TRANSPORT=files-api
```

Primary CLI path:

```bash
PYTHONPATH=src python3.11 -m intake_extractor.drk_pdf referral.pdf
```

Explicit Files API selection:

```bash
PYTHONPATH=src python3.11 -m intake_extractor.drk_pdf \
  referral.pdf \
  --pdf-transport files-api
```

Explicit inline fallback:

```bash
PYTHONPATH=src python3.11 -m intake_extractor.drk_pdf \
  referral.pdf \
  --pdf-transport inline
```

Python callers may pass `pdf_transport="files-api"` or
`pdf_transport="inline"` to `extract_drk_from_pdf`. When omitted, the function
uses `ANTHROPIC_PDF_TRANSPORT`, falling back to `files-api`.

## Fallback behavior

Fallback is deliberate, not automatic. If Files API fails, rerun the same PDF
with `--pdf-transport inline`.

The extractor does not silently switch transports because doing so could:

- repeat nine expensive model calls;
- create ambiguous audit and timing results;
- hide a Files API permission or cleanup failure; and
- complicate attribution of extraction differences.

The source SHA-256 in `_manifest.json` can be used to confirm that a fallback
run processed the same PDF.

## Accuracy observations

Transport is not expected to alter PDF content, but model extraction can still
vary between runs.

In the validated Anita Rodriguez Hernandez comparison:

- inline returned one additional diagnosis by counting “History of abdominal
  hernia” separately on pages 3 and 9;
- Files API merged those repeated mentions into one diagnosis;
- inline returned “trial of Pepcid” as an additional medication even though
  Pepcid 20 mg was already present in the Home Medications list; and
- Files API correctly retained “trial of Pepcid” as plan language rather than
  a separate medication record.

For that document, Files API produced the more accurate patient-level record.
Other completed samples had matching clinical counts, so transport quality
must continue to be judged against page evidence rather than raw record totals.

## PHI and audit requirements

- Both transports send PHI to Anthropic.
- Do not commit PDFs, `_extraction.json`, card JSON, manifests, aligned intake
  bundles, or benchmark output.
- Local aligned-intake output is written atomically with mode `0600`.
- Files API uploads are temporary and deleted after each extraction.
- Keep `_manifest.json`; it records source hash, model, effort, passes, and
  transport without inventing DRK workflow state.
- Review extraction evidence and warnings before approving Monday or DRK
  handoffs.

## Troubleshooting

Files API upload/reference failure:

1. confirm the Anthropic API key and Files API access;
2. inspect the original error instead of repeatedly retrying a permanent
   permission failure;
3. use `--pdf-transport inline` when an immediate fallback is appropriate; and
4. preserve the source PDF and manifest so the fallback remains auditable.

Inline size rejection:

1. use the default Files API transport; or
2. split the source only when the resulting document boundaries remain
   clinically and administratively meaningful.

Deletion failure:

1. treat the run as failed even if extraction completed;
2. use the file ID from the error to remove the temporary upload; and
3. do not mark the referral complete until remote cleanup is confirmed.
