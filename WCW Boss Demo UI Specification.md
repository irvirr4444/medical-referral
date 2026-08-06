# WCW Referral Automation — Boss Demo UI Specification

## Document purpose

This document specifies the single-page demonstration dashboard that will be shown to the leadership of West Coast Wound (WCW).

It is intended to be handed to a UI-generation agent such as Claude. The deliverable is a polished, clickable frontend demonstration—not a production application.

The dashboard must make the business value of the automation immediately understandable:

- less repetitive administrative work;
- less manual reading and re-entry;
- faster referral preparation;
- earlier detection of missing information;
- protection against duplicate patient creation;
- fewer disconnected handoffs;
- less manual deadline and status monitoring;
- greater referral capacity for the existing team; and
- better management visibility.

The main story is not “we built scripts.” The main story is:

> WCW employees can move from manually processing every detail to reviewing exceptions, making decisions, and confirming prepared actions.

---

## 1. Scope and honesty requirements

### 1.1 This is one dashboard

Build one cohesive dashboard experience. Do not create separate executive and operator applications.

The dashboard can use:

- expandable panels;
- drawers;
- modals;
- tabs inside a selected referral;
- animated workflow states; and
- contextual action panels.

However, the user should remain inside one central WCW Referral Automation dashboard.

### 1.2 This is a frontend demonstration

For the initial version:

- all dashboard metrics may use invented demonstration data;
- all seven patient identities and clinical details must be fictional;
- button clicks may simulate processing and update local frontend state;
- no live Outlook, Monday.com, DRK, Supabase, Anthropic, or OpenAI connection is required;
- no real production write is required;
- no login or production authentication is required; and
- no backend is required unless the UI framework needs a minimal local server.

The experience should still feel realistic. Actions should produce visible progress, state transitions, timelines, results, and impact calculations.

### 1.3 Label invented numbers clearly

Display a small but visible label such as:

> Demo Mode · Illustrative workflow and impact data

Where financial, time-saving, workload, or staffing-equivalent figures appear, add:

> Illustrative estimate based on configurable workflow assumptions. Replace with measured WCW operational data.

Do not present invented figures as audited WCW results.

### 1.4 Describe headcount impact carefully

Do not say:

- “Employees eliminated”
- “Headcount reduced”
- “These automations replace the intake team”
- “WCW no longer needs case managers”

Use:

- “Equivalent staff capacity returned”
- “More referrals handled by the existing team”
- “Less repetitive administrative work”
- “Reduced administrative overload”
- “Growth without proportional administrative hiring”
- “Employees can focus on calls, exceptions, scheduling, and patient coordination”

The dashboard may show an FTE-capacity equivalent, but it must be described as capacity—not an employee-reduction commitment.

### 1.5 Protect patient information

The demo can visually represent the seven emails and attached PDFs from the referral inbox, but the generated demo should use invented patient data.

If actual referral PDFs or actual Outlook messages are added later, use only:

- explicitly approved material;
- deidentified copies; or
- a presentation environment where every attendee is authorized to view the PHI.

Never expose:

- `.env` values;
- credentials;
- API keys;
- access tokens;
- unrelated inbox messages; or
- unauthorized patient information.

---

## 2. Primary executive message

The dashboard should answer these questions within the first 15 seconds:

1. What work did the automation perform?
2. How much employee time could it return?
3. How much repetitive work could it remove?
4. What mistakes or delays could it prevent?
5. What still requires human judgment?

Use this primary headline:

> From Manual Referral Processing to Exception-Based Review

Use this supporting statement:

> WCW Referral Automation reads incoming referrals, organizes the required patient information, identifies missing details and possible duplicates, prepares Monday.com and DRK handoffs, and keeps employees in control of every important decision.

Use this closing statement:

> The automation does not replace WCW’s clinical or operational judgment. It removes repetitive intake work, returns capacity to employees, reduces avoidable rework, and allows the existing team to safely handle greater referral volume.

---

## 3. Demonstration narrative

The presentation should tell one continuous story.

### Step 1: Seven referrals arrive

The dashboard begins with seven referral emails waiting in the WCW information inbox.

Show:

- sender;
- subject;
- received time;
- PDF filename;
- PDF page count; and
- current state.

Primary action:

> Run Referral Automation

### Step 2: The automation processes the seven referrals

When the action is clicked, show staged progress rather than a generic spinner:

