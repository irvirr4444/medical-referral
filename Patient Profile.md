# Patient profile — field inventory and layout plan

This document is the source of truth for **what we already know about one patient** across the seven stages, and **what the Patient tab should show**. It replaces the earlier modal-from-cards draft.

**Access (locked):** own nav tab, search-only entry. Empty until a patient is searched. Clicking a name on a worklist card does **not** open the profile (that still scopes the queue). Profile is **read-only**. Confirm / Edit stay on Intake step 2.

**Job:** 3-second skim of “where is this patient and who owns them,” then optional extracted detail. Not a DRK chart replacement.

**Scope of this inventory:** it is the union of what the **seven stage cards currently show**, plus canonical JSON. It is **not** every column on the live Monday Master Sheet, and **not** the live DRK chart (encounters, billing, communications). Those extras are listed under “Exists in the systems, not on the stage cards.”

---

## Data sources we already have

| Source | Lives in | Role |
|---|---|---|
| Canonical referral JSON | PDF extractor → `CanonicalReferral` | Full extracted packet. Authority for identity, clinical, insurance, source, admission. |
| Outlook / inbox | Canonical `source` + receive-referral snapshot | How the referral arrived. |
| Monday.com Master Sheet | `MondayRecord` + EOD/weekly columns | Ops sheet: identity snapshot, CM, sent-by, provider, scheduling, visit. |
| DRK | `DrkDraftRecord` | Chart write payload (demographics, contact, admission, insurance). Duplicate search result. |
| Assignment | `CaseManagerSuggestion` / `CaseManagerOption` | Owner name, email, routing reason. |
| Provider roster | `ProviderOption` + `SchedulingHandoff` | Selected provider name, NPI, city, phone, email, availability outcome. |
| Notifications | `ReferralSourceNotification`, `CaseManagerNotification` | Ack to source, CM assignment email. |
| Journey | `PatientOpsJourney` | Current stage, per-stage headline, timestamped outcomes. |
| Step status | `PatientStepProgress` | Done / current / waiting / blocked / upcoming per microstep. |

Monday scheduling and visit columns from the written workflow are **not** all on `MondayRecord` yet. They live on EOD and weekly fixtures today. The profile should treat them as one Monday sheet.

---

## Unified patient record (everything displayable)

One patient is the union of the fields below. Later stages overwrite earlier copies of the same fact (Monday provider beats canonical “pending provider”).

### Identity (canonical + Monday)

- Full name (first, middle, last, suffix)
- Date of birth, age, sex/gender
- Phones (number + type; primary is first)
- Email
- Address (line 1, line 2, city, state, postal, country)
- MRN, source patient ID + label, SSN (when extracted)
- Emergency contact (name, relationship, phone)

### Referral packet (canonical)

