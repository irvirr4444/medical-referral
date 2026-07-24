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

### Important: “text layer” detection

`pdf_payloads.has_text_layer(...)` first checks `pdffonts`, then verifies there is a **minimum amount of extractable alphanumeric text**.
This avoids misclassifying scanned faxes that have tiny header artifacts as “text PDFs”.

## Main entrypoint

`llm_direct.py` → `extract_direct_from_pdf(...)`

Pipeline highlights:
- Enforces strict JSON output matching `ReferralIntake`.
- Optional second-pass “repair” for:
  - header / sender-block fields (common on faxes)
  - missing referring contacts
  - requested-services extraction (avoid “med list == requested services”)
- Normalizes the final record in `postprocess.normalize_referral(...)`.

## Optional reviewer (QA)

`review.py` compares a candidate JSON against the PDF and proposes focused patches with evidence.
It prioritizes historically weak fields (see `review_targets.py`).