1. Connecting to referral inbox
2. Discovering new referral emails
3. Validating PDF attachments
4. Checking that attachments were not already processed
5. Reading referral documents
6. Verifying extracted information against the source
7. Evaluating the seven required fields
8. Searching for possible Monday.com duplicates
9. Preparing Monday.com records
10. Preparing DRK drafts
11. Building human-review summaries
12. Completing the automation batch

The animation may take approximately 8–12 seconds. It should feel active and comprehensible, not slow.

### Step 3: Results appear

The seven referrals move into different realistic states:

- four ready for confirmation;
- two requiring information or clarification; and
- one blocked as a possible duplicate.

The dashboard metrics update visibly.

### Step 4: A complete referral is reviewed

The presenter selects a complete referral.

Show:

- the source PDF;
- extracted patient information;
- seven-field readiness;
- source evidence;
- duplicate result;
- Monday.com preview;
- DRK draft preview;
- automation-impact receipt; and
- human confirmation action.

### Step 5: The referral is confirmed

The presenter clicks:

> Confirm Referral

Show:

- confirmation recorded;
- all seven required fields complete;
- no blocking duplicate;
- immutable review snapshot validated;
- Monday.com handoff ready; and
- DRK draft ready.

### Step 6: Destination readiness is demonstrated

After confirmation, visually branch the referral:

```text
                        ┌── Monday.com Ready
Received → Extracted → Reviewed → Confirmed
                        └── DRK Draft Ready
```

The frontend may simulate:

- “Send to Monday.com”
- “Open Monday.com Record”
- “Preview DRK Draft”
- “Open DRK Assisted Entry”

Use accurate language:

- Monday.com may be shown as ready to create or simulated as created.
- DRK must be shown as a prepared draft or assisted-entry workflow, not a completed production patient creation.

### Step 7: Management value is summarized

Return focus to:

- time returned;
- manual actions avoided;
- incomplete referrals detected;
- duplicate risk prevented;
- destination records prepared;
- active exceptions; and
- equivalent staff capacity.

---

## 4. Main workflow displayed in the dashboard

Use this high-level workflow:

> Received → Extracted → Reviewed → Confirmed → Monday.com Ready + DRK Draft Ready → Assigned → Scheduling → Weekly Monitoring → Exception or Completion

Visually distinguish:

### Demonstrable current intake and handoff capabilities

- Outlook referral intake
- PDF validation
- duplicate attachment protection
- referral extraction
- source-verification pass
- seven-field completeness evaluation
- missing and unclear field detection
- Monday.com duplicate review
- human-readable review summary
- sender/thread-bound confirmation concept
- Monday.com preview
- guarded Monday.com creation concept
- DRK draft preparation
- retry and audit tracking

### Planned or conceptual workflow capabilities

- automatic case-manager territory assignment
- provider selection
- routing-schedule matching
- provider-response monitoring
- appointment scheduling
- end-of-day exception monitoring
- weekly visit monitoring
- three-consecutive-not-seen detection
- hold monitoring
- healed and expired workflows
- QA review
- discharge approval

The planned stages can be shown to explain the larger vision, but label them:

> Planned workflow automation

Do not imply that every stage is already operating in production.

---

## 5. Executive impact summary

The business-impact section should be more prominent than technical system details.

### 5.1 Demo batch metrics

Use these invented values for the seven-referral demonstration:

- 7 referral emails received
- 7 PDFs processed
- 132 PDF pages analyzed
- 189 patient and clinical values extracted
- 49 required intake fields evaluated
- 7 Monday.com duplicate searches performed
- 7 Monday.com records prepared
- 7 DRK drafts prepared
- 2 incomplete or unclear referrals identified
- 1 probable duplicate blocked
- 4 referrals ready for confirmation
- 63 repetitive manual actions avoided

### 5.2 Demonstration time model

Use these illustrative assumptions:

- average manual processing time: 36 minutes per referral;
- average automation-assisted review time: 8 minutes per referral;
- estimated time returned: 28 minutes per referral; and
- estimated reduction in administrative touch time: 78%.

For the seven-referral batch, show:

- manual workflow estimate: 4 hours 12 minutes;
- automation-assisted estimate: 56 minutes; and
- estimated staff time returned: 3 hours 16 minutes.

### 5.3 Annual illustrative projection

Use:

- 7 referrals per working day;
- 250 working days per year;
- 1,750 referrals per year;
- approximately 817 administrative hours returned per year; and
- approximately 0.39 full-time-equivalent capacity returned.

Display:

