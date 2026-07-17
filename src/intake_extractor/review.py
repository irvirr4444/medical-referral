from __future__ import annotations

import argparse
import csv
import json
import logging
from pathlib import Path

from .anthropic_json import AnthropicJsonError, build_client, call_model_for_json
from .pdf_inputs import PDF_INPUT_MODE_CHOICES, PdfInputMode, build_pdf_input_payload
from .review_schema import PredictionReview
from .review_signals import FieldSignal, collect_field_signals, format_signals_for_prompt
from .review_targets import TARGETED_REVIEW_FIELDS, build_targeted_field_guidance


logger = logging.getLogger(__name__)

MODEL_NAME = "claude-sonnet-5"
MAX_TOKENS = 8000


REVIEW_JSON_PROMPT = """You are auditing a structured extraction produced from a healthcare referral/intake PDF.

You will receive:
1. A candidate JSON extraction.
2. Local suspicious-field heuristics for the candidate.
3. The original PDF content.

Your job is to compare the candidate JSON against the source PDF and propose controlled field patches for real mistakes.

Return EXACTLY ONE JSON object with this schema:
{
  "source_file": string|null,
  "overall_verdict": "pass"|"minor_issues"|"major_issues",
  "summary": string,
  "correct_highlights": string[],
  "field_checks": [
    {"field": string, "status": "ok"|"issue"|"uncertain", "note": string|null}
  ],
  "issues": [
    {
      "field": string,
      "severity": "minor"|"major",
      "predicted_value": any,
      "suggest_patch": boolean,
      "proposed_value": any,
      "confidence": number,
      "expected_value": string|null,
      "problem": string,
      "evidence": string|null
    }
  ]
}

Rules:
- This is a TARGETED review. Prioritize the priority fields listed below. Do not broadly rewrite the whole record.
- You MUST include one field_checks entry for EVERY priority field below, after comparing that field to the PDF.
- Do NOT use overall_verdict="pass" if any priority field_checks status is "issue".
- Review the candidate against the PDF. Do not produce a new full extraction object.
- Only list real mistakes, omissions, or likely mismatches supported by the PDF.
- When a priority-field mistake is clear and the correct value is readable in the PDF, you MUST set suggest_patch=true, set proposed_value to the concrete replacement, and set confidence >= 0.85.
- Use actual schema field names whenever possible.
- If the problem is inside requested_services, set field to "requested_services" and propose the FULL corrected list when suggest_patch=true.
- Use "major" for patient identity, insurer/member ID, referring contacts, diagnosis, referral date, or requested-service mistakes.
- Use "minor" for formatting or less material note/detail issues.
- If you are unsure of the exact replacement value, set suggest_patch=false and proposed_value=null, and mark field_checks status="uncertain".
- confidence must be a number from 0.0 to 1.0 representing your confidence in the proposed patch, not just the existence of an issue.
- If the correct action is to clear a field, set suggest_patch=true and proposed_value=null.
- For non-priority fields, only report clear major factual errors.
- Keep summary concise and specific.
- Cite short PDF evidence for every proposed patch.

- diagnosis_text: keep the clinically relevant diagnosis set from the referral/assessment. Trim duplicated/expanded narrative, but do not collapse a multi-diagnosis admitting list down to only the primary diagnosis when several diagnoses are clearly listed.

- referring_phone and referring_fax are frequently taken from the wrong section (unit phone, patient phone, PCP, fax header noise). Re-verify against the ordering/referring block.
- referral_date must be the clinical referral/order/signature date, never a fax transmission timestamp or datetime stamp.

requested_services vigilance:
- Build the ordered-item set from explicit checkboxes, order lines, therapy disciplines, DME, wound-care orders, labs/tests, and discharge meds clearly prescribed as active follow-up.
- Remove follow-up appointments, admin routing, cover-sheet text, and medication history/profile rows that are not ordered referral items.
- Prefer a corrected full list over leaving an incomplete or polluted list unchanged.

""" + build_targeted_field_guidance()


def _message_review(candidate_json: dict[str, object], signals: list[FieldSignal]) -> str:
    priority_snapshot = {
        field: candidate_json.get(field) for field in TARGETED_REVIEW_FIELDS if field in candidate_json
    }
    checklist = ", ".join(TARGETED_REVIEW_FIELDS)
    return (
        "Review this candidate extraction against the source PDF.\n"
        f"Complete field_checks for: {checklist}.\n"
        "Focus on the priority fields and local heuristic flags.\n"
        "Propose concrete patches when PDF evidence is explicit.\n\n"
        f"{format_signals_for_prompt(signals)}\n\n"
        f"PRIORITY FIELD SNAPSHOT:\n{json.dumps(priority_snapshot, indent=2, ensure_ascii=False, sort_keys=True)}\n\n"
        f"CANDIDATE JSON:\n{json.dumps(candidate_json, indent=2, ensure_ascii=False, sort_keys=True)}"
    )


def load_candidate_json(prediction_path: str | Path) -> dict[str, object]:
    prediction_file = Path(prediction_path)
    return json.loads(prediction_file.read_text(encoding="utf-8"))


