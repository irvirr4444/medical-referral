# Build: WCW Referral Automation — Demo Dashboard

You are building a single-page, desktop-first, clickable demo dashboard for the leadership of **West Coast Wound (WCW)**, a wound-care referral organization. This is a frontend demonstration, not a production system. Static/simulated data only — no live integrations, no auth, no backend beyond a minimal local server if the framework needs one.

**The story the UI must tell:** WCW employees move from manually processing every detail of a referral to reviewing exceptions, making decisions, and confirming prepared actions. Not "we built scripts" — "the team gets its time back."

Read this whole spec before writing code. Where it gives you copy, use it close to verbatim because it reflects the approved demonstration framing. Where it leaves room (layout, motion, exact styling), make deliberate design choices — don't default to generic dashboard templates.

---

## 1. Design direction

Design this the way a studio would for a healthcare-operations client who has explicitly rejected anything that feels like a generic SaaS admin template or an "AI demo." The tone is: **credible, calm, operational, executive-ready.** Not playful, not futuristic, not covered in gradients.

**Avoid the default AI-generated looks:** no cream-background+terracotta-accent combo, no near-black+neon-accent combo, no dense broadsheet hairline-grid look used as the *entire* system. Pick something specific to this subject instead.

### Palette (name these as tokens, derive everything from them)
- **Deep navy** — primary structure, header, text (e.g. `#12233F`)
- **Teal** — automation / active work / links (e.g. `#0E7C86`)
- **Green** — ready / confirmed (e.g. `#1F8A5C`)
- **Amber** — missing or unclear info, needs attention (e.g. `#B7791F`)
- **Red/clay** — blocked / duplicate risk (e.g. `#B3423A`) — used sparingly, never decoratively
- **Neutral gray** — planned/conceptual workflow stages, disabled states
- **Off-white / paper** surface — not stark white, not cream (e.g. `#F6F7F5`)

Never rely on color alone for status — pair every status color with an icon and a text label (accessibility requirement).

### Typography
Pick a confident, slightly clinical **display sans** for headlines and big numbers (something with real character but not trendy-startup — think medical-instrument precision, not consumer-app friendliness), a highly legible **body sans** for everything else, and a **monospace or utility face reserved for the audit/timeline drawer only** (timestamps, IDs) so it visually signals "this is a log," not the whole UI.

### Layout concept — the signature element
Make the **workflow spine** the persistent, literal backbone of the page: a horizontal pipeline bar —
`Received → Extracted → Reviewed → Confirmed → Monday.com Ready + DRK Draft Ready`
— stays visible (sticky or anchored near the top) throughout the whole session, with a live count badge per stage. When "Run Referral Automation" executes, the seven referral tokens visibly travel along this spine in staged steps rather than a spinner popping up elsewhere. Opening a referral, confirming it, sending it to Monday.com — all of it visibly moves that referral's token along the same spine. This is the one big idea to spend your design boldness on; keep everything else (cards, drawers, tables) quiet and disciplined around it.

### Motion
Orchestrated, not scattered. The automation run (~8–12s) is the one big choreographed sequence — 12 staged steps (listed below) with visible progress, not a generic spinner. Elsewhere, keep motion minimal: subtle state transitions, no idle/ambient animation, respect `prefers-reduced-motion`.

Before building, sanity-check your plan against this section: if any part of it is what you'd produce for any generic ops dashboard, revise it.

---

## 2. Non-negotiable framing rules

- **Demo Mode badge** visible in the header at all times: *"Demo Mode · Illustrative workflow and impact data."*
- Any financial/time/staffing figure gets a small caption: *"Illustrative estimate based on configurable workflow assumptions. Replace with measured WCW operational data."*
- **Never** say "employees eliminated," "headcount reduced," or similar. **Always** frame as capacity returned — see approved phrases in §8.
- All seven patients, senders, and clinical details are fictional (data provided below). Never introduce real PHI.
- The demo may use approved local referral PDF assets when they are explicitly provided and every attendee is authorized to view them. Otherwise use deidentified or synthetic PDF replicas. Never pair a fictional patient identity with a visible real-patient PDF; the source document and displayed identity must remain internally consistent.
- No `.env`, credentials, API keys, or tokens ever appear in the UI, even as placeholders.
- Distinguish **currently demonstrable** intake/handoff features from **planned/conceptual** later-pipeline features (scheduling, weekly monitoring, discharge, QA) — the latter are visually muted/grayed and explicitly labeled "Planned workflow automation."
- Monday.com may be simulated as created. **DRK is always a prepared draft / assisted-entry step — never shown as a completed production patient creation.**