> Capacity returned to WCW employees—not guaranteed payroll reduction.

### 5.4 Recommended primary impact cards

Show approximately six high-impact cards:

1. **3h 16m** — Estimated time returned today
2. **63** — Manual actions avoided
3. **132** — PDF pages analyzed
4. **14** — Destination records prepared
5. **2** — Incomplete referrals found early
6. **1** — Possible duplicate blocked

Secondary metrics can include:

- 78% less administrative touch time;
- 4 referrals ready for confirmation;
- 817 projected hours returned annually; and
- 0.39 FTE-equivalent capacity.

---

## 6. Before and after: complete WCW workflow

This comparison is one of the most important parts of the demonstration.

## 6.1 Referral intake

### Before

1. Open the referral email.
2. Download the PDF.
3. Verify that the attachment is valid.
4. Read every page.
5. Locate the patient’s name.
6. Locate the date of birth.
7. Locate contact information.
8. Locate the address.
9. Locate home-health or hospice information.
10. Locate wound and clinical information.
11. Locate insurance information.
12. Determine which required information is missing.
13. Search Monday.com for an existing patient.
14. Search DRK for an existing patient.
15. Contact the referral partner.
16. Re-enter information into Monday.com.
17. Re-enter information into DRK.
18. Track whether intake was completed.
19. Follow up again if information remains missing.

### With WCW automation

1. Review extracted information.
2. Review highlighted missing or uncertain fields.
3. Resolve possible duplicate warnings.
4. Confirm the referral.
5. Monday.com and DRK records are prepared.

### Value statement

> Employees stop searching every document for routine information. Their attention is directed to referrals and fields that require judgment.

## 6.2 Handoff and assignment

### Before

1. Determine the patient’s geographic area.
2. Determine the correct case manager.
3. Prepare an acknowledgement email.
4. Attach and forward the PDF.
5. Send the referral to the case manager.
6. Forward the referral to the face-sheet team.
7. Enter information into the Monday.com Master Sheet.
8. Fill the “Sent By” field.
9. Track whether each handoff occurred.

### With the proposed automation

1. Patient location is read from the referral.
2. The appropriate case manager is suggested from approved territory rules.
3. An acknowledgement is prepared automatically.
4. The Monday.com handoff is prepared.
5. The DRK draft is prepared.
6. Handoff events are recorded.
7. Employees review exceptions and confirm.

### Value statement

> One confirmed referral can create a coordinated handoff instead of several disconnected manual tasks.

## 6.3 Provider selection and scheduling

### Before

1. Review the patient’s location.
2. Search the case manager’s provider list.
3. Determine which provider covers the territory.
4. Open routing software.
5. Inspect the provider’s schedule.
6. Contact the provider.
7. Wait for a response.
8. Track the one-hour response window.
9. Decide where the patient fits if the provider does not respond.
10. Update Monday.com.
11. Update DRK.
12. Continue checking until scheduling is complete.

### With the proposed automation

1. Matching providers are suggested from territory rules.
2. Relevant routing windows are displayed.
3. Provider-response deadlines are monitored.
4. Unanswered referrals are highlighted.
5. Confirmed scheduling information is prepared for Monday.com and DRK.
6. Human staff select and confirm the final appointment.

### Value statement

> Automation performs searching, monitoring, and preparation. The case manager retains control of provider and scheduling decisions.

## 6.4 End-of-day scheduling check

### Before

1. Open Monday.com.
2. Review every active referral.
3. Check scheduled status.
4. Check appointment date.
5. Check scheduling-complete status.
6. Identify blank or overdue referrals.
7. Contact case managers through Teams.
8. Ask why each patient is not scheduled.
9. Determine whether the issue is resolvable.
10. Prepare management escalation emails.
11. Maintain a separate tracking spreadsheet.
12. Continue following up.

### With the proposed automation

1. Active referrals are checked automatically.
2. Unscheduled referrals are identified.
3. The responsible case manager and known blocker are displayed.
4. Existing Monday.com notifications are verified.
5. Uncovered exceptions are prepared for escalation.
6. Management reviews one organized exception list.

### Value statement

> Management reviews exceptions instead of manually auditing every referral.

## 6.5 Weekly visit cycle

### Before

