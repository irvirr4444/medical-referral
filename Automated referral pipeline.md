# Automated Referral → Scheduling → Visit Pipeline

## Purpose

This document describes how the referral workflow will operate as an automated system.

The system processes information available through the referral inbox, PDF attachments, Monday.com, DRK, and the routing schedule. Human involvement remains required for telephone calls, uncertain or duplicate-record review, provider confirmation, clinical decisions, exception handling, and management approvals.

## General Rules

1. Every automated action is recorded with its result, timestamp, and related referral.
2. The same email or PDF cannot create the same referral more than once.
3. An actual value or an explicitly stated negative value counts as information. For example, `No insurance` and `No home-health or hospice agency` are complete values.
4. A field is incomplete when the information is not stated or cannot be extracted confidently.
5. All seven required fields must be complete before the referral proceeds.
6. Exact and probable duplicate matches block record creation until they are reviewed.
7. Clinical conditions and discharge decisions are never determined by the automation. The system acts only on information recorded by authorized staff.

---

## 1. Referral Intake

### 1.1 Referral received

A referral arrives at the information inbox as an email or fax with one or more PDF attachments.

Possible referral sources include:

- skilled nursing facilities;
- assisted living facilities;
- hospitals;
- home-health agencies;
- physician offices; and
- self-referrals.

The email, its attachments, and their identifiers are recorded so that the same referral cannot be processed twice.

### 1.2 PDF processed

Each valid referral PDF is read automatically. The following seven required fields are extracted:

1. Patient name
2. Date of birth
3. Contact number
4. Patient address
5. Home-health or hospice agency
6. Wound or clinical information
7. Insurance information

Each extracted field is classified as:

- **Complete:** a clear value was extracted;
- **Explicitly none:** the referral clearly states that the patient has no value for that field;
- **Missing:** the referral does not state the information; or
- **Unclear:** information is present but cannot be extracted confidently.

An explicitly stated value such as `No insurance` is considered complete. An unstated insurance field is considered missing.

### 1.3 Inbox draft prepared

A private draft reply is created on the original email thread. The draft is visible to the information-box agent but is not sent automatically.

The draft contains:

- the seven extracted fields written clearly in text;
- a summary of whether the referral is complete;
- a list of missing or unclear information;
- any possible duplicate warning; and
- the recommended next action.

### 1.4 Duplicate check completed

The patient is checked against existing records in both Monday.com and DRK.

The comparison uses all available identifying information, including:

- patient name;
- date of birth;
- address and location;
- telephone number; and
- other available patient identifiers.

The result is classified as:

- **Clearly distinct:** no credible duplicate was found, so processing continues;
- **Probable duplicate:** record creation is blocked for review; or
- **Exact duplicate:** record creation is blocked for review.

The automation never creates a new Monday.com or DRK patient while a possible duplicate remains unresolved.

### 1.5 Completeness reviewed

The referral proceeds only when all seven required fields contain either a clear value or an explicitly stated negative value.

If any required field is missing or unclear:

1. The referral is placed in a `Needs Information` state.
2. The information-box manager is notified.
3. The missing or unclear fields are shown in the private email draft.
4. The information-box agent calls the referral partner to confirm the referral and request the missing information.
5. The extracted referral is updated when the information is received.

If the referral partner cannot be reached, the PDF and the missing-information summary are sent to the assigned marketer for human follow-up. The referral remains blocked until all seven fields are completed.

---

## 2. Handoff and Assignment

### 2.1 Referral approved for handoff

The referral becomes ready for handoff when:

- all seven required fields are complete;
- no duplicate review is pending; and
- any uncertain extraction has been reviewed.

### 2.2 Case manager assigned

The patient's location is matched against the case-manager territory list.

- If exactly one case manager matches, that case manager is assigned automatically.
- If no case manager or more than one case manager matches, the assignment is blocked and the information-box manager is notified for review.

The automatic assignment becomes available after the authoritative case-manager and territory list is provided.

### 2.3 Acknowledgement prepared

An acknowledgement is prepared for the referral source. It includes the assigned case manager and the confirmed referral information.

The information-box agent reviews and sends the acknowledgement on the existing email thread.

### 2.4 Monday.com and DRK handoff completed

The approved referral is processed through independent Monday.com and DRK operations:

#### Monday.com

- A new Master Sheet item is created.
- The information-box portion of the item is populated.
- The `Sent By` value is recorded.
- The assigned case manager is recorded.
- The source PDF is attached or linked.

#### DRK

- A duplicate check is completed again immediately before creation.
- The patient chart is created from the approved referral information.
- The source PDF and extracted information are associated with the chart where supported.

Monday.com and DRK are tracked separately. If one operation succeeds and the other fails, the successful operation is not repeated. Only the failed operation is retried.

### 2.5 Ownership transferred

When the handoff is complete, the assigned case manager becomes responsible for provider selection and scheduling.

---

## 3. Provider Selection and Scheduling

### 3.1 Provider selected

The assigned case manager's approved provider list and territory rules are used to identify an appropriate company provider.

- If one provider clearly matches, that provider is suggested or selected according to the approved routing rules.
- If the rules do not produce a clear provider, the case is flagged for human review.
- If no provider covers the patient's location, Nicole is notified for review. The patient is not discharged automatically.

