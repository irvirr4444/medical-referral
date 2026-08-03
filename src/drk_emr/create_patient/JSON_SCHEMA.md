# DRK Patient Intake JSON Schema

Payload shape for filling `/PatientIntake/Index` via `drk_emr.create_patient` (fill-only automation).  
This document describes the JSON the filler expects: **type**, **meaning**, and **EMR control**.

> Safety: current automation fills the form and may save an insurance **entry**, but it **never** clicks **Create Patient**.

See also [`README.md`](README.md) for commands and `.env`.

## Canonical PDF adapter envelope

`intake_extractor.aligned_intake` produces a non-submitting draft envelope:

```json
{
  "payload": {
    "demographics": {},
    "primary_address": {},
    "secondary_address": {},
    "contact": {},
    "emergency_contact": {},
    "admission": {},
    "referral": {},
    "insurances": []
  },
  "ready_for_fill": false,
  "blockers": [],
  "unresolved_fields": [],
  "warnings": []
}
```

`insurances` is plural so every PDF policy is retained. The current browser filler supports one insurance
entry, so a later approved DRK writer must process the list deliberately rather than discarding secondary
coverage. `ready_for_fill` remains false while required values are missing or typeahead values have not been
matched to exact DRK catalog rows. This envelope is a draft and is not evidence that a patient was created.

---

## Top-level object

```json
{
  "demographics": {},
  "primary_address": {},
  "secondary_address": {},
  "contact": {},
  "emergency_contact": {},
  "admission": {},
  "referral": {},
  "insurance": {}
}
```

All dates use ISO format: `YYYY-MM-DD`.  
Phones are display strings (e.g. `(555) 010-1111`).  
State codes are 2-letter US abbreviations (e.g. `TX`).

**Typeahead fields** (`*_query`) are search strings, not final stored names. The UI searches, shows dropdown rows (`div.p-3.cursor-pointer`), and a click sets a hidden ID. Queries must match real EMR catalog text.

---

## Example payload

```json
{
  "demographics": {
    "first_name": "TEST",
    "middle_name": "TEST",
    "last_name": "TESTPatient",
    "suffix": "TEST",
    "ssn": "999-99-9999",
    "date_of_birth": "1990-01-15",
    "gender": "Male",
    "preferred_language": "English"
  },
  "primary_address": {
    "address_line_1": "123 TEST Primary Street",
    "address_line_2": "Apt TEST-1",
    "city": "TEST City",
    "state": "TX",
    "zip_code": "75001",
    "country": "United States"
  },
  "secondary_address": {
    "address_line_1": "456 TEST Secondary Avenue",
    "address_line_2": "Suite TEST-2",
    "city": "TEST Town",
    "state": "TX",
    "zip_code": "75002",
    "country": "United States"
  },
  "contact": {
    "primary_phone": "(555) 010-1111",
    "secondary_phone": "(555) 010-2222",
    "email": "test.patient@example.com",
    "fax": "(555) 010-3333"
  },
  "emergency_contact": {
    "relationship": "Spouse",
    "first_name": "TEST",
    "last_name": "TESTEmergency",
    "phone": "(555) 010-4444",
    "patient_guardian": false,
    "address_line_1": "789 TEST Care Lane",
    "address_line_2": "Unit TEST-3",
    "city": "TEST Care City",
    "state": "TX",
    "zip_code": "75003"
  },
  "admission": {
    "admission_date": "2026-07-30",
    "place_of_service_query": "Home",
    "facility_query": "a",
    "home_health_query": "a",
    "provider_query": "Dr",
    "territory_query": "a",
    "medicare_admission": true,
    "palliative_care": false,
    "hospice": false
  },
  "referral": {
    "referral_source_query": "a",
    "referral_date": "2026-07-29"
  },
  "insurance": {
    "payer_query": "a",
    "insurance_type": "Primary",
    "policy_number": "TEST-POLICY-001",
    "group_number": "TEST-GROUP-001",
    "group_name": "TEST Group Name",
    "verified_with": "TEST Verifier",
    "effective_date": "2026-01-01",
    "termination_date": "2026-12-31",
    "copay": "10",
    "deductible_amount": "100",
    "percent_coverage": "80",
    "deductible_met": "25",
    "is_patient_policy_holder": false,
    "subscriber": {
      "first_name": "TEST",
      "last_name": "TESTHolder",
      "date_of_birth": "1985-06-01",
      "relationship_to_patient": "Spouse"
    }
  }
}
```