1. Review the weekly schedule.
2. Open DRK progress notes.
3. Determine whether each patient was seen.
4. Update visit status in Monday.com.
5. Reschedule patients who were not seen.
6. Count consecutive missed visits.
7. Identify patients not seen for three weeks.
8. Prepare noncompliance discharge-review requests.
9. Monitor healed and expired statuses.
10. Notify QA and management.
11. Maintain hold lists.
12. Remove held patients from active scheduling.
13. Check whether held patients are ready to return.
14. Return eligible patients to the weekly cycle.

### With the proposed automation

1. Recorded visit statuses are monitored.
2. Seen and not-seen outcomes are organized.
3. Consecutive missed visits are counted.
4. Three-week noncompliance creates a discharge-review request.
5. Healed or expired statuses initiate the appropriate human review.
6. Hold patients are removed from active scheduling.
7. Return-ready patients re-enter the weekly cycle.
8. Human staff retain all clinical and discharge decisions.

### Value statement

> The automation remembers deadlines, counts repeated events, and prepares follow-up work so employees do not have to maintain parallel tracking systems.

---

## 7. Seven fictional demonstration referrals

All names, email addresses, organizations, identifiers, diagnoses, and clinical details in this section are fictional.

## 7.1 Maria Alvarez

- Email sender: `referrals@sunrise-homehealth.example`
- Email subject: `New Wound Care Referral — Maria Alvarez`
- Referral source: Sunrise Home Health
- PDF filename: `Alvarez_Maria_Referral_08062026.pdf`
- PDF pages: 18
- Date of birth: February 14, 1958
- Phone: `(555) 014-2381`
- Address: `4821 Palm Grove Drive, Riverside, CA 92501`
- Home health/hospice: Sunrise Home Health
- Diagnosis: Diabetic ulcer of left heel with fat layer exposed
- Insurance: Medicare
- Requested service: Wound evaluation and ongoing treatment
- Required fields: 7/7 complete
- Duplicate status: Clear
- Outcome: Ready for confirmation
- Estimated manual time avoided: 29 minutes
- Demo purpose: Ideal straight-through referral

## 7.2 James Carter

- Email sender: `discharge@oakvalley-hospital.example`
- Email subject: `Hospital Discharge Referral — James Carter`
- Referral source: Oak Valley Hospital
- PDF filename: `Carter_James_Discharge_Packet.pdf`
- PDF pages: 24
- Date of birth: September 3, 1946
- Phone: `(555) 017-9204`
- Address: `1708 Magnolia Avenue, Long Beach, CA 90806`
- Home health/hospice: Pacific Recovery Home Health
- Diagnosis: Stage 3 pressure injury of sacrum
- Insurance: Medicare with supplemental coverage
- Requested service: Post-discharge wound management
- Required fields: 7/7 complete
- Duplicate status: Clear
- Outcome: Ready for confirmation
- Estimated manual time avoided: 31 minutes
- Demo purpose: Long hospital packet with substantial reading avoided

## 7.3 Linda Nguyen

- Email sender: `intake@harborview-alf.example`
- Email subject: `Resident Wound Referral — Linda Nguyen`
- Referral source: Harborview Assisted Living
- PDF filename: `Nguyen_Linda_Wound_Referral.pdf`
- PDF pages: 13
- Date of birth: June 22, 1951
- Phone: `(555) 011-6638`
- Address: `921 Harbor View Lane, San Pedro, CA 90731`
- Home health/hospice: No agency documented
- Diagnosis: Venous stasis ulcer of right lower leg
- Insurance: Missing
- Requested service: Initial wound evaluation
- Required fields: 6/7 complete
- Duplicate status: Clear
- Outcome: Needs insurance information
- Next action: Contact referral partner
- Estimated manual review time avoided: 23 minutes
- Demo purpose: Missing information detected early

## 7.4 Robert Williams

- Email sender: `referrals@carebridge-hh.example`
- Email subject: `Urgent Referral — Robert Williams`
- Referral source: CareBridge Home Health
- PDF filename: `Williams_Robert_Referral.pdf`
- PDF pages: 21
- Date of birth: November 18, 1962
- Phone: `(555) 013-4472`
- Address: `605 Cypress Street, Anaheim, CA 92805`
- Home health/hospice: CareBridge Home Health
- Diagnosis: Diabetic foot ulcer of right midfoot
- Insurance: Medicare Advantage
- Requested service: Urgent wound assessment
- Required fields: 7/7 complete
- Duplicate status: Probable duplicate
- Existing candidate: Same normalized patient name and date of birth
- Outcome: Creation blocked for human review
- Estimated duplicate-related rework prevented: 45 minutes
- Demo purpose: Duplicate protection and fail-safe behavior

