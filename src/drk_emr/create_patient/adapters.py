"""Convert the flat synthetic intake dataclass into the typed create draft."""

from __future__ import annotations

from drk_emr.create_patient.schema import (
    DrkAddressDraft,
    DrkAdmissionDraft,
    DrkContactDraft,
    DrkCreatePayloadDraft,
    DrkDemographicsDraft,
    DrkEmergencyContactDraft,
    DrkInsuranceDraft,
    DrkReferralDraft,
    DrkSubscriberDraft,
)
from drk_emr.create_patient.synthetic_data import SyntheticIntakeData


def synthetic_to_create_payload(data: SyntheticIntakeData) -> DrkCreatePayloadDraft:
    subscriber = None
    if not data.is_patient_policy_holder:
        subscriber = DrkSubscriberDraft(
            first_name=data.subscriber_first_name,
            last_name=data.subscriber_last_name,
            date_of_birth=data.subscriber_date_of_birth,
            relationship_to_patient=data.subscriber_relationship_text,
        )
    return DrkCreatePayloadDraft(
        demographics=DrkDemographicsDraft(
            first_name=data.first_name,
            middle_name=data.middle_name,
            last_name=data.last_name,
            suffix=data.suffix,
            ssn=data.ssn,
            date_of_birth=data.date_of_birth,
            gender=data.gender_text,
            preferred_language=data.language_text,
        ),
        primary_address=DrkAddressDraft(
            address_line_1=data.primary_address1,
            address_line_2=data.primary_address2,
            city=data.primary_city,
            state=data.primary_state,
            zip_code=data.primary_zip,
            country=data.primary_country_text,
        ),
        secondary_address=DrkAddressDraft(
            address_line_1=data.secondary_address1,
            address_line_2=data.secondary_address2,
            city=data.secondary_city,
            state=data.secondary_state,
            zip_code=data.secondary_zip,
            country=data.secondary_country_text,
        ),
        contact=DrkContactDraft(
            primary_phone=data.primary_phone,
            secondary_phone=data.secondary_phone,
            email=data.email,
            fax=data.fax,
        ),
        emergency_contact=DrkEmergencyContactDraft(
            relationship=data.relationship_text,
            first_name=data.relative_first_name,
            last_name=data.relative_last_name,
            phone=data.emergency_phone,
            patient_guardian=data.patient_guardian,
            address_line_1=data.care_address1,
            address_line_2=data.care_address2,
            city=data.care_city,
            state=data.care_state,
            zip_code=data.care_zip,
        ),
        admission=DrkAdmissionDraft(
            admission_date=data.admission_date,
            place_of_service_query=data.place_of_service_query,
            facility_query=data.facility_query,
            home_health_query=data.home_health_query,
            provider_query=data.provider_query,
            territory_query=data.territory_query,
            medicare_admission=data.medicare_admission,
            palliative_care=data.palliative_admission,
            hospice=data.hospice,
        ),
        referral=DrkReferralDraft(
            referral_source_query=data.referral_source_query,
            referral_date=data.referral_date,
        ),
        insurances=[
            DrkInsuranceDraft(
                payer_query=data.insurance_payer_query,
                insurance_type=data.insurance_type,
                policy_number=data.policy_number,
                group_number=data.group_number,
                group_name=data.group_name,
                verified_with=data.verified_with,
                effective_date=data.effective_date,
                termination_date=data.termination_date,
                copay=data.copay,
                deductible_amount=data.deductible_amount,
                percent_coverage=data.percent_coverage,
                deductible_met=data.deductible_met,
                is_patient_policy_holder=data.is_patient_policy_holder,
                subscriber=subscriber,
            )
        ],
    )
