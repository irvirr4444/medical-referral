from __future__ import annotations

from pathlib import Path

from intake_extractor.aligned_intake import (
    build_aligned_intake_bundle,
    to_drk_create_draft_from_canonical,
    to_master_sheet_referral_from_canonical,
)
from intake_extractor.canonical_referral import (
    CanonicalAddress,
    CanonicalClinical,
    CanonicalFieldQuality,
    CanonicalHomeHealthOrHospice,
    CanonicalInsurance,
    CanonicalName,
    CanonicalOrganization,
    CanonicalPatient,
    CanonicalPhone,
    CanonicalReferral,
    CanonicalReferralSource,
    CanonicalSource,
    _validate_structured_output,
    extract_referral_pdf,
    write_canonical_referral,
)


SAMPLE_PDF = Path("samples/BUTLER, ALVA demo.pdf")


def _record() -> CanonicalReferral:
    quality = {
        path: CanonicalFieldQuality(status="present", confidence="high", evidence_pages=[1])
        for path in (
            "patient.name",
            "patient.date_of_birth",
            "patient.phones",
            "patient.address",
            "home_health_or_hospice",
            "clinical",
            "insurances",
        )
    }
    return CanonicalReferral(
        referral_id="ref_candidate",
        source=CanonicalSource(file_name="candidate.pdf", pdf_sha256="candidate"),
        patient=CanonicalPatient(
            name=CanonicalName(first="Jane", last="Doe", full="Jane Doe"),
            date_of_birth="1950-01-02",
            sex_or_gender="Female",
            ssn="111-22-3333",
            phones=[CanonicalPhone(number="555-555-0100")],
            email="jane@example.com",
            address=CanonicalAddress(
                line_1="1 Main St",
                city="Tampa",
                state="FL",
                postal_code="33601",
            ),
        ),
        referral_source=CanonicalReferralSource(
            organization=CanonicalOrganization(
                name="Referral Clinic",
                contact_name="Case Manager",
                phone="555-0101",
                email="case@example.com",
            ),
            provider_name="Dr Smith",
            referral_or_order_date="2026-08-01",
        ),
        home_health_or_hospice=CanonicalHomeHealthOrHospice(
            organization=CanonicalOrganization(name="Current Home Health")
        ),
        clinical=CanonicalClinical(
            summary="Stage 3 sacral wound requiring skilled wound care.",
            wound_order_included=True,
        ),
        insurances=[
            CanonicalInsurance(
                payer_name="Medicare",
                policy_number="ABC123",
                insurance_type="Primary",
            )
        ],
        field_quality=quality,
    )


def test_unknown_nested_extractor_fields_are_removed_without_losing_referral() -> None:
    payload = _record().model_dump(mode="json")
    payload["insurances"][0]["insurance_type_note"] = None
    payload["patient"]["unsupported_patient_note"] = "not in schema"

    validated = _validate_structured_output(CanonicalReferral, payload)

    assert validated.insurances[0].payer_name == "Medicare"
    serialized = validated.model_dump(mode="json")
    assert "insurance_type_note" not in serialized["insurances"][0]
    assert "unsupported_patient_note" not in serialized["patient"]
    assert any(
        "insurances.0.insurance_type_note" in warning
        for warning in validated.warnings
    )


class _Message:
    def __init__(self, output: CanonicalReferral) -> None:
        self.parsed_output = output


class _Stream:
    def __init__(self, output: CanonicalReferral) -> None:
        self.output = output

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def get_final_message(self):
        return _Message(self.output)


class _Messages:
    def __init__(self, outputs: list[CanonicalReferral]) -> None:
        self.outputs = outputs
        self.calls: list[dict] = []

    def stream(self, **kwargs):
        self.calls.append(kwargs)
        return _Stream(self.outputs.pop(0))


class _Client:
    def __init__(self, outputs: list[CanonicalReferral]) -> None:
        self.messages = _Messages(outputs)


class _Files:
    def __init__(self) -> None:
        self.upload_count = 0
        self.deleted: list[str] = []

    def upload(self, **_kwargs):
        self.upload_count += 1
        return type("Uploaded", (), {"id": "file_test"})()

    def delete(self, file_id: str):
        self.deleted.append(file_id)


class _FilesClient:
    def __init__(self, outputs: list[CanonicalReferral]) -> None:
        self.messages = _Messages([])
        self.beta = type("Beta", (), {})()
        self.beta.messages = _Messages(outputs)
        self.beta.files = _Files()


def test_canonical_extractor_uses_exactly_two_calls_and_owns_source_metadata() -> None:
    client = _Client([_record(), _record()])

    result = extract_referral_pdf(
        SAMPLE_PDF,
        email_id="mail-1",
        attachment_id="attachment-1",
        client=client,
        pdf_transport="inline",
        sleep=lambda _delay: None,
    )

    assert len(client.messages.calls) == 2
    assert result.referral_id.startswith("ref_")
    assert result.source.email_id == "mail-1"
    assert result.source.attachment_id == "attachment-1"
    assert result.source.pdf_sha256 != "candidate"
    assert result.source.extraction is not None
    assert result.source.extraction.primary_model == "claude-opus-5"
    assert result.source.extraction.pass_models == ["claude-opus-5", "claude-opus-5"]


