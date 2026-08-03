from __future__ import annotations

from pathlib import Path

from intake_extractor.drk_pdf import _is_retryable_api_error, build_drk_cards, extract_drk_from_pdf
from intake_extractor.drk_pdf_schema import (
    ClinicalExtraction,
    DiagnosisCandidate,
    DrkPdfExtraction,
    IdentityReferralExtraction,
    InsuranceCandidate,
    InsuranceExtraction,
    MedicationCandidate,
    PatientCandidate,
    ReferringSourceCandidate,
)


SAMPLE_PDF = Path("samples/BUTLER, ALVA demo.pdf")


def _butler_shape() -> DrkPdfExtraction:
    return DrkPdfExtraction(
        document_type="EHR patient chart",
        patient=PatientCandidate(
            first_name="Alva",
            last_name="Butler",
            full_name="BUTLER, ALVA",
            source_patient_id="6227",
            source_patient_id_label="PATIENT ID/#",
            mrn=None,
            date_of_birth="10/4/1940",
            age=85,
            gender="M",
            address1="5316 FISHERSOUND LN",
            city="APOLLO BEACH",
            state="FL",
            zip_code="33572",
            phone_number="(260) 438-4646",
            email="Dandydeby@aol.com",
        ),
        referring_source=ReferringSourceCandidate(provider_name="YVETTE GUZMAN ARNP"),
        diagnoses_section_present=True,
        diagnoses=[
            DiagnosisCandidate(code=f"Z00.{index:02d}", description=f"Diagnosis {index}", status="Current")
            for index in range(12)
        ],
        medications_section_present=True,
        medications=[
            MedicationCandidate(name=f"Medication {index}", directions=f"Directions {index}", status="Current")
            for index in range(25)
        ],
        allergies_section_present=True,
        no_known_allergies_explicit=None,
        insurance_section_present=True,
        insurances=[
            InsuranceCandidate(payer_name="MEDICARE PART B", policy_number="4FM5A30MN88"),
            InsuranceCandidate(payer_name="FLORIDA BLUE", policy_number="VNF651M57250"),
        ],
    )


def test_build_drk_cards_preserves_source_id_and_counts() -> None:
    cards = build_drk_cards(_butler_shape(), SAMPLE_PDF, page_count=3)

    demographics = cards["patient_information"]["records"][0]["business_data"]["data"]
    assert demographics["id"] is None
    assert demographics["mrn"] is None
    assert demographics["sourcePatientId"] == "6227"
    assert demographics["sourcePatientIdLabel"] == "PATIENT ID/#"
    assert demographics["dateOfBirth"] == "1940-10-04T00:00:00"

    diagnosis = cards["diagnosis"]["records"][0]["business_data"]
    assert diagnosis["count"] == 12
    assert len(diagnosis["diagnoses"]) == 12

    medication_records = cards["medications_allergies"]["records"]
    allergy_data = medication_records[0]["business_data"]["data"]
    medication_data = medication_records[1]["business_data"]["data"]
    assert allergy_data["items"] == []
    assert allergy_data["noKnownAllergy"] is None
    assert allergy_data["hasNoKnownAllergies"] is False
    assert medication_data["pageResult"]["totalCount"] == 25

    insurance = cards["insurance"]["records"][0]["business_data"]["data"]
    assert len(insurance) == 2
    assert insurance[0]["isPrimary"] is None
    assert cards["pipeline"] == {"card": "pipeline", "record_count": 0, "records": []}


def test_overloaded_api_error_is_retryable() -> None:
    assert _is_retryable_api_error(Exception("{'type': 'overloaded_error', 'message': 'Overloaded'}"))


class _ParsedMessage:
    def __init__(self, parsed_output) -> None:
        self.parsed_output = parsed_output


class _FakeMessages:
    def __init__(self, outputs: list) -> None:
        self.outputs = outputs
        self.calls: list[dict] = []

    def stream(self, **kwargs):
        self.calls.append(kwargs)
        return _FakeStream(_ParsedMessage(self.outputs.pop(0)))