## 7.5 Evelyn Brooks

- Email sender: `woundreferrals@northstar-snf.example`
- Email subject: `Wound Care Consult — Evelyn Brooks`
- Referral source: Northstar Skilled Nursing
- PDF filename: `Brooks_Evelyn_Consult.pdf`
- PDF pages: 16
- Date of birth: January 7, 1943
- Phone: Unclear; two conflicting numbers found
- Address: `2814 East Willow Street, Compton, CA 90221`
- Home health/hospice: Northstar Skilled Nursing
- Diagnosis: Post-surgical wound dehiscence
- Insurance: Medicare
- Requested service: Wound consultation and treatment plan
- Required fields: 6/7 complete
- Duplicate status: Clear
- Outcome: Needs clarification
- Next action: Contact referral partner to verify phone
- Demo purpose: Uncertain extraction safely escalated

## 7.6 Thomas Reed

- Email sender: `office@lakeside-vascular.example`
- Email subject: `Physician Referral — Thomas Reed`
- Referral source: Lakeside Vascular Clinic
- PDF filename: `Reed_Thomas_Vascular_Referral.pdf`
- PDF pages: 19
- Date of birth: April 29, 1955
- Phone: `(555) 018-3047`
- Address: `733 Lakewood Boulevard, Downey, CA 90240`
- Home health/hospice: Golden State Home Health
- Diagnosis: Arterial ulcer of left ankle
- Insurance: Blue Cross
- Requested service: Wound evaluation following vascular consultation
- Required fields: 7/7 complete
- Duplicate status: Clear
- Outcome: Ready for confirmation
- Estimated manual time avoided: 27 minutes
- Demo purpose: Physician-office referral

## 7.7 Patricia Johnson

- Email sender: `casework@community-care.example`
- Email subject: `New Patient Referral — Patricia Johnson`
- Referral source: Community Care Services
- PDF filename: `Johnson_Patricia_Referral.pdf`
- PDF pages: 21
- Date of birth: August 11, 1948
- Phone: `(555) 015-7819`
- Address: `449 West Rosecrans Avenue, Gardena, CA 90248`
- Home health/hospice: Explicitly documented as none
- Diagnosis: Pressure injury of right hip
- Insurance: Medicare
- Requested service: Wound assessment and treatment
- Required fields: 7/7 complete
- Duplicate status: Clear
- Outcome: Ready for confirmation
- Estimated manual time avoided: 28 minutes
- Demo purpose: Explicit negative value correctly treated as complete information

---

## 8. Required dashboard content

## 8.1 Header

Include:

- WCW Referral Automation title;
- “Demo Mode” badge;
- current demo date;
- information-inbox status;
- “7 new referrals” indicator; and
- primary “Run Referral Automation” button.

Do not invent or recreate an official WCW logo unless an approved asset is provided.

## 8.2 Business-impact area

This should be the first major content block.

Include:

- estimated time returned;
- manual actions avoided;
- PDF pages analyzed;
- destination records prepared;
- incomplete referrals detected; and
- duplicates blocked.

Allow a small “How calculated” link or drawer explaining the illustrative assumptions.

## 8.3 Before-and-after summary

Include a concise version:

### Before

- Open email
- Download PDF
- Read every page
- Locate patient information
- Check required fields
- Search for duplicates
- Re-enter information into Monday.com
- Re-enter information into DRK
- Follow up on missing details
- Track completion

### With WCW automation

- Review extracted information
- Resolve exceptions
- Confirm
- Monday.com and DRK records are prepared

Headline:

> From approximately 36 minutes of manual processing to approximately 8 minutes of focused review.

Label the timing as illustrative.

## 8.4 Referral workflow

Display:

> Received → Extracted → Reviewed → Confirmed → Monday.com Ready + DRK Draft Ready

Each stage should show the number of referrals currently in that state.

Selecting a stage may filter or highlight the relevant referrals.

## 8.5 Seven-email referral queue

Show seven email-style referral cards or rows.

Each should display:

- fictional patient name;
- fictional sender;
- subject;
- received time;
- PDF filename;
- page count;
- completeness score;
- duplicate status;
- current workflow state;
- estimated minutes returned; and
- “Review Referral” action.

Provide status filters:

- All
- Ready
- Needs information
- Possible duplicate
- Confirmed

## 8.6 Selected-referral workspace

Opening a referral should keep the user inside the dashboard using a wide drawer, modal, or expandable workspace.

Include:

