# DRK Endpoint Index (Grouped by Business Domain)

- Source catalog: `endpoint_catalog_20260729T101936Z.json`
- Total captured records: **75**
- Unique endpoints: **25**

## Documents (1 endpoints)

### Documents-1: GET /PatientDashboard/GetCustomScans/{id}
- URL pattern: `https://drkemr.com/PatientDashboard/GetCustomScans/{id}?skip={value}&take={value}`
- Triggered from UI sections: Dashboard load, Documents, Insurance
- Capture count: 3
- Status codes seen: 200
- Response top-level keys: success, data

## Insurance (2 endpoints)

### Insurance-1: GET /PatientDashboard/GetEligibilityHistory/{id}
- URL pattern: `https://drkemr.com/PatientDashboard/GetEligibilityHistory/{id}`
- Triggered from UI sections: Dashboard load, Documents, Insurance
- Capture count: 3
- Status codes seen: 200
- Response top-level keys: success, data

### Insurance-2: GET /PatientDashboard/GetInsurances/{id}
- URL pattern: `https://drkemr.com/PatientDashboard/GetInsurances/{id}`
- Triggered from UI sections: Dashboard load, Documents, Insurance
- Capture count: 3
- Status codes seen: 200
- Response top-level keys: success, data

## Billing (1 endpoints)

### Billing-1: GET /PatientDashboard/GetPatientBilling
- URL pattern: `https://drkemr.com/PatientDashboard/GetPatientBilling?patientId={patientId}`
- Triggered from UI sections: Dashboard load, Documents, Insurance
- Capture count: 3
- Status codes seen: 200
- Response top-level keys: success, result, isWriteOffApprover, writeOffCeiling

## Clinical (9 endpoints)

### Clinical-1: GET /Dashboard/CheckDoseSpotAccess
- URL pattern: `https://drkemr.com/Dashboard/CheckDoseSpotAccess`
- Triggered from UI sections: Dashboard load, Documents, Insurance
- Capture count: 3
- Status codes seen: 200
- Response top-level keys: hasAccess, message

### Clinical-2: GET /Dashboard/GetUserLabInbox
- URL pattern: `https://drkemr.com/Dashboard/GetUserLabInbox`
- Triggered from UI sections: Dashboard load, Documents, Insurance
- Capture count: 3
- Status codes seen: 200
- Response top-level keys: success, data, isBackfill

### Clinical-3: GET /Dashboard/GetUserLabInboxCount
- URL pattern: `https://drkemr.com/Dashboard/GetUserLabInboxCount`
- Triggered from UI sections: Dashboard load, Documents, Insurance
- Capture count: 3
- Status codes seen: 200
- Response top-level keys: success, data, unread, total, isBackfill

### Clinical-4: GET /Encounter/GetFiltered
- URL pattern: `https://drkemr.com/Encounter/GetFiltered?page={value}&pageSize={value}&signatureStatus={value}&myTurnOnly={value}&fromDate={value}&toDate={value}`
- Triggered from UI sections: Dashboard load, Documents, Insurance
- Capture count: 3
- Status codes seen: 200
- Response top-level keys: encounters, totalCount, currentPage, pageSize, totalPages, signedCount, unsignedCount, patient

### Clinical-5: GET /PatientDashboard/GetDoseSpotAllergies/{id}
- URL pattern: `https://drkemr.com/PatientDashboard/GetDoseSpotAllergies/{id}`
- Triggered from UI sections: Dashboard load, Documents, Insurance
- Capture count: 3
- Status codes seen: 200
- Response top-level keys: success, data

### Clinical-6: GET /PatientDashboard/GetDoseSpotMedications/{id}
- URL pattern: `https://drkemr.com/PatientDashboard/GetDoseSpotMedications/{id}`
- Triggered from UI sections: Dashboard load, Documents, Insurance
- Capture count: 3
- Status codes seen: 200
- Response top-level keys: success, data

### Clinical-7: GET /PatientDashboard/GetEncounters/{id}
- URL pattern: `https://drkemr.com/PatientDashboard/GetEncounters/{id}?page={value}&pageSize={value}`
- Triggered from UI sections: Dashboard load, Documents, Insurance
- Capture count: 3
- Status codes seen: 200
- Response top-level keys: success, data

### Clinical-8: GET /PatientDashboard/GetLabResultCount/{id}
- URL pattern: `https://drkemr.com/PatientDashboard/GetLabResultCount/{id}`
- Triggered from UI sections: Dashboard load, Documents, Insurance
- Capture count: 3
- Status codes seen: 200
- Response top-level keys: success, data, unread, total

