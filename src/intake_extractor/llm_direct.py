from __future__ import annotations

import base64
import json
import logging
import os
import re
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from pydantic import ValidationError

from .schema import ReferralIntake

# By default, send ALL pages. Use --max-pages to cap if desired.
DEFAULT_MAX_PAGES: int | None = None

logger = logging.getLogger(__name__)


MODEL_NAME = "claude-sonnet-5"
MAX_TOKENS = 4000


DIRECT_JSON_PROMPT = """You are extracting structured referral/intake data from heterogeneous healthcare PDFs (digital forms, scanned faxes, EHR printouts).

Return EXACTLY ONE JSON object that matches the schema below.
Do NOT include any commentary, markdown, or extra keys—JSON only.
The output MUST be strict RFC 8259 JSON:
- no code fences
- no trailing commas
- no comments
- all strings must be properly JSON-escaped (quotes/newlines/etc.)

Rules:
- Do not guess. Only extract what is explicitly present.
- If a field is missing, set it to null (or [] for lists).
- Keep strings as written unless formatting is explicitly requested.
- Keep `notes` concise (<= 500 characters). Do NOT paste long medication lists or full problem lists into notes.
- patient_dob: use "MM/DD/YYYY" only if unambiguous; otherwise copy as written.
- icd10_codes: return a flat list of ICD-10 codes only (no ICD-9).
- referral_date: clinical referral/order date, NOT the fax transmission timestamp.
- requested_services: include explicit services (checkboxes) AND implied orders/prescriptions; put quantity/schedule/special instructions into "instructions".
- notes: include clinically/admin relevant info that doesn’t fit other fields (allergies, emergency contact, homebound justification, etc.)

Schema (keys must match exactly):
{
  "patient_name": string|null,
  "patient_dob": string|null,
  "patient_sex": string|null,
  "patient_phone": string|null,
  "patient_address": string|null,
  "patient_mrn": string|null,

  "referring_provider_name": string|null,
  "referring_facility": string|null,
  "referring_phone": string|null,
  "referring_fax": string|null,

  "diagnosis_text": string|null,
  "icd10_codes": string[],

  "insurance_provider": string|null,
  "insurance_id": string|null,
  "insurance_group_number": string|null,

  "requested_services": [
    {
      "service": string|null,
      "frequency": string|null,
      "instructions": string|null
    }
  ],

  "referral_date": string|null,

  "notes": string|null,

  "source_file": string|null,
  "pages_used": number|null
}
"""


@dataclass(frozen=True)
class DirectExtractionOutput:
    referral: ReferralIntake
    raw_json: dict[str, Any]


class DirectExtractionError(RuntimeError):
    pass


@dataclass(frozen=True)
class ExtractedText:
    pages: list[str]


@dataclass(frozen=True)
class PageImage:
    page_number: int  # 1-indexed
    media_type: str
    base64_data: str


@dataclass(frozen=True)
class ExtractedImages:
    pages: list[PageImage]


def _build_client() -> Any:
    if not os.getenv("ANTHROPIC_API_KEY"):
        load_dotenv()
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise DirectExtractionError("ANTHROPIC_API_KEY is not set (env or .env)")

    from anthropic import Anthropic

    return Anthropic(api_key=api_key)


def _message_text_only() -> str:
    # Keep prompt in system to reduce chance of the model echoing it.
    return "Extract from the document I provide. Output JSON only."

def _message_fix_json(parse_error: str) -> str:
    return (
        "Your previous response was not valid JSON and could not be parsed. "
        f"Parser error: {parse_error}\n"
        "Re-output the same content as a single strict JSON object only."
    )


def _pdffonts_available() -> bool:
    try:
        subprocess.run(["pdffonts", "-h"], check=False, capture_output=True, text=True)
        return True
    except FileNotFoundError:
        return False


def _pdftoppm_available() -> bool:
    try:
        subprocess.run(["pdftoppm", "-h"], check=False, capture_output=True, text=True)
        return True
    except FileNotFoundError:
        return False


def has_text_layer(pdf_path: str | Path) -> bool:
    """
    Detect whether a PDF has a real text layer via `pdffonts`.
    """
    if not _pdffonts_available():
        raise DirectExtractionError("Poppler `pdffonts` not found. Install poppler (pdffonts/pdftoppm).")

    proc = subprocess.run(["pdffonts", str(pdf_path)], check=False, capture_output=True, text=True)
    out = proc.stdout or ""
    lines = [ln.strip() for ln in out.splitlines() if ln.strip()]
    if len(lines) <= 2:
        return False
    non_header = []
    for ln in lines:
        if re.match(r"^name\\s+type\\s+encoding", ln):
            continue
        if re.match(r"^-{5,}$", ln):
            continue
        non_header.append(ln)
    return len(non_header) > 0