### Source document

- PDF viewer or realistic PDF placeholder;
- page navigation;
- page count;
- zoom control;
- attachment filename; and
- source email summary.

### Extracted information

- patient name;
- DOB;
- phone;
- address;
- home-health or hospice agency;
- wound or clinical information;
- insurance;
- referral source;
- referring provider;
- diagnoses;
- medications;
- allergies;
- requested services; and
- clinical summary.

### Field-quality status

Each required field should be classified as:

- Complete
- Explicitly none
- Missing
- Unclear

Use accessible status styling, not color alone.

### Evidence

Allow “View source” or “Show evidence” interactions displaying:

- source page;
- short evidence quote;
- confidence indicator; and
- verification status.

### Needs-attention panel

Pin important exceptions near the top:

- missing fields;
- unclear values;
- possible duplicates;
- unmatched agency;
- required human follow-up; and
- recommended next action.

## 8.7 Seven-field readiness

Always show:

1. Patient name
2. Date of birth
3. Contact number
4. Patient address
5. Home-health or hospice agency
6. Wound or clinical information
7. Insurance information

Show:

- `7/7 Complete`
- `6/7 Complete`
- `Blocked`
- `Manual Review Required`

Explicitly documented “No insurance” or “No home-health/hospice agency” should count as complete.

## 8.8 Duplicate comparison

For Robert Williams, provide a comparison between the incoming referral and an invented existing Monday.com patient.

Compare:

- name;
- date of birth;
- phone;
- address; and
- supporting identifiers.

Display:

> Creation blocked—human resolution required.

Actions may include:

- Mark as different patient
- Keep blocked
- Open existing record

These actions only update demo state.

## 8.9 Monday.com preview

Show:

- item name;
- target board;
- target group;
- direct column values;
- information retained in an update/comment;
- referring-agency relation;
- blockers;
- approval status; and
- write status.

Actions:

- Preview Monday.com Record
- Confirm Referral
- Send to Monday.com
- Open Monday.com Record

The simulated create should:

1. display a confirmation modal;
2. show processing steps;
3. change status to “Created”;
4. generate a fictional Monday item ID; and
5. prevent a second creation.

## 8.10 DRK draft preview

Show:

- demographics;
- contact information;
- address;
- emergency contact;
- admission information;
- referring source;
- insurance;
- diagnoses;
- requested service;
- unresolved lookup values; and
- duplicate-check status.

Actions:

- Preview DRK Draft
- Open DRK Assisted Entry
- Mark Ready for Face-Sheet Team

Always display:

> Draft prepared—final DRK patient creation remains human-controlled.

## 8.11 Confirmation experience

The selected referral should support:

- an Outlook-style review preview;
- a fictional reply box;
- a “Confirm” quick action;
- a “Request correction” quick action; and
- sender/thread validation indicators.

When confirmed, show:

```text
Confirmation recorded
✓ Authorized sender matched
✓ Original email thread matched
✓ Review snapshot validated
✓ Seven required fields complete
✓ No blocking duplicate detected
✓ Monday.com handoff ready
✓ DRK draft ready
```

## 8.12 Automation-impact receipt

Every processed referral should have an impact receipt.

Example:

```text
18 pages analyzed
27 patient and clinical values extracted
7 required fields verified
1 duplicate search completed
2 destination records prepared
12 repetitive manual actions avoided
29 estimated minutes returned to staff
```

The receipt should communicate business work accomplished, not model-token or API details.

## 8.13 Activity and audit timeline

Show realistic events:

- Referral email received
- PDF validated
- Attachment fingerprint recorded
- Extraction completed
- Source verification completed
- Required fields evaluated
- Duplicate search completed
- Review prepared
- Confirmation received
- Monday.com preview validated
- Monday.com record created or ready
- DRK draft prepared

Each event may show:

- timestamp;
- result;
- responsible system or role; and
- whether human action was required.

## 8.14 Larger workflow vision

Include a compact “What comes next” or “Full WCW workflow” section:

- Case-manager assignment
- Provider selection
- Route-aware scheduling
- One-hour provider-response monitoring
- End-of-day unscheduled referral check
- Weekly visit monitoring
- Three consecutive not-seen escalation
- Hold and return monitoring
- Healed/expired review
- QA and discharge approval

Label:

> Planned workflow automation based on the documented WCW process.

This section should reinforce expansion potential without distracting from the working intake story.

---

## 9. Required interactions

All interactions can be simulated in local frontend state.