### Clinical-9: GET /PatientDashboard/GetQuickNotes/{id}
- URL pattern: `https://drkemr.com/PatientDashboard/GetQuickNotes/{id}`
- Triggered from UI sections: Dashboard load, Documents, Insurance
- Capture count: 3
- Status codes seen: 200
- Response top-level keys: success, data

## Workflow (8 endpoints)

### Workflow-1: GET /BvPipeline/API/Automation/Tasks
- URL pattern: `https://drkemr.com/BvPipeline/API/Automation/Tasks?scope={value}&page={value}&pageSize={value}`
- Triggered from UI sections: Dashboard load, Documents, Insurance
- Capture count: 3
- Status codes seen: 200
- Response top-level keys: items, openCount, totalCount, page, pageSize, totalPages, isManager

### Workflow-2: GET /Login/ValidateUser
- URL pattern: `https://drkemr.com/Login/ValidateUser?userName=[REDACTED]&password=[REDACTED]&timeZoneId={value}`
- Triggered from UI sections: Dashboard load, Documents, Insurance
- Capture count: 3
- Status codes seen: 200
- Response top-level keys: data, isSuccessfull

### Workflow-3: GET /PatientDashboard/API/GetBvPipelineStatus/{id}
- URL pattern: `https://drkemr.com/PatientDashboard/API/GetBvPipelineStatus/{id}`
- Triggered from UI sections: Dashboard load, Documents, Insurance
- Capture count: 3
- Status codes seen: 200
- Response top-level keys: success, data

### Workflow-4: GET /PatientDashboard/GetAdmissionSummary/{id}
- URL pattern: `https://drkemr.com/PatientDashboard/GetAdmissionSummary/{id}`
- Triggered from UI sections: Dashboard load, Documents, Insurance
- Capture count: 3
- Status codes seen: 200
- Response top-level keys: success, data

### Workflow-5: GET /PatientDashboard/GetCommunicationsPaginated/{id}
- URL pattern: `https://drkemr.com/PatientDashboard/GetCommunicationsPaginated/{id}?page={value}&pageSize={value}`
- Triggered from UI sections: Dashboard load, Documents, Insurance
- Capture count: 3
- Status codes seen: 200
- Response top-level keys: success, data

### Workflow-6: GET /PatientDashboard/GetPatientDemographics/{id}
- URL pattern: `https://drkemr.com/PatientDashboard/GetPatientDemographics/{id}`
- Triggered from UI sections: Dashboard load, Documents, Insurance
- Capture count: 3
- Status codes seen: 200
- Response top-level keys: success, data

### Workflow-7: GET /PatientDashboard/GetRelationships
- URL pattern: `https://drkemr.com/PatientDashboard/GetRelationships`
- Triggered from UI sections: Dashboard load, Documents, Insurance
- Capture count: 3
- Status codes seen: 200
- Response top-level keys: success, data

### Workflow-8: POST /hubs/messaging/negotiate
- URL pattern: `https://drkemr.com/hubs/messaging/negotiate?negotiateVersion={value}`
- Triggered from UI sections: Dashboard load, Documents, Insurance
- Capture count: 3
- Status codes seen: 200
- Response top-level keys: negotiateVersion, connectionId, connectionToken, availableTransports

## Messaging (4 endpoints)

### Messaging-1: GET /DirectMessage/UnreadCount
- URL pattern: `https://drkemr.com/DirectMessage/UnreadCount`
- Triggered from UI sections: Dashboard load, Documents, Insurance
- Capture count: 3
- Status codes seen: 200
- Response top-level keys: success, count

### Messaging-2: POST /Mailbox/GetMessages
- URL pattern: `https://drkemr.com/Mailbox/GetMessages`
- Triggered from UI sections: Dashboard load, Documents, Insurance
- Capture count: 3
- Status codes seen: 200
- Response top-level keys: success, data

### Messaging-3: GET /Mailbox/GetRecipients
- URL pattern: `https://drkemr.com/Mailbox/GetRecipients`
- Triggered from UI sections: Dashboard load, Documents, Insurance
- Capture count: 3
- Status codes seen: 200
- Response top-level keys: success, data

### Messaging-4: GET /Mailbox/GetTemplates
- URL pattern: `https://drkemr.com/Mailbox/GetTemplates`
- Triggered from UI sections: Dashboard load, Documents, Insurance
- Capture count: 3
- Status codes seen: 200
- Response top-level keys: success, data