- Document type, PDF file name, page count, SHA-256
- Outlook message ID, attachment ID, received time, sent-by
- Referring organization (name, contact, phone, fax, email, address)
- Referring provider name, order/referral date
- Home health / hospice org + hospice / palliative flags
- Admission date, facility, place of service, Medicare admission
- Clinical summary, wound order included
- Diagnoses (code, description, added date, primary, status)
- Medications (name, strength, dose form, directions, status, prescribed date, prescriber, days supply, quantity, refills)
- Allergies (NKA flag; name, reaction, treatment, status)
- Clinical notes
- Insurance policies (type, payer, policy #, group #/name, holder, dates, subscriber)
- Requested services (service, frequency, instructions)
- Extraction warnings + field quality (present / missing / unclear / explicitly none)

**Intake gate (7 required):** name, DOB, phone, address, home health/hospice, clinical, insurance.  
**Minimum threshold to proceed:** name, DOB, phone, address.

### People

- Case manager name + email + routing reason (territory)
- Referral partner name + email (contact confirmation)
- Assigned provider: name, NPI, city, phone, email
- Provider availability: requested at, 1-hour deadline, outcome (waiting / confirmed / timeout / placed), resolved at
- Info-box / sent-by

### Monday Master Sheet (ops columns)

Full exported dictionary: [`WCW Master Sheet Reference Guide.md`](WCW%20Master%20Sheet%20Reference%20Guide.md). The frontend `MondayRecord` is a thin demo subset. Profile Monday should follow the **live board**, not the demo type.

**Patient / intake (direct):** name, DOB, phone, address, email, date/time referral received, POS (`SNF` / `ALF` / `HOME` / clinics), **Patient Contacted** (`Yes` / `No` / `LVM` / `VM FULL`), Wx order included, comments, F/up comments.

**Agency / source (direct):** thank-agency contact, agency contact, agency phone, agency email, **territory**, marketer follow-up. Relations: referring agency, current HH/hospice. Mirrors from those boards: agency type, marketer, comm pref, city/zip/state/fax (agency, not patient).

**Handoff / assignment (direct):** case manager, sent to CM, time sent to CM, sent by, **sent to Nexus**, time sent to Nexus, intake group copy, stage (unreliable as lifecycle — almost always `In intake`).

**Provider / scheduling (direct):** referral sent to provider, appointment date, scheduled status (`Scheduled` / `Not Scheduled`), scheduling complete, provider change, due date. Relation: Provider → mirrors provider name + email.

**Visit / hold / discharge (direct):** **Visit Status** (this is the real lifecycle column: Seen, Scheduled, Hospitalized, On Holds List, Deceased, Immediate DC, Pending - No Provider, …), QA hold reason, DC reason, discharge reason dropdown, LEAD FOLLOWUP, ACT Ready.

**Out of profile skim (CRM / derived):** Kathy Email, time since entry, current-stage start date, legal request, sales rep, outsource boards, subitems, Visit Status TEST.

**Demo-only extras (not live Monday columns):** hours since provider selected, 48h scheduling label, consecutive not-seen count, CM follow-up/escalation taken.

Visit Status and discharge dropdowns are truncated in the export (`+10 more`, `+7 more`). The written flow still asks for a **Patient Status variables list**. We do not have the complete choice set.

### DRK

- Chart match result (none / candidate needing DOB confirm / blocked)
- Draft: first/last, DOB, gender, address, country, primary phone, email
- Admission date, place of service, facility, home health
- Referral source, referral date, referring provider, clinical
- Primary payer, insurance type, policy number
- Ready-for-fill, blockers, warnings
- Assigned provider + NPI once written

### Workflow position (computed from journey + steps)

- Current stage + current step
- Step status (done / current / waiting / blocked / upcoming)
- Headline (“Awaiting approval · agency missing”)
- Next expected step
- Active blocker (missing fields, duplicate, partner not contacted, no provider, unscheduled, 3× not seen)
- Person responsible for the next action

---

## Inventory by stage and step

What each step **produces** for that patient. The profile does not copy every step card; it **merges** these into the record above.

### 1. Referral intake

| Step | System | Patient facts produced |
|---|---|---|
| **Receive referral in inbox** | Outlook | Inbox, sender, received time, message ID, PDF file name, attachment ID |
| **Extract and verify** | Canonical extractor | Full canonical JSON. Gate: 7 required + 4-field threshold. Completeness `n/7`. Missing / unclear labels. Identity line (name · DOB · phone). Confirm/Edit happens **here only**. |
| **Check Monday** | Monday reader | Query identity (name · DOB). Candidate count. Duplicate vs clear. Search skipped if identity incomplete. |
| **Check DRK** | DRK reader | Query identity. Candidate count. Exact match vs needs-DOB-confirm. Partial implementation. |
| **Referral partner contacted** | Intake team | Partner name, partner email, contacted-back yes/no. Intake cannot complete until confirmed. |

### 2. Assignment

| Step | System | Patient facts produced |
|---|---|---|
| **Assign Case Manager** | Assignment rules | Suggested CM name + email. Routing reason (service area). Complete → CM, incomplete → marketer. Territory conflict is not auto-assigned. |
| **Notify Case Manager** | WCW approval | Confirmed owner. Notification: subject, message, and the seven required fields copied into the CM email. |

### 3. Handoff

| Step | System | Patient facts produced |
|---|---|---|
| **Notify referral source** | Outlook | Ack To (source email), CC (CM). Body names patient, source, assigned CM. PDF attached to CM. |
| **Create Monday.com Record** | Monday | Master Sheet item: seven required + CM + sent-by + referral status. Item ID. |
| **Create DRK Chart** | DRK | Chart draft / write. Blockers if identity or facility unresolved. Planned. |

### 4. Provider selection

| Step | System | Patient facts produced |
|---|---|---|
| **Select Provider** | Roster + CM | Patient location (city/state/ZIP). Shortlist. Selected provider (name, NPI, city, phone, email) or coverage gap → Nicole → discharge. |
| **Confirm Provider Availability** | CM / provider | Requested at, 1-hour deadline, outcome: confirmed / timeout / CM placement. |
| **Update Monday.com and DRK** | Monday + DRK | Provider name + NPI written to both. Referral status → Provider confirmed. Must match before scheduling. |

### 5. Scheduling

| Step | System | Patient facts produced |
|---|---|---|
| **Send Referral to Provider** | Secure send + Monday | Packet (identity + PDF) delivered to confirmed provider. Monday “Referral sent to provider”. Route: provider_confirmed vs manual_placement. |
| **Schedule Patient** | CM / routing | Appointment date (and time when we have it). Target 24–48h from availability. |

### 6. End-of-day check

| Step | System | Patient facts produced |
|---|---|---|
| **Check Scheduling Status** | Monday | Scheduled status, appointment date, scheduled complete. Derived 48h label. Parties: patient, provider, CM. Hours since provider selected. |
| **Follow Up with Case Manager** | Teams | Follow-up sent yes/no. Message to assigned CM. Required before escalation when blank/conflicting. |
| **Escalate Unresolved Cases** | Email + spreadsheet | Escalated to Nicole/management yes/no. Patient appears once on the list. |

### 7. Weekly visit cycle

| Step | System | Patient facts produced |
|---|---|---|
| **Seen patients** | Monday / DRK / Teams | Visit outcome Seen or Not Seen. Last visit. Consecutive not-seen. Reschedule, or discharge-review queue at 3 misses. |
| **Healed patients** | QA / Monday | Visit status Healed. QA discharge path opened. Human DC required. |
| **Expired patients** | CM / Monday | Visit status Expired. Removed from schedule pending DC approval. Closure action taken yes/no. |
| **On hold patients** | Holds list / Monday | Hold reason (hospital / vacation / other). Moved to holds. Weekly monitoring paused until return. |

---

## One-page layout

Everything lives on **one Patient tab**. No inner tabs. No stage left rail (that still means steps). Search is the only entry.

Nav: `Overview · Patient · 1. Referral intake · … · 7. Weekly visit cycle`. Patient is not numbered.

### Empty

Search field. Copy: “Search a patient to open their profile.” No cards, no JSON, no last-viewed list in v1.

### Found — first screen (always visible)

Sticky identity header, then two compact blocks. This is the 3-second skim.

**Now (header)**

| Slot | Source |
|---|---|
| Name, DOB, phone, city | Canonical (confirmed extract) else Monday |
| Current stage · step · status | Journey + step progress |
| Next action + owner | Derived from current step |
| Blocker | First of: missing gate fields, partner not contacted, duplicate, no provider / discharged, unscheduled >48h, 3× not seen, DRK blocked |

**People (three cells)**

| Cell | Source |
|---|---|
| Case manager name · email · territory | Assignment |
| Provider name · city · NPI, or “Not selected” | Provider selection / Monday mirror |
| Referral source + partner contacted + sent by | Canonical source + contact step + Monday sent-by |

**Monday ops (one row)**

Referral sent · Appointment · Scheduled · Scheduled complete · Visit Status · Patient contacted · POS.

Blank (`—`) until that stage has written the column. Later-stage patients fill the same slots; we do not add new header widgets.

### Same page, collapsed

Three disclosures. Closed by default except Extracted when intake is the current stage (optional).

1. **Extracted details** — read-only `ArtifactSections` from Intake Confirm: 7 required, then demographics through warnings, plus PDF. No Edit.
2. **Records** — full Monday item (sent-to-CM, Nexus, due date, QA hold, DC reason, comments, territory), DRK draft, duplicate results, Outlook metadata, PDF.
3. **Timeline** — `PatientOpsJourney` events: when + summary.

### What stays off this page

Buttons (Confirm, assign, schedule, EOD, weekly). Raw JSON. Live DRK chart. CRM mirrors (Kathy Email, sales, Visit Status TEST). Opening from a worklist name click.

### How it is built

`patientProfile(patientId)` merges: confirmed canonical + overlay edits, Monday/EOD/weekly columns, CM, provider, availability, DRK draft, journey.

Wire: add `patient` to `WORKFLOW_MODAL_TABS` (not a `FlowOpsPageId`). `App.tsx` renders `PatientProfilePage` instead of `StageOperationsPage`. Search writes `opsProfilePatient` (separate from worklist `opsScopedPatient`). Clearing search returns the empty tab.

Demo v1 can keep EOD/weekly fields on those fixtures; the profile reads them as Monday columns. Do not invent appointment time, RingRx, or a full Visit Status enum until those lists exist.

---

## Do not put on the profile

- Confirm / Edit / assignment / provider / EOD / weekly **buttons** (stay on the step)
- Raw canonical JSON
- Extraction model names, SHA-256, message IDs in the skim (keep under Records)
- Full medication/allergy lists in the skim (they belong under Extracted details)
- Opening from a worklist name click
- Live DRK chart dump (encounters, billing, communications, scans) — link out, do not copy

---

## Exists in the systems, not on the stage cards

These are real patient facts. The first inventory missed them because the worklist UI does not render them.

**Live Monday (reader + write config), not in `MondayRecord`:**

- Email, referral-received datetime, place of service
- Agency contact / phone / email
- Stage, sent-to-CM, time-sent-to-CM
- Due date
- QA hold reason, discharge reason, comments
- Company and current-HH board relations
- Monday item id, board group

**DRK create payload (`DrkCreatePayloadDraft`), not in the frontend DRK card:**

- Preferred language
- Secondary address, contact fax, secondary phone
- Emergency contact as structured name + address + guardian flag
- Admission: territory query, provider query, palliative, hospice, Medicare
- Referral: referring facility (separate from provider)
- Insurance: copay, deductible, percent coverage, verified-with, termination date

**Live DRK chart (read patient), out of profile scope:**

- EMR patient id, patient status display name
- Communications, encounters, billing, custom scans, eligibility pipeline
- Progress notes (monitoring also has `progress_note_status`)

**Workflow flags stored in demo session, not a “field” but they change Now:**

- Intake verified / field edits
- Partner contacted confirmed
- Assignment confirmed
- Provider confirmed vs territory **discharged**
- Availability outcome (waiting / confirmed / timeout / placed)
- Scheduling handoff route (provider confirmed vs manual placement)
- EOD follow-up / escalation taken
- Weekly reschedule / holds action / DC review sent

**Asked for in the written flow, still not fully in our schemas:**

- Complete Visit Status / Patient Status choice list (export truncates; POS already has SNF/ALF/HOME)
- RingRx
- Routing-software appointment *time* (Monday has appointment *date* only)
- Canonical has no structured referral-source-type enum; Monday POS is the closest

---

## Certainty

| Layer | Sure? | Why |
|---|---|---|
| Canonical JSON | Yes | Closed Pydantic schema. Every field is listed. |
| Demo stage cards | Yes | Walked all 7 stages and the feed components. |
| Monday Master Sheet columns | Yes for the **exported dictionary** in `WCW Master Sheet Reference Guide.md`. No for **every live choice value** (Visit Status `+10 more`) and no for item updates, files, or subitem bodies. |
| DRK create draft | Yes | Closed schema. |
| Live DRK chart | No | Open EMR: communications, encounters, billing, notes. Out of profile scope. |
| RingRx / routing / Patient Status list | No | Still “to be provided” in the written flow. |

Do not treat this inventory as “every column WCW will ever add.” Treat it as: canonical (complete) + Monday export (complete as of that snapshot) + DRK write draft (complete) + stage-card ops flags (complete).

---

## Gaps to close when we build the aggregator

These facts exist in the workflow but are **split across fixtures**. The Patient tab needs one lookup, e.g. `patientProfile(patientId)`:

1. Canonical from intake demo / overlay edits (confirmed extract).
2. Monday record + provider overlay.
3. DRK draft + provider overlay.
4. Assignment suggestion / confirmed CM.
5. Provider selection + availability + scheduling handoff.
6. EOD scheduling columns (appointment, scheduled status, complete, hours, follow-up, escalation).
7. Weekly visit columns (outcome, last visit, consecutive misses, hold, DC).
8. Journey: current stage/step, headline, next action, timeline.

Until (6) and (7) are copied onto the Monday record type, the profile should **read EOD + weekly fixtures** as if they were Master Sheet columns.

For v1 skim, prefer **live Monday aliases** (received, sent-to-CM, due date, QA hold, discharge reason) over inventing new labels. Do not pull the live DRK chart into the profile.

---

## Privacy

Display what coordinators already see on stage cards. Do not put SSN, SHA-256, or message IDs in the skim. PHI stays in the app; do not put it in URLs.
