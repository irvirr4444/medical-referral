from intake_extractor.postprocess import normalize_referral
from intake_extractor.schema import ReferralIntake, RequestedService


def test_normalize_referral_formats_contact_fields() -> None:
    referral = ReferralIntake(
        patient_dob="3/6/26",
        patient_phone="626.379.1461",
        referring_phone="18189389143",
        referring_fax="8189389179",
    )

    normalized = normalize_referral(referral)

    assert normalized.patient_dob == "03/06/2026"
    assert normalized.patient_phone == "(626) 379-1461"
    assert normalized.referring_phone == "(818) 938-9143"
    assert normalized.referring_fax == "(818) 938-9179"


def test_normalize_referral_clears_medication_profile_requested_services() -> None:
    referral = ReferralIntake(
        requested_services=[
            RequestedService(service="acetaminophen 325 mg oral tablet", instructions="Dispense #1 Tablet"),
            RequestedService(service="alprazolam 0.25 mg oral tablet", instructions="0 Refills"),
            RequestedService(service="clopidogrel 75 mg oral tablet", instructions="Take once daily"),
            RequestedService(service="Eliquis 5 mg oral tablet", instructions="Take twice daily"),
            RequestedService(service="levothyroxine 50 mcg oral tablet", instructions="Take once daily"),
            RequestedService(service="Novolog FlexPen U-100 Insulin", instructions="Refill profile"),
            RequestedService(service="oxycodone 5 mg oral tablet", instructions="Take as needed"),
            RequestedService(service="famotidine 20 mg oral tablet", instructions="Dispense #180"),
        ]
    )

    normalized = normalize_referral(referral)

    assert normalized.requested_services == []


def test_normalize_referral_drops_address_from_referring_facility_when_provider_exists() -> None:
    referral = ReferralIntake(
        referring_provider_name="YVETTE GUZMAN, APRN DNP",
        referring_facility="4912 WEST TRAPNELL RD, PLANT CITY FL 33566-0128",
        notes="Existing note.",
    )

    normalized = normalize_referral(referral)

    assert normalized.referring_facility is None
    assert "Referring address listed separately" in (normalized.notes or "")


def test_normalize_referral_preserves_generic_service_shapes() -> None:
    referral = ReferralIntake(
        patient_address="17950 E Dorado Dr, Aurora CO 80015",
        referring_facility="AccentCare Home Health",
        requested_services=[
            RequestedService(service="Home Health - Skilled Nursing"),
            RequestedService(service="DME - Wheelchair"),
            RequestedService(service="Topical mupirocin (BACTROBAN) 2% ointment", instructions="Apply to left knee"),
            RequestedService(service="Wound Care evaluation", instructions="Need wound care eval"),
        ],
    )

    normalized = normalize_referral(referral)

    assert normalized.patient_address == "17950 E Dorado Dr, Aurora, CO 80015"
    assert normalized.referring_facility == "Accent Care Home Health"
    assert [service.service for service in normalized.requested_services] == [
        "Skilled Nursing (Home Health)",
        "Durable Medical Equipment - Wheelchair",
        "Medication - mupirocin (BACTROBAN) 2% ointment",
        "Wound Care evaluation",
    ]


def test_normalize_referral_preserves_distinct_requested_services() -> None:
    referral = ReferralIntake(
        requested_services=[
            RequestedService(service="Referral to Home Health - Outpatient", frequency="1 visit"),
            RequestedService(service="Skilled Nursing", instructions="Home safety eval"),
            RequestedService(service="Physical Therapy", instructions="Mobility training"),
            RequestedService(
                service="Home Health - Wound Care",
                frequency="DAILY",
                instructions="Remove all dressings. Wash wounds with normal saline.",
            ),
            RequestedService(service="Case Management Order", instructions="Post-hospitalization planning"),
            RequestedService(service="CT Abdomen Pelvis Without contrast", frequency="ONCE", instructions="abd pain"),
        ]
    )

    normalized = normalize_referral(referral)

    assert [service.service for service in normalized.requested_services] == [
        "Referral to Home Health - Outpatient",
        "Skilled Nursing (Home Health)",
        "Physical Therapy (Home Health)",
        "Home Health - Wound Care",
        "Case Management Order",
        "CT Abdomen Pelvis Without contrast",
    ]


def test_normalize_referral_does_not_promote_services_from_notes() -> None:
    referral = ReferralIntake(
        requested_services=[
            RequestedService(
                service="Wound care evaluation",
                frequency="3m",
                instructions="Please see patient for wound care eval of stage 2 coccyx wound.",
            )
        ],
        notes="Physical Therapy (Omni, Therapy) assigned 3/12/2026; Skilled Nursing (Martirosyan, David) assigned 3/8/2026.",
    )

    normalized = normalize_referral(referral)

    assert [service.service for service in normalized.requested_services] == [
        "Wound care evaluation",
    ]


def test_normalize_referral_collapses_dme_supply_line_items() -> None:
    referral = ReferralIntake(
        requested_services=[
            RequestedService(
                service="DME Wound Care Supplies - Long abdominal pads",
                frequency="60 monthly",
                instructions="For abdominal wound, minimal drainage, surgical, non-debrided, for one month",
            ),
            RequestedService(
                service="DME Wound Care Supplies - 4x4 gauzes",
                frequency="200 monthly",
                instructions="For abdominal wound, minimal drainage, surgical, non-debrided, for one month",
            ),
            RequestedService(
                service="DME Wound Care Supplies - Paper tape",
                frequency="4 monthly",
                instructions="For abdominal wound, minimal drainage, surgical, non-debrided, for one month",
            ),
        ]
    )

    normalized = normalize_referral(referral)

    assert len(normalized.requested_services) == 1
    assert normalized.requested_services[0].service == "DME Wound Care Supplies"
    assert normalized.requested_services[0].frequency == "For one month"
