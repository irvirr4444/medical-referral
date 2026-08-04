# DRK Endpoint Index

- Source catalog: `endpoint_catalog_20260729T101936Z.json`
- Total captured records: **75**
- Unique endpoints: **25**
- Note: query parameter values are redacted/placeheld.

## Unique Endpoint Inventory

### 1. GET /BvPipeline/API/Automation/Tasks
- URL pattern: `https://drkemr.com/BvPipeline/API/Automation/Tasks?scope={value}&page={value}&pageSize={value}`
- UI sections seen: Dashboard load, Documents, Insurance
- Capture count: 3
- Typical status: 200
- Purpose: API endpoint
- Response top-level keys: items, openCount, totalCount, page, pageSize, totalPages, isManager

### 2. GET /Dashboard/CheckDoseSpotAccess
- URL pattern: `https://drkemr.com/Dashboard/CheckDoseSpotAccess`
- UI sections seen: Dashboard load, Documents, Insurance
- Capture count: 3
- Typical status: 200
- Purpose: General JSON endpoint
- Response top-level keys: hasAccess, message

### 3. GET /Dashboard/GetUserLabInbox
- URL pattern: `https://drkemr.com/Dashboard/GetUserLabInbox`
- UI sections seen: Dashboard load, Documents, Insurance
- Capture count: 3
- Typical status: 200
- Purpose: General JSON endpoint
- Response top-level keys: success, data, isBackfill

### 4. GET /Dashboard/GetUserLabInboxCount
- URL pattern: `https://drkemr.com/Dashboard/GetUserLabInboxCount`
- UI sections seen: Dashboard load, Documents, Insurance
- Capture count: 3
- Typical status: 200
- Purpose: General JSON endpoint
- Response top-level keys: success, data, unread, total, isBackfill

### 5. GET /DirectMessage/UnreadCount
- URL pattern: `https://drkemr.com/DirectMessage/UnreadCount`
- UI sections seen: Dashboard load, Documents, Insurance
- Capture count: 3
- Typical status: 200
- Purpose: General JSON endpoint
- Response top-level keys: success, count

### 6. GET /Encounter/GetFiltered
- URL pattern: `https://drkemr.com/Encounter/GetFiltered?page={value}&pageSize={value}&signatureStatus={value}&myTurnOnly={value}&fromDate={value}&toDate={value}`
- UI sections seen: Dashboard load, Documents, Insurance
- Capture count: 3
- Typical status: 200
- Purpose: General JSON endpoint
- Response top-level keys: encounters, totalCount, currentPage, pageSize, totalPages, signedCount, unsignedCount, patient

### 7. GET /Login/ValidateUser
- URL pattern: `https://drkemr.com/Login/ValidateUser?userName=[REDACTED]&password=[REDACTED]&timeZoneId={value}`
- UI sections seen: Dashboard load, Documents, Insurance
- Capture count: 3
- Typical status: 200
- Purpose: General JSON endpoint
- Response top-level keys: data, isSuccessfull

### 8. POST /Mailbox/GetMessages
- URL pattern: `https://drkemr.com/Mailbox/GetMessages`
- UI sections seen: Dashboard load, Documents, Insurance
- Capture count: 3
- Typical status: 200
- Purpose: General JSON endpoint
- Response top-level keys: success, data

### 9. GET /Mailbox/GetRecipients
- URL pattern: `https://drkemr.com/Mailbox/GetRecipients`
- UI sections seen: Dashboard load, Documents, Insurance
- Capture count: 3
- Typical status: 200
- Purpose: General JSON endpoint
- Response top-level keys: success, data

### 10. GET /Mailbox/GetTemplates
- URL pattern: `https://drkemr.com/Mailbox/GetTemplates`
- UI sections seen: Dashboard load, Documents, Insurance
- Capture count: 3
- Typical status: 200
- Purpose: General JSON endpoint
- Response top-level keys: success, data

### 11. GET /PatientDashboard/API/GetBvPipelineStatus/{id}
- URL pattern: `https://drkemr.com/PatientDashboard/API/GetBvPipelineStatus/{id}`
- UI sections seen: Dashboard load, Documents, Insurance
- Capture count: 3
- Typical status: 200
- Purpose: Workflow/pipeline status
- Response top-level keys: success, data

### 12. GET /PatientDashboard/GetAdmissionSummary/{id}
- URL pattern: `https://drkemr.com/PatientDashboard/GetAdmissionSummary/{id}`
- UI sections seen: Dashboard load, Documents, Insurance
- Capture count: 3
- Typical status: 200
- Purpose: Patient dashboard data endpoint
- Response top-level keys: success, data

