"""Synthetic Patient Intake payload — every text-ish value is marked TEST."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class SyntheticIntakeData:
    # Demographics
    first_name: str = "TEST"
    middle_name: str = "TEST"
    last_name: str = "TESTPatient"
    suffix: str = "TEST"
    ssn: str = "999-99-9999"  # clearly non-production / test SSN pattern
    date_of_birth: str = "1990-01-15"
    gender_text: str = "Male"
    language_text: str = "English"

    # Primary address
    primary_address1: str = "123 TEST Primary Street"
    primary_address2: str = "Apt TEST-1"
    primary_city: str = "TEST City"
    primary_state: str = "TX"
    primary_zip: str = "75001"
    primary_country_text: str = "United States"

    # Secondary address
    secondary_address1: str = "456 TEST Secondary Avenue"
    secondary_address2: str = "Suite TEST-2"
    secondary_city: str = "TEST Town"
    secondary_state: str = "TX"
    secondary_zip: str = "75002"
    secondary_country_text: str = "United States"

    # Contact
    primary_phone: str = "(555) 010-1111"
    secondary_phone: str = "(555) 010-2222"
    email: str = "test.patient@example.com"
    fax: str = "(555) 010-3333"

    # Emergency contact
    relationship_text: str = "Spouse"
    relative_first_name: str = "TEST"
    relative_last_name: str = "TESTEmergency"
    emergency_phone: str = "(555) 010-4444"
    patient_guardian: bool = False
    care_address1: str = "789 TEST Care Lane"
    care_address2: str = "Unit TEST-3"
    care_city: str = "TEST Care City"
    care_state: str = "TX"
    care_zip: str = "75003"

    # Admission / referral
    admission_date: str = "2026-07-30"
    medicare_admission: bool = True
    palliative_admission: bool = False
    hospice: bool = False
    referral_date: str = "2026-07-29"
    # Typeahead queries must match real EMR catalog rows (dropdown click required).
    # These are search strings, not free-text values; first visible suggestion is clicked.
    place_of_service_query: str = "Home"
    facility_query: str = "a"
    home_health_query: str = "a"
    provider_query: str = "Dr"
    territory_query: str = "a"
    referral_source_query: str = "a"

    # Insurance
    insurance_payer_query: str = "a"
    insurance_type: str = "Primary"
    policy_number: str = "TEST-POLICY-001"
    group_number: str = "TEST-GROUP-001"
    group_name: str = "TEST Group Name"
    verified_with: str = "TEST Verifier"
    effective_date: str = "2026-01-01"
    termination_date: str = "2026-12-31"
    copay: str = "10"
    deductible_amount: str = "100"
    percent_coverage: str = "80"
    deductible_met: str = "25"
    # When False, #subscriberSection appears and must be filled.
    is_patient_policy_holder: bool = False
    subscriber_first_name: str = "TEST"
    subscriber_last_name: str = "TESTHolder"
    subscriber_date_of_birth: str = "1985-06-01"
    subscriber_relationship_text: str = "Spouse"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_test_intake_data() -> SyntheticIntakeData:
    return SyntheticIntakeData()
