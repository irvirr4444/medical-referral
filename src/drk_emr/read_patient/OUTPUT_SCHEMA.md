# Read Patient — Output JSON Schema

Each card file has this wrapper:

```json
{
  "card": "patient_information",
  "record_count": 1,
  "records": [
    {
      "endpoint": {
        "method": "GET",
        "url": "https://drkemr.com/PatientDashboard/GetPatientDemographics/{patientId}",
        "status": 200
      },
      "business_data": {}
    }
  ]
}
```

| Wrapper field | Type | Meaning |
|---|---|---|
| `card` | `string` | Card name / filename stem |
| `record_count` | `integer` | Number of captured API (or DOM) records |
| `records[]` | `array` | One entry per matched endpoint response |
| `records[].endpoint.method` | `string` | HTTP method, or `"DOM"` for diagnosis scrape |
| `records[].endpoint.url` | `string` | URL pattern with `{patientId}` placeholders |
| `records[].endpoint.status` | `integer` | HTTP status (DOM scrape uses `200`) |
| `records[].business_data` | `object` \| `array` \| `any` | Raw EMR JSON body (or structured DOM scrape) |

---

## Card → API mapping

| File | Source API / method |
|---|---|
| `patient_information.json` | `GET /PatientDashboard/GetPatientDemographics/{patientId}` |
| `admission.json` | `GET /PatientDashboard/GetAdmissionSummary/{patientId}` |
| `communications.json` | `GET /PatientDashboard/GetCommunicationsPaginated/...` |
| `encounters.json` | `GET /PatientDashboard/GetEncounters/...` |
| `diagnosis.json` | Diagnosis JSON API if present; else **DOM scrape** of `#diagnosisCard` |
| `medications_allergies.json` | DoseSpot meds + allergies endpoints |
| `insurance.json` | Insurances + eligibility history |
| `custom_scans.json` | `GetCustomScans` |
| `billing.json` | `GetPatientBilling` |
| `pipeline.json` | `GetBvPipelineStatus` |
| `endpoint_catalog_*.json` | Full captured JSON catalog for the run |

---

## `patient_information.json` — typical `business_data.data`

| Field | Type | Meaning |
|---|---|---|
| `id` | `integer` | EMR patient id |
| `firstName` | `string` | First name |
| `lastName` | `string` | Last name |
| `fullName` | `string` | Display name |
| `mrn` | `string` | Medical record number |
| `status` / `patientStatusDisplayName` | `string` | Active / etc. |
| `dateOfBirth` | `string` (ISO datetime) | DOB |
| `age` | `integer` | Age |
| `gender` | `string` | Gender label |
| `genderIdentityId` | `integer` | Gender option id |
| `address1` / `address2` | `string` \| `null` | Address lines |
| `city` / `state` / `zipCode` | `string` | Address parts |
| `fullAddress` | `string` | Combined address |
| `phoneNumber` | `string` \| `null` | Phone |
| `email` | `string` \| `null` | Email |
| `emergencyContactName` / `emergencyContactPhone` | `string` \| `null` | Emergency contact |
| `facilityName` | `string` \| `null` | Facility |
| `homeHealthCompanyName` | `string` \| `null` | Home health company |

Exact keys can vary by EMR version; treat `business_data` as the source of truth from the live response.

---

## `diagnosis.json` — DOM fallback shape

When no diagnosis JSON API is captured:

```json
{
  "card": "diagnosis",
  "record_count": 1,
  "records": [
    {
      "endpoint": {
        "method": "DOM",
        "url": "/PatientDashboard/Index/?patientId={patientId}#diagnosisCard",
        "status": 200
      },
      "business_data": {
        "source": "diagnosisCard DOM scrape",
        "count": 9,
        "diagnoses": [
          {
            "code": "L89.153",
            "description": "Pressure ulcer of sacral region, stage 3",
            "added": "Jul 24, 2026",
            "is_primary": true,
            "status": "Active"
          }
        ]
      }
    }
  ]
}
```

| Field | Type | Meaning |
|---|---|---|
| `diagnoses[].code` | `string` | ICD-10 code (may include trailing `.` as shown in UI) |
| `diagnoses[].description` | `string` | Diagnosis text |
| `diagnoses[].added` | `string` \| `null` | Added date text from UI |
| `diagnoses[].is_primary` | `boolean` | Primary diagnosis flag |
| `diagnoses[].status` | `string` \| `null` | e.g. `Active` |

---

## `endpoint_catalog_*.json`

Array of captured requests:

| Field | Type | Meaning |
|---|---|---|
| `section` | `string` | Capture phase label |
| `url` | `string` | Full request URL (query secrets redacted where applied) |
| `method` | `string` | HTTP method |
| `request_headers` | `object` | Headers with sensitive values masked |
| `request_body` | `string` \| `null` | Request body if any |
| `response_status` | `integer` | Status code |
| `response_headers` | `object` | Response headers (masked) |
| `response_json` | `any` | Parsed JSON body |
| `observed_at_utc` | `string` | ISO UTC timestamp |