### 9.1 Run Referral Automation

Before click:

- seven unprocessed emails;
- metrics show zero processed;
- workflow shows seven received.

During processing:

- show staged automation progress;
- progressively update referral statuses; and
- count pages, values, checks, and prepared records.

After processing:

- four ready;
- two need attention;
- one duplicate blocked;
- impact metrics populated; and
- completion summary displayed.

### 9.2 Review a referral

Open the selected-referral workspace and show the PDF, extracted data, evidence, readiness, previews, timeline, and impact receipt.

### 9.3 Confirm a referral

Confirmation should:

- validate readiness;
- reject blocked referrals;
- update the workflow;
- activate destination actions; and
- add an audit event.

### 9.4 Request missing information

For Linda Nguyen or Evelyn Brooks:

- show missing/unclear fields;
- allow “Prepare follow-up”;
- generate a fictional follow-up message;
- assign ownership to intake team or marketer; and
- update status to “Follow-up prepared.”

### 9.5 Resolve duplicate

For Robert Williams:

- open duplicate comparison;
- keep destination actions disabled until a choice is made;
- allow “Different patient” for demo purposes; and
- add a human-resolution audit event.

### 9.6 Send to Monday.com

Only enabled after confirmation and no blockers.

Show:

1. Validating approved snapshot
2. Mapping fields
3. Preparing item update
4. Creating Monday.com item
5. Verifying result

Then show:

> Monday.com item created successfully

Use a fictional item ID and demo URL unless a safe demo-board link is deliberately configured later.

### 9.7 Preview DRK draft

Show the prepared DRK information and emphasize that final creation remains human-controlled.

### 9.8 Impact calculator

Allow the presenter to change:

- referrals per day;
- manual minutes per referral;
- assisted-review minutes per referral;
- working days per year; and
- annual productive hours per employee.

Calculate:

- minutes returned per referral;
- hours returned per day;
- hours returned per week;
- hours returned per year;
- additional referral capacity; and
- FTE-equivalent capacity returned.

Keep the seven-referral demo assumptions as defaults.

---

## 10. Human-controlled decisions

The dashboard should clearly show that automation supports employees rather than making unauthorized clinical decisions.

Human-controlled actions include:

- calling the referral partner;
- confirming missing information;
- marketer follow-up;
- reviewing unclear extraction;
- resolving duplicates;
- confirming case-manager assignment;
- confirming provider selection;
- confirming provider availability;
- choosing the final schedule;
- resolving scheduling exceptions;
- making clinical decisions;
- recording healed or expired status;
- placing or removing a patient from hold;
- QA review;
- discharge approval; and
- management escalation decisions.

Use this supporting message:

> Automation prepares information, monitors workflow conditions, records outcomes, and executes approved system actions. WCW employees retain control of patient, clinical, scheduling, and management decisions.

---

## 11. Visual and writing direction

### 11.1 Tone

The dashboard should feel:

- credible;
- calm;
- operational;
- healthcare-appropriate;
- modern;
- safe; and
- executive-ready.

Avoid:

- playful consumer-app styling;
- excessive gradients;
- excessive animation;
- AI robot imagery;
- “magic” language;
- overly technical logs; and
- cluttered developer controls.

### 11.2 Suggested visual hierarchy

1. Business impact
2. Referral workflow
3. Seven-referral queue
4. Selected-referral details
5. Before-and-after comparison
6. Annual capacity projection
7. Larger automation roadmap

### 11.3 Suggested color semantics

Use an accessible healthcare palette:

- navy or deep blue for primary structure;
- teal for automation and completed work;
- green for ready/confirmed;
- amber for missing or unclear information;
- red for blocked or duplicate risk;
- neutral gray for planned workflow stages; and
- white or light neutral surfaces for readability.

Do not rely on color alone. Include icons and text labels.

### 11.4 Language

Prefer business language:

- “Time returned”
- “Work prepared”
- “Needs attention”
- “Human confirmation required”
- “Possible duplicate blocked”
- “Ready for Monday.com”
- “DRK draft ready”

Avoid internal implementation terms unless inside a technical details drawer:

- JSON
- CLI
- LLM
- API payload
- SHA-256
- circuit breaker
- immutable digest

The concepts can still be represented in executive language:

- “Attachment fingerprint recorded”
- “Source verified”
- “Approved snapshot protected”
- “Duplicate processing prevented”

---

## 12. Suggested dashboard copy

### Primary headline