Automatic provider selection becomes available after the authoritative provider, territory, and case-manager assignment lists are provided.

### 3.2 Provider notified

The selected company provider is recorded in Monday.com. The Monday.com provider-selection process automatically sends the configured notification to that provider.

The `Referral sent to provider` value records whether the provider notification has been completed.

### 3.3 Appointment times suggested

The provider's routing schedule is read automatically. Available appointment times that fit the patient's location and the provider's route are identified and presented to the case manager.

The provider's acceptance and scheduling communication remain human actions. The suggestions reduce the time needed to inspect the schedule but do not replace provider confirmation.

### 3.4 Provider response monitored

The provider response is monitored for one hour.

- **Provider confirms:** the patient is scheduled according to the confirmed availability, normally within 24–48 hours.
- **Provider does not confirm within one hour:** the case is flagged for review, and the case manager determines the best placement using the provider's schedule.

### 3.5 Scheduling recorded

When an appointment is confirmed:

- the appointment date is recorded in Monday.com;
- the scheduled status is updated;
- the case-manager portion of Monday.com is completed;
- the corresponding DRK information is updated; and
- the referral is marked as scheduled.

---

## 4. End-of-Day Scheduling Check

### 4.1 Scheduling status checked

Immediately after the end-of-day deadline, every active referral is checked for:

- scheduled status;
- appointment date; and
- scheduling-complete status.

### 4.2 Unscheduled referrals flagged

If a referral is not scheduled:

1. A scheduling exception is created immediately after the end-of-day check.
2. The lead and responsible team members are alerted.
3. The alert includes the patient, assigned case manager, provider status, current scheduling information, and known blocker.
4. Management is notified about the case.
5. Management determines whether the problem can be resolved by the case manager or lead or requires further escalation.

The automation identifies and communicates the exception. The team and management remain responsible for resolving it.

### 4.3 Scheduled referrals advanced

When scheduling is complete, the patient is added to the weekly schedule and enters the weekly visit cycle.

---

## 5. Weekly Visit Cycle

### 5.1 Weekly patients monitored

The active weekly schedule is monitored using Monday.com, the routing schedule, and DRK.

The automation reads the recorded visit and patient statuses. It does not make clinical determinations.

### 5.2 Visit outcome processed

The DRK progress note and available status information are checked after the scheduled visit.

#### Patient seen

- The visit is recorded as completed.
- The initial visit is marked `SEEN` in Monday.com when applicable.
- The consecutive-not-seen counter is reset.
- The patient remains in the weekly cycle unless another recorded status changes the workflow.

#### Patient not seen

- The visit is marked `NOT SEEN`.
- The patient is returned to the next weekly scheduling cycle unless placed on hold.
- The consecutive-not-seen counter is increased.

When the patient has not been seen for three consecutive weeks:

1. A discharge-review request is created with the reason `Noncompliance`.
2. The case manager and upper management are notified.
3. Management reviews and approves or rejects the discharge.

The patient is never discharged automatically because of missed visits.

### 5.3 Healed or expired status processed

The visit status recorded by authorized staff is monitored for healed or expired patients.

#### Wound healed

- The recorded healed status triggers a QA review request.
- The provider and QA workflow remains human-controlled.
- The patient is discharged only after the required review and approval are recorded.

#### Patient expired

- The recorded expired status triggers removal from future scheduling.
- A discharge-approval request is created.
- The patient is discharged only after the required approval is recorded.

The automation responds to the recorded clinical status but does not determine that the wound is healed or that the patient has expired.

### 5.4 Hold status processed

When an authorized user records that a patient is on hold because of hospitalization, vacation, or another reason:

- the patient is removed from the active weekly schedule;
- the patient is added to the holds workflow or holds list; and
- the hold status is monitored.

When an authorized user records that the patient is ready to return:

- the patient is removed from the holds workflow;
- the patient is returned to the weekly visit cycle; and
- scheduling resumes.

The automation validates and processes recorded hold statuses. The decision to place or remove a patient from hold remains a human decision.

---

## 6. Human-Controlled Actions

The following actions remain human-controlled:

- calling the referral partner;
- marketer follow-up;
- reviewing unclear extraction results;
- resolving probable or exact duplicate matches;
- resolving unclear case-manager or provider assignments;
- confirming provider availability;
- choosing a schedule when the provider does not respond;
- resolving scheduling exceptions;
- making clinical decisions;
- recording healed, expired, treatment, and hold decisions;
- QA review;
- discharge approval; and
- management escalation decisions.

The automation prepares the information, monitors deadlines and statuses, creates alerts, records outcomes, and executes approved system actions.

---

## 7. Required Configuration and Access

The complete pipeline requires:

- authoritative case-manager territory assignments;
- authoritative company-provider territory assignments;
- information-inbox access;
- Monday.com access and confirmed provider-notification behavior;
- DRK access;
- routing-schedule access and schedule structure;
- the complete list of Monday.com patient and visit status values;
- marketer assignments by referral source;
- end-of-day deadline and time zone;
- notification recipients and escalation rules; and
- any required RingRx information.

