from __future__ import annotations

import argparse
import json
import logging
from dataclasses import dataclass
from pathlib import Path

from pydantic import ValidationError

from .pdf_inputs import PDF_INPUT_MODE_CHOICES, PdfInputMode
from .postprocess import normalize_referral
from .review import load_candidate_json, review_prediction
from .review_audit import AuditDocument, build_document_audit, write_document_audit, write_folder_audit_summary
from .review_patch import AppliedPatch, apply_review_patches_with_decisions
from .review_schema import PredictionReview
from .review_signals import FieldSignal
from .review_targets import TARGETED_REVIEW_FIELDS
from .schema import ReferralIntake


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CorrectionResult:
    referral: ReferralIntake
    review: PredictionReview
    signals: list[FieldSignal]
    applied_patches: list[AppliedPatch]
    audit: AuditDocument


def correct_prediction(
    pdf_path: str | Path,
    prediction_path: str | Path,
    *,
    input_mode: PdfInputMode = "auto",
    max_pages: int | None = None,
) -> ReferralIntake:
    return correct_prediction_detailed(
        pdf_path,
        prediction_path,
        input_mode=input_mode,
        max_pages=max_pages,
    ).referral


def correct_prediction_detailed(
    pdf_path: str | Path,
    prediction_path: str | Path,
    *,
    input_mode: PdfInputMode = "auto",
    max_pages: int | None = None,
) -> CorrectionResult:
    candidate_json = load_candidate_json(prediction_path)
    review, signals = review_prediction(
        pdf_path,
        prediction_path,
        input_mode=input_mode,
        max_pages=max_pages,
        candidate_json=candidate_json,
    )
    suspicious = {signal.field for signal in signals}

    try:
        patched_json, applied_patches, decisions = apply_review_patches_with_decisions(
            candidate_json,
            review,
            suspicious_fields=suspicious,
        )
        referral = ReferralIntake.model_validate(patched_json)
    except ValidationError as exc:
        raise RuntimeError(f"Corrected JSON did not validate: {exc.__class__.__name__}") from None

    if applied_patches:
        fields = ", ".join(sorted(patch.field for patch in applied_patches))
        logger.info("Applied %s review patch(es) to %s: %s", len(applied_patches), Path(pdf_path).name, fields)

    normalized = normalize_referral(referral)
    reviewed_fields = (
        [check.field for check in review.field_checks]
        if review.field_checks
        else list(TARGETED_REVIEW_FIELDS)
    )
    audit = build_document_audit(
        source_file=Path(pdf_path).name,
        candidate=candidate_json,
        review=review,
        decisions=decisions,
        signals=signals,
        reviewed_fields=reviewed_fields,
    )
    return CorrectionResult(
        referral=normalized,
        review=review,
        signals=signals,
        applied_patches=applied_patches,
        audit=audit,
    )


def correct_folder(
    pdf_dir: str | Path,
    predictions_dir: str | Path,
    *,
    out_dir: str | Path,
    audit_dir: str | Path | None = None,
    input_mode: PdfInputMode = "auto",
    max_pages: int | None = None,
) -> None:
    pdf_root = Path(pdf_dir)
    predictions_root = Path(predictions_dir)
    output_root = Path(out_dir)
    audit_root = Path(audit_dir) if audit_dir is not None else output_root / "audit"
    output_root.mkdir(parents=True, exist_ok=True)
    audit_root.mkdir(parents=True, exist_ok=True)

    ok = 0
    audits: list[AuditDocument] = []
    pdfs = sorted(pdf_root.glob("*.pdf"))
    for pdf in pdfs:
        prediction_path = predictions_root / f"{pdf.stem}.json"
        if not prediction_path.exists():
            logger.warning("Missing prediction JSON", extra={"pdf": pdf.name})
            continue

        try:
            result = correct_prediction_detailed(
                pdf,
                prediction_path,
                input_mode=input_mode,
                max_pages=max_pages,
            )
        except Exception:
            logger.exception("Review/correct failed for %s", pdf.name)
            continue

        out_path = output_root / f"{pdf.stem}.json"
        out_path.write_text(
            json.dumps(result.referral.model_dump(mode="json"), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        write_document_audit(audit_root, pdf.stem, result.review, result.audit)
        audits.append(result.audit)
        ok += 1

    write_folder_audit_summary(audit_root, audits)
    print(f"Corrected predictions complete: {ok}/{len(pdfs)} succeeded. Outputs in {output_root}")
    print(f"Wrote review audit artifacts to {audit_root}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Correct extracted JSONs using a reviewer LLM against the source PDFs.")
    parser.add_argument("pdf_dir", type=Path, help="Directory containing source PDFs")
    parser.add_argument("predictions_dir", type=Path, help="Directory containing extracted JSONs")
    parser.add_argument("--out-dir", type=Path, required=True, help="Directory to write corrected JSON outputs")
    parser.add_argument(
        "--audit-dir",
        type=Path,
        default=None,
        help="Directory for review/audit sidecars (default: <out-dir>/audit)",
    )
    parser.add_argument(
        "--input-mode",
        choices=PDF_INPUT_MODE_CHOICES,
        default="auto",
        help="PDF input mode for reviewer/corrector: auto, text, image, or hybrid",
    )
    parser.add_argument("--max-pages", type=int, default=None, help="Optional page cap for the reviewer/corrector")
    args = parser.parse_args()

    correct_folder(
        args.pdf_dir,
        args.predictions_dir,
        out_dir=args.out_dir,
        audit_dir=args.audit_dir,
        input_mode=args.input_mode,
        max_pages=args.max_pages,
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
