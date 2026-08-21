# Confirmation actions by stage

Human confirmation / confirm-class CTAs wired in the stage feed (`StageFeedMessage` via `StagePatientSteps`).

**Count:** 17 primary confirm / action CTAs across 6 stages (Intake, Assignment, Provider, Scheduling, End-of-day, Weekly). Handoff has none.

Each **primary** CTA gets one in-app SLA timer (`actionTimers` in demo state). Companion controls (Edit / Save / Add or edit) and Discharge on provider-select are not timed. Timers are demo-only: they reset with Reset day / refresh, and they never send email or Teams.

**Demo clock:** canonical SLAs are divided by `DEMO_TIMER_SCALE` (60), so 15 real minutes is about 15 seconds in the demo. Status moves pending → warning at 75% of the SLA, then overdue at the deadline.

**Alert surfaces:** countdown (then an overdue banner) on the feed card; clay/red treatment on the card; red dots on the stage rail and FlowNav; a header bar `{n} overdue confirmations` that jumps to the first overdue stage. Unread stays a separate blue “new update” signal. Patient profile is read-only: it can show the countdown/overdue state, but it does not add confirm buttons.

---

## 1. Referral intake

| Step | Button label | What it confirms | SLA |
| --- | --- | --- | --- |
| **Extract and verify referral details** | Confirm all information is correct | Intake review / extracted fields are good | 15m |
| | Edit / Save changes | Not a confirmation — edit companion | — |
| | Add or edit patient information | Reopen after confirm | — |
| **Referral partner contacted** | Confirm partner is contacted | Partner outreach done → hands off to Assignment | 1h |

No confirm CTAs on: Receive referral in inbox, Check Monday for existing patient, Check DRK for existing chart.

---

## 2. Assignment

| Step | Button label | What it confirms | SLA |
| --- | --- | --- | --- |
| **Assign Case Manager** | Confirm | Chosen case manager is the owner → lights Handoff / Provider / Notify CM | 30m |

No confirm CTA on: Notify Case Manager (message only after the handoff).

**Product rule (email):** when CM ownership is written, send a **notify** (not a confirm CTA) so the CM knows they own the patient. Monday does not do this today. See [docs/GMAIL_ALERTS.md](docs/GMAIL_ALERTS.md#case-manager-assignment--what-should-happen).

---

## 3. Handoff

No confirmation buttons. Notify referral source / Create Monday.com Record / Create DRK Chart are feed receipts only (unread dots, no Confirm CTA).

---

## 4. Provider selection

| Step | Button label | What it confirms | SLA |
| --- | --- | --- | --- |
| **Select Provider** | Confirm | Selected provider | 30m |
| | Use selected provider | Fallback when no territory match | 30m |
| | Discharge | Reject / discharge path (danger action) | — |
| **Confirm Provider Availability** | Provider confirmed | Provider replied yes | 1h |
| | No response — place manually | Timeout path | — |
| | Placement completed | Manual placement done after timeout | 30m |

No confirm CTA on: Update Monday.com and DRK (auto after availability).

---

## 5. Scheduling

| Step | Button label | What it confirms | SLA |
| --- | --- | --- | --- |
| **Schedule Patient** | Schedule patient | Selected provider slot is the appointment | 48h |
| | No suitable time | Blocker: declined / unavailable / no slots | — |

No confirm CTA on: Send Referral to Provider (packet / delivery receipt).

---

## 6. End-of-day check

| Step | Button label | What it confirms / does | SLA |
| --- | --- | --- | --- |
| **Check Scheduling Status** | Follow up with case manager | Early manual CM Teams follow-up | 24h |
| | Escalate to Nicole | Escalate before / after auto notify | 48h |
| | Escalate to management | Same escalation when past the 48h gate | 48h |
| **Follow Up with Case Manager** | — | Receipt only (auto or prior manual notify) | — |
| **Escalate Unresolved Cases** | — | Receipt only after escalate from Check Scheduling Status | — |

---

## 7. Weekly visit cycle

| Step | Button label | What it confirms / does | SLA |
| --- | --- | --- | --- |
| **Seen patients** | Mark NOT seen · reschedule | Mark miss + start reschedule path | 4h |
| | Escalate for DC (noncompliance) | Queue discharge review | 4h |
| | Confirm rescheduled | Appointment was rescheduled | 4h |
| **Healed patients** | Send to QA discharge | Closure action | 4h |
| **Expired patients** | Remove from schedule · DC | Closure action | 4h |
| **On hold patients** | Move to holds team | Hold handoff | 4h |

---

## Not used in the live stage feed

`StagePatientStepDetail` still has generic **Confirm step** / **Resolve and confirm**. That panel is not what the stage pages drive today.