---

## 3. Page structure (single page, one cohesive dashboard — no separate exec/operator apps)

Use drawers, modals, tabs, and expandable panels for depth; the user never leaves the one dashboard.

1. **Header** — WCW Referral Automation title, Demo Mode badge, demo date, inbox status ("7 new referrals"), primary **Run Referral Automation** button.
2. **Business-impact strip** (first major content block, most prominent section) — 6 primary impact cards + secondary metrics + "How calculated" drawer.
3. **Workflow spine** (the signature element, described above) with per-stage counts; clicking a stage filters the queue below.
4. **Before/after summary** — concise intake comparison, headline: *"From approximately 36 minutes of manual processing to approximately 8 minutes of focused review"* (labeled illustrative), plus an expandable complete-workflow comparison covering intake, handoff, scheduling, end-of-day monitoring, and the weekly visit cycle (§9).
5. **Seven-referral queue** — email-style cards/rows with filters (All / Ready / Needs information / Possible duplicate / Confirmed). Every row shows fictional patient name, sender, subject, received time, PDF filename, page count, completeness score, duplicate status, workflow state, estimated minutes returned, and a Review Referral action.
6. **Selected-referral workspace** — wide drawer/modal opened from the queue (see §5).
7. **Annual capacity projection** + interactive impact calculator (§7).
8. **"What comes next" / Full WCW workflow** — compact, visually muted roadmap of planned stages.

---

## 4. The automation run sequence

On clicking **Run Referral Automation**, animate through these 12 stages against the workflow spine (~8–12s total, deterministic, repeatable):

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

End state: 4 ready for confirmation, 2 need information, 1 blocked as probable duplicate. Metrics populate live during/after the run. Completion message: *"Seven referrals processed. Four are ready for confirmation, two need additional information, and one possible duplicate was safely blocked."*

---

## 5. Selected-referral workspace (drawer/modal)

- **Source document**: approved local PDF asset when explicitly supplied, otherwise a realistic deidentified/synthetic placeholder; include page nav, page count, zoom, filename, and source-email summary. Never expose unauthorized PHI.
- **Extracted information**: name, DOB, phone, address, home-health/hospice agency, wound/clinical info, insurance, referral source, referring provider, diagnoses, medications, allergies, requested services, clinical summary.
- **Seven-field readiness** (always visible, always these 7 in this order): Patient name · Date of birth · Contact number · Patient address · Home-health/hospice agency · Wound/clinical information · Insurance information. Each field status: **Complete / Explicitly none / Missing / Unclear** — icon + label, not color alone. Explicit "no insurance" / "no agency" counts as **Complete**.
- **Evidence panel**: "View source" shows source page, short evidence quote, confidence indicator, verification status.
- **Needs-attention panel**: pinned near top — missing fields, unclear values, possible duplicates, unmatched agency, recommended next action.
- **Duplicate comparison** (Robert Williams only): side-by-side incoming vs. existing invented Monday.com record (name, DOB, phone, address, identifiers). Banner: *"Creation blocked — human resolution required."* Actions: Mark as different patient / Keep blocked / Open existing record.
- **Monday.com preview**: item name, board, group, column values, update/comment content, referring-agency relation, blockers, approval status, write status. Actions: Preview Record → Confirm Referral → Send to Monday.com → Open Record.
- **DRK draft preview**: demographics, contact, address, emergency contact, admission info, referring source, insurance, diagnoses, requested service, unresolved lookups, duplicate-check status. Actions: Preview DRK Draft / Open DRK Assisted Entry / Mark Ready for Face-Sheet Team. Always show: *"Draft prepared — final DRK patient creation remains human-controlled."*
- **Confirmation block**: Outlook-style preview, reply box, Confirm / Request correction actions, sender/thread validation. On confirm, show the exact checklist:
  ```
  Confirmation recorded
  ✓ Authorized sender matched
  ✓ Original email thread matched
  ✓ Review snapshot validated
  ✓ Seven required fields complete
  ✓ No blocking duplicate detected
  ✓ Monday.com handoff ready
  ✓ DRK draft ready
  ```