def extract_text(pdf_path: str | Path, *, max_pages: int | None = DEFAULT_MAX_PAGES) -> ExtractedText:
    """
    Extract text from a PDF's text layer using pdfplumber.
    """
    import pdfplumber

    pages_text: list[str] = []
    with pdfplumber.open(str(pdf_path)) as pdf:
        limit = len(pdf.pages) if max_pages is None else min(len(pdf.pages), max_pages)
        for i in range(limit):
            pages_text.append(pdf.pages[i].extract_text() or "")
    return ExtractedText(pages=pages_text)


def _read_file_base64(path: Path) -> str:
    return base64.b64encode(path.read_bytes()).decode("ascii")


def extract_images(pdf_path: str | Path, *, max_pages: int | None = DEFAULT_MAX_PAGES, dpi: int = 150) -> ExtractedImages:
    """
    Rasterize pages to PNG via `pdftoppm` and return base64 images.

    IMPORTANT: This returns ALL selected pages as a single list so you can send
    the whole packet as ONE multi-image LLM request.
    """
    if not _pdftoppm_available():
        raise DirectExtractionError("Poppler `pdftoppm` not found. Install poppler (pdffonts/pdftoppm).")

    p = Path(pdf_path)
    with tempfile.TemporaryDirectory(prefix="intake_extractor_pdftoppm_") as td:
        out_prefix_path = Path(td) / "page"
        out_prefix = str(out_prefix_path)
        cmd: list[str] = [
            "pdftoppm",
            "-png",
            "-r",
            str(dpi),
            "-f",
            "1",
            str(p),
            out_prefix,
        ]
        if max_pages is not None:
            cmd[cmd.index(str(p)) : cmd.index(str(p))] = ["-l", str(max_pages)]
        subprocess.run(cmd, check=True, capture_output=True, text=True)

        produced = list(out_prefix_path.parent.glob(f"{out_prefix_path.name}-*.png"))
        if not produced:
            raise DirectExtractionError("pdftoppm produced no PNG files")

        def _page_num(png_path: Path) -> int:
            try:
                return int(png_path.stem.split("-")[-1])
            except Exception:
                return 10**9

        images: list[PageImage] = []
        for png_path in sorted(produced, key=_page_num):
            num = _page_num(png_path)
            images.append(PageImage(page_number=num, media_type="image/png", base64_data=_read_file_base64(png_path)))
        return ExtractedImages(pages=images)


def _parse_json_from_message(message: Any) -> dict[str, Any]:
    content = getattr(message, "content", None)
    if not isinstance(content, list):
        raise DirectExtractionError("Claude response did not contain a content list")

    text_parts: list[str] = []
    for block in content:
        btype = getattr(block, "type", None) or (block.get("type") if isinstance(block, dict) else None)
        if btype != "text":
            continue
        txt = getattr(block, "text", None) or (block.get("text") if isinstance(block, dict) else None)
        if isinstance(txt, str):
            text_parts.append(txt)

    if not text_parts:
        raise DirectExtractionError("Claude response had no text blocks")

    raw = "\n".join(text_parts).strip()
    # Some models may wrap JSON in fences; strip common wrappers.
    if raw.startswith("```"):
        raw = raw.strip("`")
        raw = raw.replace("json", "", 1).strip()
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as e:
        raise DirectExtractionError(f"Failed to parse JSON output: {e}") from None

    if not isinstance(parsed, dict):
        raise DirectExtractionError("Claude output JSON was not an object")
    return parsed


def _vision_user_content(extracted: ExtractedImages, *, pages_used: int) -> list[dict[str, Any]]:
    pages = extracted.pages[:pages_used]
    page_numbers = [p.page_number for p in pages]
    content: list[dict[str, Any]] = [
        {"type": "text", "text": f"INPUT TYPE: IMAGES\nPAGES PROVIDED (in order): {', '.join(map(str, page_numbers))}\n"}
    ]
    for p in pages:
        content.append(
            {
                "type": "image",
                "source": {"type": "base64", "media_type": p.media_type, "data": p.base64_data},
            }
        )
    return content


def _text_user_content(extracted: ExtractedText, *, pages_used: int) -> list[dict[str, Any]]:
    chunks: list[str] = [f"INPUT TYPE: TEXT\nPAGES PROVIDED: {pages_used}\n"]
    for i, page_text in enumerate(extracted.pages[:pages_used], start=1):
        chunks.append(f"\n--- PAGE {i} ---\n{page_text}\n")
    return [{"type": "text", "text": "\n".join(chunks)}]