def build_pdf_user_content(
    pdf_path: str | Path,
    *,
    input_mode: PdfInputMode = "auto",
    max_pages: int | None = None,
) -> list[dict[str, object]]:
    return build_pdf_input_payload(pdf_path, input_mode=input_mode, max_pages=max_pages).user_content


def review_prediction(
    pdf_path: str | Path,
    prediction_path: str | Path,
    *,
    input_mode: PdfInputMode = "auto",
    max_pages: int | None = None,
    candidate_json: dict[str, object] | None = None,
) -> tuple[PredictionReview, list[FieldSignal]]:
    pdf = Path(pdf_path)
    candidate = candidate_json if candidate_json is not None else load_candidate_json(prediction_path)
    signals = collect_field_signals(candidate)
    payload = build_pdf_input_payload(pdf, input_mode=input_mode, max_pages=max_pages)
    user_content = payload.user_content

    client = build_client()
    try:
        parsed = call_model_for_json(
            client,
            model_name=MODEL_NAME,
            max_tokens=MAX_TOKENS,
            system_prompt=REVIEW_JSON_PROMPT,
            user_content=user_content,
            lead_text=_message_review(candidate, signals),
        )
    except AnthropicJsonError as exc:
        raise RuntimeError(str(exc)) from None

    review = PredictionReview.model_validate(parsed)
    if review.source_file is None:
        review.source_file = pdf.name
    return review, signals


def review_folder(
    pdf_dir: str | Path,
    predictions_dir: str | Path,
    *,
    out_dir: str | Path,
    input_mode: PdfInputMode = "auto",
    max_pages: int | None = None,
) -> None:
    pdf_root = Path(pdf_dir)
    predictions_root = Path(predictions_dir)
    output_root = Path(out_dir)
    output_root.mkdir(parents=True, exist_ok=True)

    pdfs = sorted(pdf_root.glob("*.pdf"))
    issue_rows: list[dict[str, object]] = []
    summary_lines = ["# Prediction Review", ""]

    for pdf in pdfs:
        prediction_path = predictions_root / f"{pdf.stem}.json"
        if not prediction_path.exists():
            logger.warning("Missing prediction JSON", extra={"pdf": pdf.name})
            continue

        review, signals = review_prediction(pdf, prediction_path, input_mode=input_mode, max_pages=max_pages)
        out_path = output_root / f"{pdf.stem}.review.json"
        payload = review.model_dump(mode="json")
        payload["suspicious_fields"] = [
            {"field": signal.field, "reason": signal.reason} for signal in signals
        ]
        out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

        summary_lines.append(f"## {pdf.name}")
        summary_lines.append(f"- Verdict: `{review.overall_verdict}`")
        summary_lines.append(f"- Summary: {review.summary}")
        if signals:
            summary_lines.append(
                "- Suspicious fields: "
                + ", ".join(f"`{signal.field}` ({signal.reason})" for signal in signals)
            )
        if review.correct_highlights:
            summary_lines.append(f"- Correct highlights: {'; '.join(review.correct_highlights)}")
        if review.issues:
            for issue in review.issues:
                summary_lines.append(
                    f"- `{issue.field}` [{issue.severity}]: {issue.problem}"
                    + (f" Expected: {issue.expected_value}." if issue.expected_value else "")
                )
                issue_rows.append(
                    {
                        "pdf_name": pdf.name,
                        "verdict": review.overall_verdict,
                        "field": issue.field,
                        "severity": issue.severity,
                        "problem": issue.problem,
                        "predicted_value": json.dumps(issue.predicted_value, ensure_ascii=False, sort_keys=True),
                        "suggest_patch": issue.suggest_patch,
                        "proposed_value": json.dumps(issue.proposed_value, ensure_ascii=False, sort_keys=True),
                        "confidence": issue.confidence,
                        "expected_value": issue.expected_value or "",
                        "evidence": issue.evidence or "",
                    }
                )
        else:
            summary_lines.append("- No material issues found.")
        summary_lines.append("")

    (output_root / "summary.md").write_text("\n".join(summary_lines), encoding="utf-8")
    _write_issue_csv(output_root / "issues.csv", issue_rows)


def _write_issue_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Review extracted JSONs against their source PDFs.")
    parser.add_argument("pdf_dir", type=Path, help="Directory containing source PDFs")
    parser.add_argument("predictions_dir", type=Path, help="Directory containing extracted JSONs")
    parser.add_argument("--out-dir", type=Path, required=True, help="Directory to write review outputs")
    parser.add_argument(
        "--input-mode",
        choices=PDF_INPUT_MODE_CHOICES,
        default="auto",
        help="PDF input mode for reviewer: auto, text, image, or hybrid",
    )
    parser.add_argument("--max-pages", type=int, default=None, help="Optional page cap for the reviewer")
    args = parser.parse_args()

    review_folder(
        args.pdf_dir,
        args.predictions_dir,
        out_dir=args.out_dir,
        input_mode=args.input_mode,
        max_pages=args.max_pages,
    )
    print(f"Wrote review outputs to {args.out_dir}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