### 13. GET /PatientDashboard/GetCommunicationsPaginated/{id}
- URL pattern: `https://drkemr.com/PatientDashboard/GetCommunicationsPaginated/{id}?page={value}&pageSize={value}`
- UI sections seen: Dashboard load, Documents, Insurance
- Capture count: 3
- Typical status: 200
- Purpose: Patient dashboard data endpoint
- Response top-level keys: success, data

### 14. GET /PatientDashboard/GetCustomScans/{id}
- URL pattern: `https://drkemr.com/PatientDashboard/GetCustomScans/{id}?skip={value}&take={value}`
- UI sections seen: Dashboard load, Documents, Insurance
- Capture count: 3
- Typical status: 200
- Purpose: Document list / file metadata
- Response top-level keys: success, data

### 15. GET /PatientDashboard/GetDoseSpotAllergies/{id}
- URL pattern: `https://drkemr.com/PatientDashboard/GetDoseSpotAllergies/{id}`
- UI sections seen: Dashboard load, Documents, Insurance
- Capture count: 3
- Typical status: 200
- Purpose: Allergy list
- Response top-level keys: success, data

### 16. GET /PatientDashboard/GetDoseSpotMedications/{id}
- URL pattern: `https://drkemr.com/PatientDashboard/GetDoseSpotMedications/{id}`
- UI sections seen: Dashboard load, Documents, Insurance
- Capture count: 3
- Typical status: 200
- Purpose: Medication list
- Response top-level keys: success, data

### 17. GET /PatientDashboard/GetEligibilityHistory/{id}
- URL pattern: `https://drkemr.com/PatientDashboard/GetEligibilityHistory/{id}`
- UI sections seen: Dashboard load, Documents, Insurance
- Capture count: 3
- Typical status: 200
- Purpose: Insurance eligibility history
- Response top-level keys: success, data

### 18. GET /PatientDashboard/GetEncounters/{id}
- URL pattern: `https://drkemr.com/PatientDashboard/GetEncounters/{id}?page={value}&pageSize={value}`
- UI sections seen: Dashboard load, Documents, Insurance
- Capture count: 3
- Typical status: 200
- Purpose: Patient dashboard data endpoint
- Response top-level keys: success, data

### 19. GET /PatientDashboard/GetInsurances/{id}
- URL pattern: `https://drkemr.com/PatientDashboard/GetInsurances/{id}`
- UI sections seen: Dashboard load, Documents, Insurance
- Capture count: 3
- Typical status: 200
- Purpose: Insurance policies and coverage
- Response top-level keys: success, data

### 20. GET /PatientDashboard/GetLabResultCount/{id}
- URL pattern: `https://drkemr.com/PatientDashboard/GetLabResultCount/{id}`
- UI sections seen: Dashboard load, Documents, Insurance
- Capture count: 3
- Typical status: 200
- Purpose: Lab count summary
- Response top-level keys: success, data, unread, total

### 21. GET /PatientDashboard/GetPatientBilling
- URL pattern: `https://drkemr.com/PatientDashboard/GetPatientBilling?patientId={patientId}`
- UI sections seen: Dashboard load, Documents, Insurance
- Capture count: 3
- Typical status: 200
- Purpose: Billing summary
- Response top-level keys: success, result, isWriteOffApprover, writeOffCeiling

### 22. GET /PatientDashboard/GetPatientDemographics/{id}
- URL pattern: `https://drkemr.com/PatientDashboard/GetPatientDemographics/{id}`
- UI sections seen: Dashboard load, Documents, Insurance
- Capture count: 3
- Typical status: 200
- Purpose: Patient dashboard data endpoint
- Response top-level keys: success, data

### 23. GET /PatientDashboard/GetQuickNotes/{id}
- URL pattern: `https://drkemr.com/PatientDashboard/GetQuickNotes/{id}`
- UI sections seen: Dashboard load, Documents, Insurance
- Capture count: 3
- Typical status: 200
- Purpose: Quick notes
- Response top-level keys: success, data

### 24. GET /PatientDashboard/GetRelationships
- URL pattern: `https://drkemr.com/PatientDashboard/GetRelationships`
- UI sections seen: Dashboard load, Documents, Insurance
- Capture count: 3
- Typical status: 200
- Purpose: Relationship lookup dictionary
- Response top-level keys: success, data

### 25. POST /hubs/messaging/negotiate
- URL pattern: `https://drkemr.com/hubs/messaging/negotiate?negotiateVersion={value}`
- UI sections seen: Dashboard load, Documents, Insurance
- Capture count: 3
- Typical status: 200
- Purpose: General JSON endpoint
- Response top-level keys: negotiateVersion, connectionId, connectionToken, availableTransports