- **Automation-impact receipt** (per referral), business language only — e.g.:
  ```
  18 pages analyzed
  27 patient and clinical values extracted
  7 required fields verified
  1 duplicate search completed
  2 destination records prepared
  12 repetitive manual actions avoided
  29 estimated minutes returned to staff
  ```
- **Activity/audit timeline**: received → PDF validated → attachment fingerprint recorded → extraction completed → source verification completed → fields evaluated → duplicate search completed → review prepared → confirmation received → Monday preview validated → Monday record created/ready → DRK draft prepared. Timestamp + result + responsible system/role + human-required flag per event. This is the one place where a monospace utility face and denser layout is appropriate.

---

## 6. Interaction rules (state machine constraints)

- Send-to-Monday.com is only enabled after confirmation, with no active blockers, and can only fire **once** per referral (prevent double-creation).
- Confirmation rejects blocked (duplicate) referrals.
- "Prepare follow-up" (Linda Nguyen / Evelyn Brooks) generates a fictional follow-up message, assigns to intake/marketer, sets status "Follow-up prepared."
- "Resolve duplicate" (Robert Williams) keeps destination actions disabled until a choice is made; "Different patient" unblocks for demo purposes; logs a human-resolution audit event.
- **Reset Demo** restores: all 7 referrals to Received, all metrics to zero, all confirmations to false, all destination records to not-created, timelines to just the email-received event, run button enabled.
- Keyboard-accessible throughout; visible focus states; responsive down to presentation/projector widths.

---

## 7. Impact numbers (use exactly)

**Batch metrics:** 7 emails received · 7 PDFs processed · 132 pages analyzed · 189 values extracted · 49 required fields evaluated · 7 duplicate searches · 7 Monday.com previews generated · 7 DRK drafts generated · 4 destination-ready · 2 incomplete/unclear · 1 probable duplicate blocked from submission · 63 manual actions avoided.

**Time model:** manual ≈36 min/referral → assisted ≈8 min/referral → ≈28 min returned/referral (≈78% reduction). Batch: manual ≈4h12m → assisted ≈56m → **≈3h16m returned**.

**Annual projection (defaults for the impact calculator):** 7 referrals/day × 250 working days = 1,750/yr → ≈817 admin hours returned/yr → ≈0.39 FTE-equivalent capacity. Caption: *"Capacity returned to WCW employees — not a guaranteed payroll reduction."*

**6 primary impact cards:** 3h 16m time returned today · 63 manual actions avoided · 132 PDF pages analyzed · 14 destination previews/drafts generated · 2 incomplete referrals found early · 1 possible duplicate blocked.
**Secondary:** 78% less admin touch time · 4 ready for confirmation · 817 projected annual hours · 0.39 FTE-equivalent.

**Impact calculator** (presenter-adjustable, these 7-referral values as defaults): referrals/day, manual min/referral, assisted min/referral, working days/yr, annual productive hours/employee → recompute minutes/referral, hours/day, hours/week, hours/year, added referral capacity, FTE-equivalent.

---

## 8. Approved language

Use: "Equivalent staff capacity returned" · "More referrals handled by the existing team" · "Less repetitive administrative work" · "Reduced administrative overload" · "Growth without proportional administrative hiring" · "Employees can focus on calls, exceptions, scheduling, and patient coordination" · "Time returned" · "Work prepared" · "Needs attention" · "Human confirmation required" · "Possible duplicate blocked" · "Ready for Monday.com" · "DRK draft ready."

Never: "employees eliminated," "headcount reduced," "replaces the intake team," "no longer needs case managers."

Keep implementation jargon (JSON, API, LLM, SHA-256, circuit breaker) out of the main UI; if you need a technical-details drawer, translate to: "Attachment fingerprint recorded," "Source verified," "Approved snapshot protected," "Duplicate processing prevented."

