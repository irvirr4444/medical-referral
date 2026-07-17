"""Field-targeted second-pass review configuration.

Keeps weak-field focus, prompt guidance, and patch tiers in one place so
review prompts and local patch policy stay aligned without hardcoding
document-specific rules.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


PatchTier = Literal["sensitive", "standard", "flexible"]


# Highest-weight / historically weak extraction fields. The second pass
# prioritizes these instead of treating every schema key equally.
TARGETED_REVIEW_FIELDS: tuple[str, ...] = (
    "requested_services",
    "diagnosis_text",
    "referring_provider_name",
    "referring_facility",
    "referring_phone",
    "referring_fax",
    "patient_address",
    "referral_date",
)


@dataclass(frozen=True)
class FieldReviewPolicy:
    field: str
    tier: PatchTier
    base_threshold: float
    # Extra confidence relief when local heuristics mark the field suspicious.
    suspicious_bonus: float
    # Extra confidence demand when replacing a non-empty value (not just filling null).
    replacement_penalty: float
    # Floor after bonuses so we never accept very low-confidence patches.
    min_threshold: float
    guidance: str


FIELD_POLICIES: dict[str, FieldReviewPolicy] = {
    "patient_name": FieldReviewPolicy(
        field="patient_name",
        tier="sensitive",
        base_threshold=0.97,
        suspicious_bonus=0.02,
        replacement_penalty=0.03,
        min_threshold=0.9,
        guidance="Verify legal/preferred name against demographics only. Do not patch from cover sheets or emergency contacts.",
    ),
    "patient_dob": FieldReviewPolicy(
        field="patient_dob",
        tier="sensitive",
        base_threshold=0.97,
        suspicious_bonus=0.02,
        replacement_penalty=0.03,
        min_threshold=0.9,
        guidance="Confirm DOB digits carefully. Prefer MM/DD/YYYY when unambiguous.",
    ),
    "insurance_id": FieldReviewPolicy(
        field="insurance_id",
        tier="sensitive",
        base_threshold=0.97,
        suspicious_bonus=0.02,
        replacement_penalty=0.03,
        min_threshold=0.9,
        guidance="Member/policy IDs must match the insurance section exactly. Prefer no patch over a guessed character.",
    ),
    "requested_services": FieldReviewPolicy(
        field="requested_services",
        tier="flexible",
        base_threshold=0.78,
        suspicious_bonus=0.08,
        replacement_penalty=0.0,
        min_threshold=0.7,
        guidance=(
            "Include only explicit referral/order items: therapies, skilled nursing, wound care, DME, "
            "labs/tests/imaging ordered in the packet, and discharge medications clearly prescribed "
            "as active follow-up. Exclude med history/profiles, staffing, follow-up appointments, "
            "admin routing, and vague narrative. Keep distinct ordered items as separate list rows. "
            "Propose the full corrected list when patching."
        ),
    ),
    "diagnosis_text": FieldReviewPolicy(
        field="diagnosis_text",
        tier="flexible",
        base_threshold=0.9,
        suspicious_bonus=0.03,
        replacement_penalty=0.05,
        min_threshold=0.85,
        guidance=(
            "Prefer concise reason-for-referral / assessment wording. "
            "When multiple admitting/primary diagnoses are listed, keep that set; "
            "trim duplicated or massively expanded narrative rows rather than collapsing to only the primary diagnosis. "
            "Avoid dumping raw ICD code strings as the diagnosis text."
        ),
    ),
    "referring_provider_name": FieldReviewPolicy(
        field="referring_provider_name",
        tier="flexible",
        base_threshold=0.8,
        suspicious_bonus=0.07,
        replacement_penalty=0.02,
        min_threshold=0.7,
        guidance=(
            "Use the ordering/referring clinician only. Do not use PCP, attending, cover-sheet sender, "
            "or emergency contact unless the document clearly marks them as the referrer/orderer. "
            "Clear to null when only a facility is present."
        ),
    ),
    "referring_facility": FieldReviewPolicy(
        field="referring_facility",
        tier="flexible",
        base_threshold=0.8,
        suspicious_bonus=0.07,
        replacement_penalty=0.02,
        min_threshold=0.7,
        guidance=(
            "Use the organization originating/sending the referral. Check fax headers and cover sheets. "
            "Never store a street address here; if only an address is present, set null."
        ),
    ),
    "referring_phone": FieldReviewPolicy(
        field="referring_phone",
        tier="flexible",
        base_threshold=0.78,
        suspicious_bonus=0.06,
        replacement_penalty=0.0,
        min_threshold=0.7,
        guidance="Use referring/ordering contact phone near the referrer block, not patient/PCP/emergency/unit numbers unless clearly labeled as referring contact.",
    ),
    "referring_fax": FieldReviewPolicy(
        field="referring_fax",
        tier="flexible",
        base_threshold=0.78,
        suspicious_bonus=0.06,
        replacement_penalty=0.0,
        min_threshold=0.7,
        guidance="Use referring/facility fax from the referrer or fax header block, not unrelated clinic/unit faxes.",
    ),
    "patient_address": FieldReviewPolicy(
        field="patient_address",
        tier="flexible",
        base_threshold=0.82,
        suspicious_bonus=0.06,
        replacement_penalty=0.02,
        min_threshold=0.72,
        guidance=(
            "Choose one active/current patient location. Prefer discharge/recuperative destinations over "
            "crossed-out prior addresses. Do not invent unit numbers."
        ),
    ),
    "referral_date": FieldReviewPolicy(
        field="referral_date",
        tier="flexible",
        base_threshold=0.85,
        suspicious_bonus=0.05,
        replacement_penalty=0.02,
        min_threshold=0.75,
        guidance="Use clinical referral/order/signature date. Do NOT use fax transmission timestamps.",
    ),
}

DEFAULT_FIELD_POLICY = FieldReviewPolicy(
    field="*",
    tier="standard",
    base_threshold=0.9,
    suspicious_bonus=0.03,
    replacement_penalty=0.03,
    min_threshold=0.8,
    guidance="Only patch when the PDF evidence is explicit and the replacement is concrete.",
)


def get_field_policy(field: str) -> FieldReviewPolicy:
    return FIELD_POLICIES.get(field, DEFAULT_FIELD_POLICY)


def build_targeted_field_guidance() -> str:
    lines = ["Priority fields to verify against the PDF:"]
    for field in TARGETED_REVIEW_FIELDS:
        policy = get_field_policy(field)
        lines.append(f"- {field}: {policy.guidance}")
    return "\n".join(lines)