class _FakeStream:
    def __init__(self, message: _ParsedMessage) -> None:
        self.message = message

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def get_final_message(self) -> _ParsedMessage:
        return self.message


class _FakeClient:
    def __init__(self, outputs: list) -> None:
        self.messages = _FakeMessages(outputs)


def test_three_pass_extraction_uses_native_pdf_and_final_adjudication() -> None:
    expected = _butler_shape()
    identity_first = IdentityReferralExtraction(patient=PatientCandidate(full_name="Wrong"))
    identity_second = IdentityReferralExtraction(patient=PatientCandidate(full_name="BUTLER, ALVA"))
    identity_final = IdentityReferralExtraction(
        document_type=expected.document_type,
        patient=expected.patient,
        referring_source=expected.referring_source,
        admission=expected.admission,
    )
    clinical = ClinicalExtraction(
        diagnoses_section_present=True,
        diagnoses=expected.diagnoses,
        medications_section_present=True,
        medications=expected.medications,
        allergies_section_present=True,
    )
    insurance = InsuranceExtraction(
        insurance_section_present=True,
        insurances=expected.insurances,
    )
    client = _FakeClient(
        [
            identity_first,
            identity_second,
            identity_final,
            clinical,
            clinical,
            clinical,
            insurance,
            insurance,
            insurance,
        ]
    )

    result = extract_drk_from_pdf(
        SAMPLE_PDF,
        passes=3,
        client=client,
        parallel_domains=False,
        parallel_readings=False,
        pdf_transport="inline",
    )

    assert result.patient.source_patient_id == "6227"
    assert len(client.messages.calls) == 9
    for call in client.messages.calls:
        assert call["model"] == "claude-opus-5"
        assert call["output_config"] == {"effort": "max"}
        assert call["thinking"] == {"type": "adaptive"}
        assert call["messages"][0]["content"][0]["type"] == "document"

    adjudication_text = client.messages.calls[2]["messages"][0]["content"][1]["text"]
    assert "CANDIDATE EXTRACTIONS" in adjudication_text
    assert '"candidate_a"' in adjudication_text


class _UploadedFile:
    id = "file_test_123"


class _FakeFiles:
    def __init__(self) -> None:
        self.upload_count = 0
        self.deleted_ids: list[str] = []

    def upload(self, **_kwargs):
        self.upload_count += 1
        return _UploadedFile()

    def delete(self, file_id: str):
        self.deleted_ids.append(file_id)


class _FakeBeta:
    def __init__(self, outputs: list) -> None:
        self.messages = _FakeMessages(outputs)
        self.files = _FakeFiles()


class _FakeFilesClient:
    def __init__(self, outputs: list) -> None:
        self.messages = _FakeMessages([])
        self.beta = _FakeBeta(outputs)


def test_files_api_uploads_once_uses_file_block_and_deletes() -> None:
    expected = _butler_shape()
    identity = IdentityReferralExtraction(
        document_type=expected.document_type,
        patient=expected.patient,
        referring_source=expected.referring_source,
    )
    clinical = ClinicalExtraction(
        diagnoses_section_present=True,
        diagnoses=expected.diagnoses,
        medications_section_present=True,
        medications=expected.medications,
    )
    insurance = InsuranceExtraction(insurance_section_present=True, insurances=expected.insurances)
    client = _FakeFilesClient([identity, clinical, insurance])

    result = extract_drk_from_pdf(
        SAMPLE_PDF,
        passes=1,
        client=client,
        parallel_domains=False,
        parallel_readings=False,
        pdf_transport="files-api",
    )

    assert result.patient.source_patient_id == "6227"
    assert client.beta.files.upload_count == 1
    assert client.beta.files.deleted_ids == ["file_test_123"]
    assert len(client.beta.messages.calls) == 3
    for call in client.beta.messages.calls:
        assert call["betas"] == ["files-api-2025-04-14"]
        document = call["messages"][0]["content"][0]
        assert document["source"] == {"type": "file", "file_id": "file_test_123"}