**Key copy to reuse:**
- Headline: *"From Manual Referral Processing to Exception-Based Review"*
- Subhead: *"WCW Referral Automation reads incoming referrals, organizes the required patient information, identifies missing details and possible duplicates, prepares Monday.com and DRK handoffs, and keeps employees in control of every important decision."*
- Closing: *"The automation does not replace WCW's clinical or operational judgment. It removes repetitive intake work, returns capacity to employees, reduces avoidable rework, and allows the existing team to safely handle greater referral volume."*

---

## 9. Complete WCW workflow value story

The intake comparison is the opening proof point, but the dashboard must also explain how the same automation model reduces work across the complete documented WCW workflow. Present these as expandable before/after sections or a compact comparison journey. Intake and handoff are currently demonstrable; later stages are visually muted and labeled **Planned workflow automation**.

### 9.1 Referral intake

**Before**

1. Open the referral email.
2. Download and validate the PDF.
3. Read every page.
4. Locate the patient name, DOB, phone, and address.
5. Locate home-health/hospice, wound, clinical, and insurance information.
6. Determine which required information is missing or unclear.
7. Search Monday.com for an existing patient.
8. Search DRK for an existing patient.
9. Contact the referral partner.
10. Re-enter information into Monday.com.
11. Re-enter information into DRK.
12. Track whether intake was completed and follow up again when needed.

**With WCW automation**

1. Review extracted information.
2. Review highlighted missing or uncertain fields.
3. Resolve possible duplicate warnings.
4. Confirm the referral.
5. Monday.com and DRK records are prepared.

**Value statement**

> Employees stop searching every document for routine information. Their attention is directed to referrals and fields that require judgment.

### 9.2 Handoff and case-manager assignment

**Before**

1. Determine the patient's geographic area.
2. Determine the correct case manager.
3. Prepare an acknowledgement email.
4. Attach and forward the PDF.
5. Send the referral to the case manager.
6. Forward the referral to the face-sheet team.
7. Enter information into the Monday.com Master Sheet.
8. Fill the Sent By field.
9. Track whether each handoff occurred.

**With proposed automation**

1. Patient location is read from the referral.
2. The appropriate case manager is suggested from approved territory rules.
3. An acknowledgement is prepared automatically.
4. The Monday.com handoff is prepared.
5. The DRK draft is prepared.
6. Handoff events are recorded.
7. Employees review exceptions and confirm.

**Value statement**

> One confirmed referral can create a coordinated handoff instead of several disconnected manual tasks.

### 9.3 Provider selection and scheduling

**Before**

1. Review the patient's location.
2. Search the case manager's provider list.
3. Determine which provider covers the territory.
4. Open routing software.
5. Inspect the provider's schedule.
6. Contact the provider.
7. Wait for a response.
8. Track the one-hour response window.
9. Decide where the patient fits if the provider does not respond.
10. Update Monday.com and DRK.
11. Continue checking until scheduling is complete.

**With proposed automation**

1. Matching providers are suggested from territory rules.
2. Relevant routing windows are displayed.
3. Provider-response deadlines are monitored.
4. Unanswered referrals are highlighted.
5. Confirmed scheduling information is prepared for Monday.com and DRK.
6. Human staff select and confirm the final appointment.

**Value statement**

> Automation performs searching, monitoring, and preparation. The case manager retains control of provider and scheduling decisions.

### 9.4 End-of-day scheduling check

**Before**

1. Open Monday.com and review every active referral.
2. Check scheduled status, appointment date, and scheduling-complete status.
3. Identify blank or overdue referrals.
4. Contact case managers through Teams.
5. Ask why each patient is not scheduled.
6. Determine whether the issue is resolvable.
7. Prepare management escalation emails.
8. Maintain a separate tracking spreadsheet.
9. Continue following up.

**With proposed automation**

1. Active referrals are checked automatically.
2. Unscheduled referrals are identified.
3. The responsible case manager and known blocker are displayed.
4. Existing Monday.com notifications are verified.
5. Uncovered exceptions are prepared for escalation.
6. Management reviews one organized exception list.