def extract_direct_from_pdf(
    pdf_path: str | Path,
    *,
    prefer_text: bool | None = None,
    max_pages: int | None = DEFAULT_MAX_PAGES,
) -> DirectExtractionOutput:
    """
    Direct Claude call (JSON-only) using either extracted text or page images.

    This is intentionally NOT forced-tool-use; it relies on prompt discipline,
    then validates against the Pydantic model.
    """
    p = Path(pdf_path)
    pages_used: int
    user_content: list[dict[str, Any]]

    if prefer_text is None:
        # Auto-route: use text layer if present, otherwise vision.
        prefer_text = has_text_layer(p)

    if prefer_text:
        extracted_text = extract_text(p, max_pages=max_pages)
        pages_used = len(extracted_text.pages)
        user_content = _text_user_content(extracted_text, pages_used=pages_used)
    else:
        extracted_images = extract_images(p, max_pages=max_pages)
        pages_used = len(extracted_images.pages)
        user_content = _vision_user_content(extracted_images, pages_used=pages_used)

    client = _build_client()

    logger.info("Calling Claude direct JSON", extra={"source_file": p.name, "pages_used": pages_used})

    last_parse_error: str | None = None
    for attempt in (1, 2):
        lead_text = _message_text_only() if attempt == 1 else _message_fix_json(last_parse_error or "unknown")
        message = client.messages.create(
            model=MODEL_NAME,
            max_tokens=MAX_TOKENS,
            system=DIRECT_JSON_PROMPT,
            messages=[{"role": "user", "content": [{"type": "text", "text": lead_text}] + user_content}],
        )

        try:
            parsed = _parse_json_from_message(message)
        except DirectExtractionError as e:
            last_parse_error = str(e)
            if attempt == 1:
                continue
            raise

        try:
            referral = ReferralIntake.model_validate(parsed)
        except ValidationError as e:
            raise DirectExtractionError(f"Claude JSON did not validate: {e.__class__.__name__}") from None
        break

    # Set metadata deterministically.
    referral.source_file = p.name
    referral.pages_used = pages_used

    return DirectExtractionOutput(referral=referral, raw_json=parsed)


def write_direct_output(out: DirectExtractionOutput, out_path: str | Path) -> None:
    Path(out_path).write_text(json.dumps(out.referral.model_dump(mode="json"), indent=2, sort_keys=True))


def extract_folder_to_expected(
    input_dir: str | Path,
    *,
    out_dir: str | Path = "out/benchmarks",
    max_pages: int = DEFAULT_MAX_PAGES,
) -> None:
    """
    Generate `*.expected.json` files for every PDF in a folder.
    """
    in_dir = Path(input_dir)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    pdfs = sorted([p for p in in_dir.iterdir() if p.suffix.lower() == ".pdf"])
    ok = 0
    combined_path = out / "_combined.expected.jsonl"
    with combined_path.open("w", encoding="utf-8") as combined:
        for pdf in pdfs:
            try:
                result = extract_direct_from_pdf(pdf, prefer_text=None, max_pages=max_pages)
                out_path = out / f"{pdf.stem}.expected.json"
                write_direct_output(result, out_path)
                combined.write(json.dumps(result.referral.model_dump(mode="json"), sort_keys=True) + "\n")
                ok += 1
                print(f"OK  | {pdf.name} | pages_used={result.referral.pages_used}")
            except Exception as e:
                # PHI-safe: don't print model output, only the error class.
                print(f"FAIL| {pdf.name} | err={type(e).__name__}")
    print(f"Expected generation complete: {ok}/{len(pdfs)} succeeded. Outputs in {out}")


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Direct Claude JSON extraction (no tool forcing).")
    parser.add_argument("pdf_path", type=str, help="Path to a single PDF")
    parser.add_argument(
        "--max-pages",
        type=int,
        default=DEFAULT_MAX_PAGES,
        help="Optional: cap pages sent (default: all pages)",
    )
    parser.add_argument(
        "--prefer-text",
        action="store_true",
        help="Force text extraction (otherwise auto-detect via pdffonts)",
    )
    parser.add_argument(
        "--write-out",
        type=str,
        default=None,
        help="Optional: also write JSON to this directory as <pdf_stem>.json",
    )
    args = parser.parse_args()

    pdf = Path(args.pdf_path)
    if not pdf.exists():
        raise SystemExit(f"File not found: {pdf}")
    if pdf.is_dir():
        raise SystemExit(f"Expected a PDF file, got a directory: {pdf}")

    result = extract_direct_from_pdf(pdf, prefer_text=(True if args.prefer_text else None), max_pages=args.max_pages)
    # Print the validated JSON to stdout.
    print(json.dumps(result.referral.model_dump(mode="json"), indent=2, sort_keys=True))

    if args.write_out:
        out_dir = Path(args.write_out)
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / (pdf.stem + ".json")
        write_direct_output(result, out_path)
        logger.info("Wrote output JSON", extra={"path": str(out_path)})


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()

