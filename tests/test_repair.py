from intake_extractor.llm.repair import (
    merge_contact_repair_payload,
    merge_header_payload,
    merge_repair_payload,
    merge_requested_services_payload,
    should_repair_header_fields,
    should_repair_contacts,
    should_repair_requested_services,
)
from intake_extractor.models.schema import ReferralIntake, RequestedService


def test_should_not_repair_requested_services_for_sparse_multi_page_packet() -> None:
    referral = ReferralIntake(
        pages_used=23,
        requested_services=[
            RequestedService(service="Referral to Home Health - Outpatient"),
            RequestedService(service="Skilled Nursing"),
            RequestedService(service="Physical Therapy"),
        ],
    )

    assert should_repair_requested_services(referral) is False


def test_should_repair_requested_services_for_single_generic_item() -> None:
    referral = ReferralIntake(
        pages_used=8,
        requested_services=[
            RequestedService(service="Referral to Home Health - Outpatient"),
        ],
    )

    assert should_repair_requested_services(referral) is True


def test_should_not_repair_specific_single_service_packet() -> None:
    referral = ReferralIntake(
        pages_used=10,
        requested_services=[
            RequestedService(
                service="DME Wound Care Supplies",
                instructions="Long abdominal pads - 60 monthly; 4x4 gauzes - 200 monthly",
            )
        ],
    )

    assert should_repair_requested_services(referral) is False


def test_should_repair_contacts_for_missing_sender_block() -> None:
    referral = ReferralIntake(
        referring_provider_name=None,
        referring_facility=None,
        referring_phone=None,
        referring_fax="(303) 647-3647",
    )

    assert should_repair_contacts(referral) is True


def test_should_repair_header_fields_for_abbreviated_facility_or_multi_phone() -> None:
    referral = ReferralIntake(
        patient_phone="home (626) 379-1461, mobile (626) 524-2856",
        referring_facility="Providence LCOM San Pedro",
        referring_phone="(310) 514-5357",
        referring_fax="(310) 514-5413",
    )

    assert should_repair_header_fields(referral) is True


def test_merge_repair_payload_prefers_richer_requested_services() -> None:
    primary = ReferralIntake(
        diagnosis_text="Short diagnosis",
        referral_date="07/10/2026",
        pages_used=10,
        requested_services=[
            RequestedService(service="Skilled Nursing", instructions="Assess/instruct wound care"),
        ],
    )

    repaired = merge_repair_payload(
        primary,
        {
            "diagnosis_text": "Longer diagnosis with more explicit source language",
            "requested_services": [
                {
                    "service": "Skilled Nursing (Home Health)",
                    "frequency": None,
                    "instructions": "Assess/instruct wound care/incision care",
                },
                {
                    "service": "Physical Therapy (Home Health)",
                    "frequency": None,
                    "instructions": "Mobility and caregiver training",
                },
            ],
        },
    )

    assert repaired.diagnosis_text == "Short diagnosis"
    assert [service.service for service in repaired.requested_services] == [
        "Skilled Nursing",
        "Skilled Nursing (Home Health)",
        "Physical Therapy (Home Health)",
    ]


def test_merge_header_payload_overrides_scanned_header_contacts() -> None:
    primary = ReferralIntake(
        patient_phone="home (626) 379-1461, mobile (626) 524-2856",
        referring_facility="Providence LCOM San Pedro",
        referring_phone="(310) 514-5357",
        referring_fax="(310) 514-5413",
    )

    repaired = merge_header_payload(
        primary,
        {
            "patient_phone": "(626) 379-1461",
            "referring_provider_name": "Heather Krohn",
            "referring_facility": "Ay Home Health Care LLC",
            "referring_phone": "(303) 993-1330",
            "referring_fax": "(303) 647-3647",
        },
    )

    assert repaired.patient_phone == "(626) 379-1461"
    assert repaired.referring_provider_name == "Heather Krohn"
    assert repaired.referring_facility == "Ay Home Health Care LLC"
    assert repaired.referring_phone == "(303) 993-1330"
    assert repaired.referring_fax == "(303) 647-3647"


def test_merge_contact_repair_payload_only_fills_contact_fields() -> None:
    primary = ReferralIntake(
        patient_mrn=None,
        patient_address=None,
        referring_phone=None,
        requested_services=[RequestedService(service="Wound Care")],
    )

    repaired = merge_contact_repair_payload(
        primary,
        {
            "patient_mrn": "12345",
            "patient_address": "123 Main St",
            "referring_phone": "(312) 555-0101",
            "requested_services": [{"service": "Bad overwrite"}],
        },
    )

    assert repaired.patient_mrn == "12345"
    assert repaired.patient_address == "123 Main St"
    assert repaired.referring_phone == "(312) 555-0101"
    assert [service.service for service in repaired.requested_services] == ["Wound Care"]


def test_merge_requested_services_payload_rejects_noisy_expansion() -> None:
    primary = ReferralIntake(
        requested_services=[
            RequestedService(
                service="Referral to Home Health - Outpatient",
                frequency="1 visit",
                instructions="Reason: Specialty Services Required",
            )
        ]
    )

    repaired = merge_requested_services_payload(
        primary,
        {
            "requested_services": [
                {
                    "service": "Referral to Home Health - Outpatient",
                    "frequency": "1 visit",
                    "instructions": "Reason: Specialty Services Required",
                },
                {
                    "service": "Specialty request to Social Work",
                    "frequency": None,
                    "instructions": "Patient recently discharged",
                },
                {
                    "service": "XR Chest 2 Views",
                    "frequency": None,
                    "instructions": "Future order",
                },
                {
                    "service": "H Pylori Antigen Stool",
                    "frequency": None,
                    "instructions": "Routine collect",
                },
            ]
        },
    )

    assert [service.service for service in repaired.requested_services] == ["Referral to Home Health - Outpatient"]