---

## 1. `demographics`

| JSON field | Type | Required | Meaning | EMR control (`id`) |
|---|---|---|---|---|
| `first_name` | `string` | yes | Patient legal first name | `#firstName` |
| `middle_name` | `string` | no | Middle name | `#middleName` |
| `last_name` | `string` | yes | Patient legal last name | `#lastName` |
| `suffix` | `string` | no | Name suffix (`Jr.`, `Sr.`, etc.) | `#suffix` |
| `ssn` | `string` | yes | SSN, usually `XXX-XX-XXXX` | `#ssn` |
| `date_of_birth` | `string` (`YYYY-MM-DD`) | yes | Date of birth | `#dateOfBirth` |
| `gender` | `string` | yes | Exact gender option label | `#genderIdentityId` (select) |
| `preferred_language` | `string` | no | Exact language option label | `#languageId` (select) |

**Gender allowed labels (exact):**  
`Female` · `Male` · `Male-to-Female` · `Female-to-Male` · `Genderqueer` · `Unknown` · `Other`

---

## 2. `primary_address`

| JSON field | Type | Required | Meaning | EMR control |
|---|---|---|---|---|
| `address_line_1` | `string` | no* | Street address | `#primaryAddress1` |
| `address_line_2` | `string` | no | Apt / suite / unit | `#primaryAddress2` |
| `city` | `string` | no* | City | `#primaryCity` |
| `state` | `string` | no* | US state code (`AL`…`WY`) | `#primaryStateId` (select by value) |
| `zip_code` | `string` | no* | ZIP (`XXXXX` or `XXXXX-XXXX`) | `#primaryZipCode` |
| `country` | `string` | no | Exact country label (e.g. `United States`) | `#primaryCountryId` (select) |

\*Not marked with `*` on the form in all cases, but needed for a usable patient address.

---

## 3. `secondary_address`

Same shape as `primary_address`, mapped to `#secondaryAddress1`, `#secondaryAddress2`, `#secondaryCity`, `#secondaryStateId`, `#secondaryZipCode`, `#secondaryCountryId`.

| JSON field | Type | Meaning |
|---|---|---|
| `address_line_1` | `string` | Secondary street |
| `address_line_2` | `string` | Secondary apt/suite |
| `city` | `string` | Secondary city |
| `state` | `string` | Secondary state code |
| `zip_code` | `string` | Secondary ZIP |
| `country` | `string` | Secondary country label |

---

## 4. `contact`

| JSON field | Type | Required | Meaning | EMR control |
|---|---|---|---|---|
| `primary_phone` | `string` | yes | Main phone | `#primaryPhoneNumber` |
| `secondary_phone` | `string` | no | Alternate phone | `#secondaryPhoneNumber` |
| `email` | `string` | no | Email address | `#email` |
| `fax` | `string` | no | Fax number | `#fax` |

---

## 5. `emergency_contact`

| JSON field | Type | Required | Meaning | EMR control |
|---|---|---|---|---|
| `relationship` | `string` | no | Exact relationship label | `#relationshipId` |
| `first_name` | `string` | no | Emergency contact first name | `#relativeFirstName` |
| `last_name` | `string` | no | Emergency contact last name | `#relativeLastName` |
| `phone` | `string` | no | Emergency contact phone | `#emergencyContactPhoneNumber` |
| `patient_guardian` | `boolean` | no | Whether contact is patient guardian | `#patientGuardian` |
| `address_line_1` | `string` | no | Guardian/care address line 1 | `#carePrimaryAddress1` |
| `address_line_2` | `string` | no | Guardian/care address line 2 | `#carePrimaryAddress2` |
| `city` | `string` | no | Guardian/care city | `#carePrimaryCity` |
| `state` | `string` | no | Guardian/care state code | `#carePrimaryStateId` |
| `zip_code` | `string` | no | Guardian/care ZIP | `#carePrimaryZipCode` |