> From Manual Referral Processing to Exception-Based Review

### Supporting copy

> Seven incoming referrals can be read, organized, checked, and prepared for Monday.com and DRK while WCW employees remain in control of every decision.

### Main action

> Run Referral Automation

### Completion message

> Seven referrals processed. Four are ready for confirmation, two need additional information, and one possible duplicate was safely blocked.

### Value summary

> This demonstration batch returned an estimated 3 hours and 16 minutes of administrative capacity by reducing document reading, duplicate searches, repeated data entry, and manual tracking.

### Duplicate message

> A possible existing patient was found. Creation remains blocked until an employee resolves the match.

### Missing-information message

> The automation found required information that was not clearly documented and prepared the next follow-up action.

### Confirmation message

> Human confirmation recorded. The approved referral is ready for the Monday.com handoff, and the DRK draft is prepared.

### Management message

> The same team can spend less time transcribing information and more time resolving exceptions, coordinating care, and moving referrals forward.

---

## 13. Implementation guidance for the UI-generation agent

Build a polished, responsive, desktop-first single-page demo.

Requirements:

- use static mock data for all seven referrals;
- keep state in the frontend;
- persist demo state only in memory or browser storage;
- include a reset-demo action;
- make all key actions clickable;
- simulate processing with deterministic timers;
- make the “Run Referral Automation” sequence repeatable;
- allow opening and closing referral details without navigation loss;
- support a realistic PDF placeholder or approved local PDF assets;
- ensure status transitions remain consistent;
- prevent simulated Monday creation before confirmation;
- prevent simulated Monday creation for blocked referrals;
- prevent duplicate simulated creation;
- clearly distinguish Monday.com ready/created from DRK draft ready;
- include accessible keyboard interactions;
- include responsive behavior for presentation screens;
- avoid requiring external credentials; and
- avoid production API calls.

The demo should work reliably without internet access after dependencies are installed.

### Recommended deterministic referral outcomes

- Maria Alvarez: ready
- James Carter: ready
- Linda Nguyen: missing insurance
- Robert Williams: probable duplicate
- Evelyn Brooks: unclear phone
- Thomas Reed: ready
- Patricia Johnson: ready

### Recommended default timestamps

Use a single fictional business day and stagger the seven emails between 7:42 AM and 10:18 AM.

### Reset behavior

“Reset Demo” should restore:

- all seven referrals to Received;
- all metrics to the initial state;
- all confirmation states to false;
- all destination records to not created;
- all demo timelines to initial email-received events; and
- the automation run button to enabled.

---

## 14. Acceptance criteria

The generated UI is successful when:

1. A viewer understands the WCW business value within 15 seconds.
2. The dashboard presents one cohesive experience.
3. Seven fictional referral emails and PDFs are visible.
4. The presenter can run a simulated referral-automation batch.
5. The batch visibly processes all seven referrals.
6. Four referrals become ready, two need attention, and one is duplicate-blocked.
7. A complete referral can be opened and reviewed.
8. The seven required fields are clearly displayed.
9. Source evidence can be demonstrated.
10. The referral can be confirmed.
11. Confirmation activates Monday.com and DRK destination previews.
12. Monday.com can be simulated as created exactly once.
13. DRK remains accurately labeled as a prepared draft or assisted-entry step.
14. Missing-information follow-up can be demonstrated.
15. Duplicate protection can be demonstrated.
16. Every referral shows an automation-impact receipt.
17. The dashboard shows the before-and-after workflow.
18. The dashboard shows illustrative time and capacity impact.
19. Invented metrics are clearly labeled as illustrative.
20. Planned workflow automation is distinguishable from currently demonstrable intake capabilities.
21. No real patient information or credentials are required.
22. The entire demo can be reset and presented again.

---

## 15. Final presentation takeaway

The audience should leave with this understanding:

> Today, WCW employees spend significant time opening referral emails, reading PDFs, locating required information, checking completeness, searching for duplicates, entering the same information into multiple systems, and manually tracking follow-up.

> The WCW Referral Automation changes that work. It prepares the information, highlights exceptions, protects against duplicates, creates an accountable confirmation step, and prepares Monday.com and DRK handoffs.

> Employees remain responsible for communication, clinical judgment, scheduling decisions, QA, and approvals—but they no longer need to perform every repetitive administrative step manually.

> The result is capacity returned to the team, reduced operational overload, fewer preventable errors, faster referral preparation, and a foundation for automating the complete referral-to-visit workflow.