**Value statement**

> Management reviews exceptions instead of manually auditing every referral.

### 9.5 Weekly visit cycle

**Before**

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

**With proposed automation**

1. Recorded visit statuses are monitored.
2. Seen and not-seen outcomes are organized.
3. Consecutive missed visits are counted.
4. Three-week noncompliance creates a discharge-review request.
5. Healed or expired statuses initiate the appropriate human review.
6. Hold patients are removed from active scheduling.
7. Return-ready patients re-enter the weekly cycle.
8. Human staff retain all clinical and discharge decisions.

**Value statement**

> The automation remembers deadlines, counts repeated events, and prepares follow-up work so employees do not have to maintain parallel tracking systems.

### 9.6 Planned-workflow management preview

Include one compact, muted management-exception preview to make the future value tangible without pretending it is already live. Use invented counts such as:

- 3 patients awaiting provider confirmation;
- 2 referrals unscheduled at the end-of-day checkpoint;
- 1 patient approaching three consecutive not-seen visits;
- 4 patients currently on hold;
- 1 QA/discharge review awaiting approval.

Every item in this preview must carry the label:

> Planned workflow automation · Illustrative data

---

## 10. The seven fictional referrals (use exactly)

All names, organizations, email addresses, identifiers, diagnoses, and clinical details below are fictional. All sender domains use `.example`. Stagger received timestamps between 7:42 AM and 10:18 AM on one fictional business day.

### 10.1 Maria Alvarez

- Received: 7:42 AM
- Email sender: `referrals@sunrise-homehealth.example`
- Email subject: `New Wound Care Referral — Maria Alvarez`
- Referral source: Sunrise Home Health
- PDF filename: `Alvarez_Maria_Referral_08062026.pdf`
- PDF pages: 18
- DOB: February 14, 1958
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

### 10.2 James Carter

- Received: 8:09 AM
- Email sender: `discharge@oakvalley-hospital.example`
- Email subject: `Hospital Discharge Referral — James Carter`
- Referral source: Oak Valley Hospital
- PDF filename: `Carter_James_Discharge_Packet.pdf`
- PDF pages: 24
- DOB: September 3, 1946
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

### 10.3 Linda Nguyen

- Received: 8:37 AM
- Email sender: `intake@harborview-alf.example`
- Email subject: `Resident Wound Referral — Linda Nguyen`
- Referral source: Harborview Assisted Living
- PDF filename: `Nguyen_Linda_Wound_Referral.pdf`
- PDF pages: 13
- DOB: June 22, 1951
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

### 10.4 Robert Williams

- Received: 9:03 AM
- Email sender: `referrals@carebridge-hh.example`
- Email subject: `Urgent Referral — Robert Williams`
- Referral source: CareBridge Home Health
- PDF filename: `Williams_Robert_Referral.pdf`
- PDF pages: 21
- DOB: November 18, 1962
- Phone: `(555) 013-4472`
- Address: `605 Cypress Street, Anaheim, CA 92805`
- Home health/hospice: CareBridge Home Health
- Diagnosis: Diabetic foot ulcer of right midfoot
- Insurance: Medicare Advantage
- Requested service: Urgent wound assessment
- Required fields: 7/7 complete
- Duplicate status: Probable duplicate
- Existing candidate: Same normalized patient name and DOB
- Outcome: Creation blocked for human review
- Estimated duplicate-related rework prevented: 45 minutes
- Demo purpose: Duplicate protection and fail-safe behavior

### 10.5 Evelyn Brooks

- Received: 9:26 AM
- Email sender: `woundreferrals@northstar-snf.example`
- Email subject: `Wound Care Consult — Evelyn Brooks`
- Referral source: Northstar Skilled Nursing
- PDF filename: `Brooks_Evelyn_Consult.pdf`
- PDF pages: 16
- DOB: January 7, 1943
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

### 10.6 Thomas Reed

- Received: 9:51 AM
- Email sender: `office@lakeside-vascular.example`
- Email subject: `Physician Referral — Thomas Reed`
- Referral source: Lakeside Vascular Clinic
- PDF filename: `Reed_Thomas_Vascular_Referral.pdf`
- PDF pages: 19
- DOB: April 29, 1955
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

