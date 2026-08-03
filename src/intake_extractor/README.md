## `intake_extractor` (what it does today)

This package extracts a normalized `ReferralIntake` JSON from heterogeneous healthcare PDFs (referral forms, faxed packets, EHR printouts).

It is designed to be **loss-tolerant**: most fields are optional because many source layouts simply do not contain them.

## Output schema (`ReferralIntake`)

Defined in `schema.py`.

- **Patient identity & contact (document-derived)**
  - `patient_name`
  - `patient_dob` (kept as written when ambiguous; normalized in `postprocess.py` when it matches a simple date)
  - `patient_sex`
  - `patient_phone`
  - `patient_address`
  - `patient_mrn` (MRN / patient id / account # — whichever the document uses as the patient identifier)

- **Referring source (document-derived)**
  - `referring_provider_name` (ordering/referring clinician only, when explicit)
  - `referring_facility` (originating/sending organization; **not** a street address)
  - `referring_phone`
  - `referring_fax`

- **Clinical / insurance / services (document-derived)**
  - `diagnosis_text`
  - `icd10_codes[]`
  - `insurance_provider`, `insurance_id`, `insurance_group_number`
  - `requested_services[]` (`service`, `frequency`, `instructions`)

- **Dates**
  - `referral_date`: the **clinical order/referral/signature date** when present.
    - **Do not** use fax transmission timestamps for this field.

- **Other**
  - `notes`: short leftovers that do not fit structured fields.

- **Extraction metadata (not from the document itself)**
  - `source_file`: filename
  - `pages_used`: how many pages were sent to the model

## Input modes (how we read PDFs)

`build_pdf_input_payload(...)` in `pdf_inputs.py` supports:

- **`auto`**: chooses `text` if the PDF has a meaningful text layer; otherwise `image`.
- **`text`**: uses `pdfplumber` text extraction.
- **`image`**: renders pages with `pdftoppm` and sends images.
- **`hybrid`**: sends both extracted text + rendered images for the same pages.

### Recommended policy (profiles)

For most callers, prefer **profiles** (a higher-level policy layer) instead of hardcoding an input mode:

- **`balanced`** → `auto` (default; good for mixed traffic)
- **`accurate`** → `hybrid` (best correctness; higher token/cost)
- **`fax`** → `image` (best for scanned faxes/packets)

CLI examples:

```bash
# default cost-aware behavior
PYTHONPATH=src python3.11 -m intake_extractor.llm.direct "samples/EC - REFERRAL FORM.pdf" --profile balanced

# highest accuracy (text + images)
PYTHONPATH=src python3.11 -m intake_extractor.llm.direct "samples/EC - REFERRAL FORM.pdf" --profile accurate

# known scanned fax packet
PYTHONPATH=src python3.11 -m intake_extractor.llm.direct "samples/fax20260710-1422744-nkqbp2.pdf" --profile fax
```

### Important: “text layer” detection

`pdf.payloads.has_text_layer(...)` currently uses Poppler `pdffonts` as a heuristic: if the PDF contains fonts, `auto` will treat it as a text PDF.

Some scanned faxes include tiny text artifacts (headers/banners) that can trigger `pdffonts` even when the patient data is image-only. If you see missing fields when using `balanced`/`auto` on faxes, use `--profile fax` (forces image) or `--profile accurate` (hybrid) instead.

## Main entrypoint

`llm/direct.py` → `extract_direct_from_pdf(...)`

Pipeline highlights:
- Enforces strict JSON output matching `ReferralIntake`.
- Optional second-pass “repair” for:
  - header / sender-block fields (common on faxes)
  - missing referring contacts
  - requested-services extraction (avoid “med list == requested services”)
- Normalizes the final record in `core.postprocess.normalize_referral(...)`.

## Focused Monday-only contract

`monday_pdf.py` extracts the small `MondayPdfIntakeContract` defined in
`monday_pdf_schema.py`. It uses the native PDF and exactly two Opus calls:

1. focused extraction of all PDF facts used by the Master Sheet intake path;
2. source verification and correction of the first candidate.

The focused facts cover patient identity/contact, separate referring and current
HH/hospice agencies, agency contacts, place of service, explicit wound-order
presence, clinical summary, insurance policies, and clinical referral/order date.
`sent_by` must be supplied by the caller because it identifies the info-box/email
workflow actor and is not a document fact. The contract can be converted to the
existing `ReferralIntake` planner shape with `monday_pdf.to_referral_intake(...)`.

This path intentionally excludes complete diagnosis and medication histories.
Use `drk_pdf.py` when building the full DRK-compatible record.

## Optional reviewer (QA)

`review_tools/review.py` compares a candidate JSON against the PDF and proposes focused patches with evidence.
It prioritizes historically weak fields (see `review_tools/targets.py`).

