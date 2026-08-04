from pathlib import Path

from intake_extractor.drk_pdf import _is_retryable_api_error, build_drk_cards
from intake_extractor.drk_pdf_schema import (
    DiagnosisCandidate,
    DrkPdfExtraction,
    InsuranceCandidate,
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
        insurance_section_present=True,
        insurances=[
            InsuranceCandidate(payer_name="MEDICARE PART B", policy_number="4FM5A30MN88"),
            InsuranceCandidate(payer_name="FLORIDA BLUE", policy_number="VNF651M57250"),
        ],
    )


def test_build_drk_cards_preserves_source_id_and_counts() -> None:
    cards = build_drk_cards(_butler_shape(), SAMPLE_PDF, page_count=3)

    demographics = cards["patient_information"]["records"][0]["business_data"]["data"]
    assert demographics["mrn"] is None
    assert demographics["sourcePatientId"] == "6227"
    assert demographics["dateOfBirth"] == "1940-10-04T00:00:00"
    assert cards["diagnosis"]["records"][0]["business_data"]["count"] == 12
    medication_records = cards["medications_allergies"]["records"]
    assert medication_records[1]["business_data"]["data"]["pageResult"]["totalCount"] == 25
    insurance = cards["insurance"]["records"][0]["business_data"]["data"]
    assert len(insurance) == 2
    assert insurance[0]["isPrimary"] is None


def test_overloaded_api_error_is_retryable() -> None:
    assert _is_retryable_api_error(Exception("{'type': 'overloaded_error', 'message': 'Overloaded'}"))