### 10.7 Patricia Johnson

- Received: 10:18 AM
- Email sender: `casework@community-care.example`
- Email subject: `New Patient Referral — Patricia Johnson`
- Referral source: Community Care Services
- PDF filename: `Johnson_Patricia_Referral.pdf`
- PDF pages: 21
- DOB: August 11, 1948
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
- Demo purpose: Explicit negative value correctly treated as complete

---

## 11. Human-controlled actions (must read as employee-in-control, not automation-in-control)

Calling the referral partner · confirming missing information · marketer follow-up · reviewing unclear extraction · resolving duplicates · confirming case-manager assignment · confirming provider selection/availability · choosing final schedule · resolving scheduling exceptions · clinical decisions · healed/expired status · hold placement/removal · QA review · discharge approval · management escalation decisions.

Supporting line: *"Automation prepares information, monitors workflow conditions, records outcomes, and executes approved system actions. WCW employees retain control of patient, clinical, scheduling, and management decisions."*

---

## 12. Demo implementation and reliability

- Initial state: all seven referrals are at **Received**, processed metrics are zero, confirmation flags are false, and destination records are not created.
- All interactions use deterministic local mock state; no production API is required.
- The primary demonstration must work without internet access after project dependencies are installed.
- Use approved local PDF assets only when explicitly supplied; otherwise render synthetic/deidentified PDF replicas containing the fictional data in §10.
- Never render a fictional identity over a real patient's visible document.
- Keep the dashboard desktop-first and reliable at common laptop and projector widths.
- Respect `prefers-reduced-motion`; provide the same state changes without token-travel animation when motion is reduced.
- Include a visible but secondary **Reset Demo** action.
- A failed or interrupted animation must not leave impossible workflow states.
- “Send to Monday.com” produces a fictional item ID/demo URL unless a safe demo-board configuration is deliberately added later.
- DRK always ends at **Draft Ready**, **Assisted Entry**, or **Ready for Face-Sheet Team**—never production patient created.

---

## 13. Acceptance checklist

- [ ] Business value is legible within 15 seconds of landing
- [ ] One cohesive dashboard — no separate apps/pages
- [ ] Initial state shows 7 Received, zero processed metrics, no confirmations, and no created destination records
- [ ] All 7 fictional email cards show sender, subject, time, PDF filename, page count, readiness, duplicate state, workflow state, and estimated time returned
- [ ] Approved local PDF assets can be used safely; otherwise fictional/deidentified replicas are shown
- [ ] Run Referral Automation plays the full 12-stage staged sequence against the workflow spine
- [ ] End state: 4 ready / 2 needs-attention / 1 duplicate-blocked
- [ ] Batch wording distinguishes 7 previews/drafts generated from only 4 destination-ready referrals
- [ ] A ready referral can be opened, reviewed, and confirmed end to end
- [ ] Seven-field readiness always appears in the fixed order, with 4-state status (Complete/Explicitly none/Missing/Unclear)
- [ ] Duplicate comparison works for Robert Williams; destination actions stay disabled until resolved
- [ ] Follow-up flow works for Linda Nguyen / Evelyn Brooks
- [ ] Monday.com “creation” happens once per referral, only after confirmation, never for blocked referrals
- [ ] DRK is never shown as completed — always draft / assisted entry / face-sheet-team ready
- [ ] Every processed referral shows an impact receipt
- [ ] Impact calculator recomputes live from presenter inputs
- [ ] Full before/after value story covers intake, handoff, provider scheduling, end-of-day monitoring, and weekly visits
- [ ] Planned management-exception preview is visibly muted and labeled illustrative/planned
- [ ] Planned workflow automation is visually distinct from demonstrable features
- [ ] Demo Mode badge and illustrative-data captions appear wherever invented numbers are used
- [ ] Reset Demo fully restores initial state
- [ ] Primary demo works without internet after dependencies are installed
- [ ] No credentials or secrets ever appear; no real PHI appears unless explicitly approved and every attendee is authorized
- [ ] Keyboard accessible, responsive, and status is never conveyed by color alone