def test_default_files_api_uploads_once_and_still_uses_two_calls() -> None:
    client = _FilesClient([_record(), _record()])

    extract_referral_pdf(SAMPLE_PDF, client=client, sleep=lambda _delay: None)

    assert client.beta.files.upload_count == 1
    assert client.beta.files.deleted == ["file_test"]
    assert len(client.beta.messages.calls) == 2
    assert all(call["betas"] == ["files-api-2025-04-14"] for call in client.beta.messages.calls)


class _FlakyMessages:
    def __init__(self, outputs: list[CanonicalReferral], fail_times: int) -> None:
        self.outputs = outputs
        self.fail_times = fail_times
        self.calls: list[dict] = []

    def stream(self, **kwargs):
        self.calls.append(kwargs)
        if self.fail_times > 0:
            self.fail_times -= 1

            class Overloaded(Exception):
                status_code = 529
                body = {"error": {"type": "overloaded_error", "message": "Overloaded"}}

            raise Overloaded("Overloaded")
        return _Stream(self.outputs.pop(0))


class _FallbackClient:
    def __init__(self, outputs: list[CanonicalReferral], fail_primary: int) -> None:
        self.messages = _FlakyMessages(outputs, fail_primary)


def test_canonical_extractor_falls_back_after_primary_capacity_errors() -> None:
    client = _FallbackClient([_record(), _record()], fail_primary=3)

    result = extract_referral_pdf(
        SAMPLE_PDF,
        client=client,
        pdf_transport="inline",
        model="claude-opus-5",
        fallback_models=["claude-opus-4-8"],
        sleep=lambda _delay: None,
        random_source=lambda: 0.0,
    )

    assert result.source.extraction is not None
    assert result.source.extraction.fallback_used is True
    assert "claude-opus-4-8" in result.source.extraction.models_attempted
    assert client.messages.calls[0]["model"] == "claude-opus-5"
    assert any(call["model"] == "claude-opus-4-8" for call in client.messages.calls)


def test_all_seven_intake_values_survive_monday_and_drk_projection() -> None:
    canonical = _record()
    monday = to_master_sheet_referral_from_canonical(canonical)
    drk = to_drk_create_draft_from_canonical(canonical).payload

    assert monday.patient_name == "Jane Doe"
    assert monday.patient_dob == "1950-01-02"
    assert monday.patient_phone == "555-555-0100"
    assert monday.patient_address == "1 Main St Tampa FL 33601"
    assert monday.referring_facility == "Referral Clinic"
    assert monday.current_home_health_or_hospice == "Current Home Health"
    assert monday.wound_order_included is True
    assert monday.diagnosis_text == "Stage 3 sacral wound requiring skilled wound care."
    assert monday.insurance_provider == "Medicare"
    assert drk.demographics.ssn == "111-22-3333"
    assert drk.primary_address.address_line_1 == "1 Main St"
    assert drk.insurances[0].policy_number == "ABC123"


def test_bundle_readiness_tracks_all_seven_fields(tmp_path: Path) -> None:
    pdf = tmp_path / "referral.pdf"
    pdf.write_bytes(b"%PDF-1.4\n")

    bundle = build_aligned_intake_bundle(_record(), pdf, page_count=1)

    assert bundle.readiness.seven_field_ready is True
    assert bundle.readiness.seven_field_missing == []
    assert bundle.canonical_referral.clinical.summary


def test_explicitly_none_is_a_resolved_quality_state(tmp_path: Path) -> None:
    pdf = tmp_path / "referral.pdf"
    pdf.write_bytes(b"%PDF-1.4\n")
    canonical = _record().model_copy(
        update={
            "insurances": [],
            "field_quality": {
                **_record().field_quality,
                "insurances": CanonicalFieldQuality(
                    status="explicitly_none",
                    confidence="high",
                    evidence_pages=[2],
                ),
            },
        }
    )

    bundle = build_aligned_intake_bundle(canonical, pdf, page_count=2)

    assert bundle.readiness.seven_field_ready is True
    assert bundle.readiness.seven_field_status["insurances"] == "explicitly_none"


def test_one_canonical_write_emits_all_destination_projections(tmp_path: Path) -> None:
    canonical_path = write_canonical_referral(_record(), tmp_path)
    folder = canonical_path.parent

    assert canonical_path.name == "canonical-referral.json"
    assert (folder / "inbox-intake.txt").is_file()
    assert (folder / "monday-referral.json").is_file()
    assert (folder / "drk-create-draft.json").is_file()
    assert "Stage 3 sacral wound" in (folder / "inbox-intake.txt").read_text()