**Relationship allowed labels (exact):**  
`Brother` · `Daughter` · `Father` · `Grandfather` · `Grandmother` · `Guardian` · `Mother` · `Sister` · `Son` · `Spouse`

---

## 6. `admission`

| JSON field | Type | Required | Meaning | EMR control |
|---|---|---|---|---|
| `admission_date` | `string` (`YYYY-MM-DD`) | no | Admission date | `#admissionDate` |
| `place_of_service_query` | `string` | no | Typeahead search for place of service | `#placeOfServiceSearch` → hidden `#placeOfServiceCode` |
| `facility_query` | `string` | no | Typeahead search for facility | `#facilitySearch` → `#facilityId` |
| `home_health_query` | `string` | no | Typeahead search for home health company | `#homeHealthSearch` → `#homeHealthCompanyId` |
| `provider_query` | `string` | no | Typeahead search for provider | `#providerSearch` → `#providerId` |
| `territory_query` | `string` | no | Typeahead search for territory | `#territorySearch` → `#territoryId` |
| `medicare_admission` | `boolean` | no | Admission type: Medicare | `#medicareAdmission` |
| `palliative_care` | `boolean` | no | Admission type: Palliative Care | `#palliativeAdmission` |
| `hospice` | `boolean` | no | Admission type: Hospice | `#hospice` |

---

## 7. `referral`

| JSON field | Type | Required | Meaning | EMR control |
|---|---|---|---|---|
| `referral_source_query` | `string` | no | Typeahead search for referral source / marketer | `#marketerSearch` → `#referralSourceId` |
| `referral_date` | `string` (`YYYY-MM-DD`) | no | Referral date | `#referralDate` |

---

## 8. `insurance`

Opened via `#addInsuranceBtn`. Saved as an insurance **entry** via `#saveInsuranceBtn` (not Create Patient).

| JSON field | Type | Required | Meaning | EMR control |
|---|---|---|---|---|
| `payer_query` | `string` | yes* | Typeahead search for insurance payer | `#insurancePayerSearch` → `#insurancePayerId` |
| `insurance_type` | `string` | yes* | `Primary` · `Secondary` · `Tertiary` | `#insuranceType` |
| `policy_number` | `string` | yes* | Policy number | `#policyNumber` |
| `group_number` | `string` | no | Group number | `#groupNumber` |
| `group_name` | `string` | no | Group name | `#groupName` |
| `verified_with` | `string` | no | Who verified coverage | `#verifiedWith` |
| `effective_date` | `string` (`YYYY-MM-DD`) | no | Coverage start | `#effectiveDate` |
| `termination_date` | `string` (`YYYY-MM-DD`) | no | Coverage end | `#terminationDate` |
| `copay` | `string` \| `number` | no | Copay amount | `#copay` |
| `deductible_amount` | `string` \| `number` | no | Deductible amount | `#deductibleAmount` |
| `percent_coverage` | `string` \| `number` | no | Coverage percent `0–100` | `#percentCoverage` |
| `deductible_met` | `string` \| `number` | no | Deductible already met | `#deductibleMet` |
| `is_patient_policy_holder` | `boolean` | no | If `true`, patient is policy holder and subscriber block is hidden | `#isPatientPolicyHolder` |
| `subscriber` | `object` \| `null` | conditional | Required when `is_patient_policy_holder` is `false` | `#subscriberSection` |

### 8.1 `insurance.subscriber` (only if patient is **not** policy holder)

When `is_patient_policy_holder` is `false`, `#subscriberSection` becomes visible.

| JSON field | Type | Required | Meaning | EMR control |
|---|---|---|---|---|
| `first_name` | `string` | yes (conditional) | Policy holder first name | `#subscriberFirstName` |
| `last_name` | `string` | yes (conditional) | Policy holder last name | `#subscriberLastName` |
| `date_of_birth` | `string` (`YYYY-MM-DD`) | yes (conditional) | Policy holder DOB | `#subscriberDateOfBirth` |
| `relationship_to_patient` | `string` | yes (conditional) | Exact relationship label (same list as emergency) | `#subscriberRelationshipId` |

---

## Typeahead behavior (important)

These JSON values are **search queries**, not final display values:

- `admission.place_of_service_query`
- `admission.facility_query`
- `admission.home_health_query`
- `admission.provider_query`
- `admission.territory_query`
- `referral.referral_source_query`
- `insurance.payer_query`

Automation flow for each:

1. Type the query into the search input  
2. Wait for dropdown rows (`div.p-3.cursor-pointer`)  
3. Click a matching row  
4. Confirm the related hidden ID field is populated  

If no row appears, the field cannot be considered selected.

---

## Flat key map (current Python filler)

The live filler currently uses a flat dataclass. Equivalent flat keys:

| Flat key | Nested JSON path |
|---|---|
| `first_name` | `demographics.first_name` |
| `middle_name` | `demographics.middle_name` |
| `last_name` | `demographics.last_name` |
| `suffix` | `demographics.suffix` |
| `ssn` | `demographics.ssn` |
| `date_of_birth` | `demographics.date_of_birth` |
| `gender_text` | `demographics.gender` |
| `language_text` | `demographics.preferred_language` |
| `primary_address1` | `primary_address.address_line_1` |
| `primary_address2` | `primary_address.address_line_2` |
| `primary_city` | `primary_address.city` |
| `primary_state` | `primary_address.state` |
| `primary_zip` | `primary_address.zip_code` |
| `primary_country_text` | `primary_address.country` |
| `secondary_address1` | `secondary_address.address_line_1` |
| `secondary_address2` | `secondary_address.address_line_2` |
| `secondary_city` | `secondary_address.city` |
| `secondary_state` | `secondary_address.state` |
| `secondary_zip` | `secondary_address.zip_code` |
| `secondary_country_text` | `secondary_address.country` |
| `primary_phone` | `contact.primary_phone` |
| `secondary_phone` | `contact.secondary_phone` |
| `email` | `contact.email` |
| `fax` | `contact.fax` |
| `relationship_text` | `emergency_contact.relationship` |
| `relative_first_name` | `emergency_contact.first_name` |
| `relative_last_name` | `emergency_contact.last_name` |
| `emergency_phone` | `emergency_contact.phone` |
| `patient_guardian` | `emergency_contact.patient_guardian` |
| `care_address1` | `emergency_contact.address_line_1` |
| `care_address2` | `emergency_contact.address_line_2` |
| `care_city` | `emergency_contact.city` |
| `care_state` | `emergency_contact.state` |
| `care_zip` | `emergency_contact.zip_code` |
| `admission_date` | `admission.admission_date` |
| `place_of_service_query` | `admission.place_of_service_query` |
| `facility_query` | `admission.facility_query` |
| `home_health_query` | `admission.home_health_query` |
| `provider_query` | `admission.provider_query` |
| `territory_query` | `admission.territory_query` |
| `medicare_admission` | `admission.medicare_admission` |
| `palliative_admission` | `admission.palliative_care` |
| `hospice` | `admission.hospice` |
| `referral_source_query` | `referral.referral_source_query` |
| `referral_date` | `referral.referral_date` |
| `insurance_payer_query` | `insurance.payer_query` |
| `insurance_type` | `insurance.insurance_type` |
| `policy_number` | `insurance.policy_number` |
| `group_number` | `insurance.group_number` |
| `group_name` | `insurance.group_name` |
| `verified_with` | `insurance.verified_with` |
| `effective_date` | `insurance.effective_date` |
| `termination_date` | `insurance.termination_date` |
| `copay` | `insurance.copay` |
| `deductible_amount` | `insurance.deductible_amount` |
| `percent_coverage` | `insurance.percent_coverage` |
| `deductible_met` | `insurance.deductible_met` |
| `is_patient_policy_holder` | `insurance.is_patient_policy_holder` |
| `subscriber_first_name` | `insurance.subscriber.first_name` |
| `subscriber_last_name` | `insurance.subscriber.last_name` |
| `subscriber_date_of_birth` | `insurance.subscriber.date_of_birth` |
| `subscriber_relationship_text` | `insurance.subscriber.relationship_to_patient` |

---

## Explicitly out of scope

| Control | Why |
|---|---|
| `#createPatientBtnBottom` / Create Patient | Must never be clicked by fill-only automation |
| Final patient create/submit API | Not part of this JSON fill contract yet |
