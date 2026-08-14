from __future__ import annotations

from patient_profile.lookup import drk_profile_from_cards
from patient_profile.sections import drk_sections_from_cards


def _card(name: str, *records: dict) -> dict:
    return {"card": name, "record_count": len(records), "records": list(records)}


def _record(url: str, business: dict) -> dict:
    return {"endpoint": {"method": "GET", "url": url, "status": 200}, "business_data": business}


def test_drk_sections_map_diagnoses_meds_admission_notes_insurance() -> None:
    cards = {
        "patient_information": _card(
            "patient_information",
            _record(
                "/PatientDashboard/GetPatientDemographics/77",
                {
                    "success": True,
                    "data": {
                        "id": 77,
                        "fullName": "Alva Butler",
                        "mrn": "MRN-77",
                        "dateOfBirth": "1940-10-04T00:00:00",
                        "gender": "Female",
                        "phoneNumber": "8135550100",
                        "placeOfServiceDescription": "Home",
                        "facilityName": "Tampa General",
                    },
                },
            ),
        ),
        "admission": _card(
            "admission",
            _record(
                "/PatientDashboard/GetAdmissionSummary/77",
                {
                    "success": True,
                    "data": {
                        "currentAdmissionDate": "2026-07-01T00:00:00",
                        "currentFacilityName": "Tampa General",
                        "currentMedicareAdmission": True,
                        "isHospice": False,
                        "placeOfServiceCode": "12",
                        "referral": {"marketerName": "Pat Marketer", "notes": "Wound follow up"},
                    },
                },
            ),
        ),
        "diagnosis": _card(
            "diagnosis",
            {
                "endpoint": {
                    "method": "DOM",
                    "url": "/PatientDashboard/Index/?patientId={patientId}#diagnosisCard",
                    "status": 200,
                },
                "business_data": {
                    "diagnoses": [
                        {
                            "code": "L89.153",
                            "description": "Pressure ulcer",
                            "added": "Jul 24, 2026",
                            "is_primary": True,
                            "status": "Active",
                        }
                    ]
                },
            },
        ),
        "medications_allergies": _card(
            "medications_allergies",
            _record(
                "/PatientDashboard/GetDoseSpotAllergies/77",
                {
                    "success": True,
                    "data": {
                        "items": [{"name": "Penicillin", "reaction": "Rash"}],
                        "hasNoKnownAllergies": False,
                    },
                },
            ),
            _record(
                "/PatientDashboard/GetDoseSpotMedications/77",
                {"success": True, "data": {"items": []}},
            ),
        ),
        "insurance": _card(
            "insurance",
            _record("/PatientDashboard/GetEligibilityHistory/77", {"success": True, "data": []}),
            _record(
                "/PatientDashboard/GetInsurances/77",
                {
                    "success": True,
                    "data": [
                        {
                            "type": "Primary",
                            "payerName": "Medicare",
                            "policyNumber": "1EG4",
                            "isPatientPolicyHolder": True,
                        }
                    ],
                },
            ),
        ),
        "communications": _card(
            "communications",
            _record(
                "/PatientDashboard/GetCommunicationsPaginated/77",
                {
                    "success": True,
                    "data": {
                        "communications": [
                            {
                                "notes": "Called patient",
                                "subject": "Follow up",
                                "timestamp": "2026-07-24T10:00:00",
                                "userName": "Nurse",
                            }
                        ]
                    },
                },
            ),
        ),
        "encounters": _card(
            "encounters",
            _record("/GetEncounters/77", {"success": True, "data": {"encounters": []}}),
        ),
        "custom_scans": _card(
            "custom_scans",
            _record("/GetCustomScans/77", {"success": True, "data": {"scans": []}}),
        ),
        "billing": _card(
            "billing",
            _record(
                "/GetPatientBilling",
                {"success": True, "result": {"collectionsStatus": "None", "totalOutstanding": 0}},
            ),
        ),
        "pipeline": _card(
            "pipeline",
            _record("/GetBvPipelineStatus/77", {"success": True, "data": {"currentStageName": "ACT"}}),
        ),
    }

    titles = {section["title"]: section for section in drk_sections_from_cards(cards)}
    assert any(field["value"] == "L89.153" for field in titles["Diagnoses"]["fields"])
    assert titles["Medications"]["fields"] == []
    assert any(field["value"] == "Tampa General" for field in titles["Admission"]["fields"])
    assert any("Wound follow up" in field["value"] for field in titles["Clinical"]["fields"])
    assert any(field["value"] == "Called patient" for field in titles["Clinical notes"]["fields"])
    assert any(field["value"] == "Medicare" for field in titles["Insurance policies"]["fields"])
    assert any(field["value"] == "Penicillin" for field in titles["Allergies"]["fields"])

    profile = drk_profile_from_cards("77", cards)
    assert profile["sections"]
    assert profile["name"] == "Alva Butler"


def test_drk_sections_map_display_name_meds_and_pipeline_cards() -> None:
    cards = {
        "patient_information": _card(
            "patient_information",
            _record(
                "/PatientDashboard/GetPatientDemographics/55125",
                {"success": True, "data": {"fullName": "Alva Butler", "mrn": "1087998220"}},
            ),
        ),
        "medications_allergies": _card(
            "medications_allergies",
            _record(
                "/PatientDashboard/GetDoseSpotMedications/55125",
                {
                    "success": True,
                    "data": {
                        "items": [
                            {
                                "displayName": "Mupirocin Topical Ointment 2 %",
                                "strength": "2 %",
                                "medicationStatus": "Active",
                                "status": "PharmacyVerified",
                                "directions": "Apply to wound",
                            }
                        ]
                    },
                },
            ),
        ),
        "pipeline": _card(
            "pipeline",
            _record(
                "/PatientDashboard/API/GetBvPipelineStatus/55125",
                {
                    "success": True,
                    "data": {
                        "currentStageName": "QA",
                        "actStatusName": "SW_ACTDone",
                        "activeTherapies": [{"therapyType": "MIST", "status": "Approved"}],
                        "alerts": [{"message": "No MIST device assigned", "severity": "Info"}],
                    },
                },
            ),
        ),
        "encounters": _card(
            "encounters",
            _record(
                "/PatientDashboard/GetEncounters/55125",
                {
                    "success": True,
                    "data": {
                        "encounters": [
                            {
                                "encounterDate": "2026-07-29T10:00:00",
                                "providerName": "Arnaldo Gomez Lotti",
                                "serviceType": "Wound Progress Service",
                                "status": "Completed",
                            }
                        ]
                    },
                },
            ),
        ),
        "custom_scans": _card(
            "custom_scans",
            _record(
                "/PatientDashboard/GetCustomScans/55125",
                {
                    "success": True,
                    "data": {"scans": [{"fileName": "Wound photo", "category": "Other"}]},
                },
            ),
        ),
    }
    titles = {section["title"]: section for section in drk_sections_from_cards(cards)}
    assert any(field["value"] == "Mupirocin Topical Ointment 2 %" for field in titles["Medications"]["fields"])
    assert any(field["value"] == "QA" for field in titles["Pipeline"]["fields"])
    assert any(field["value"] == "MIST" for field in titles["Therapies"]["fields"])
    assert any(field["value"] == "No MIST device assigned" for field in titles["Pipeline alerts"]["fields"])
    assert any(field["value"] == "Arnaldo Gomez Lotti" for field in titles["Encounters"]["fields"])
    assert any(field["value"] == "Wound photo" for field in titles["Documents"]["fields"])
