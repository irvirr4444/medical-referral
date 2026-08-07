# WCW Boss Demo — What We Built

**Purpose:** An interactive walkthrough for West Coast Wound leadership showing how referral automation returns capacity to the existing team — without cutting headcount, and without taking clinical or approval decisions away from WCW employees.

**Product framing:** This should feel like a live operations console, not a labeled “demo.” Fake/sample data is fine; the story is operational.

**How to run:** from `frontend/` — `npm install` then `npm run dev`.

---

## The story in one sentence

Incoming referrals are read, checked, and prepared for Monday.com and DRK so the team reviews exceptions and confirms the next action — **36 minutes of manual intake → 8 minutes of focused review**.

Automation prepares information and monitors deadlines. **WCW employees retain patient, clinical, scheduling, and approval decisions.**

---

## Navigation (what the boss will click)

| Tab | What it shows |
| --- | --- |
| **Overview** | Company-wide impact, patients requiring attention, live activity, WCW network, annual capacity projection, and the live patient census |
| **1. Referral intake** | Action worklist + automation impact for inbox / extraction / confirm |
| **2. Handoff** | Acknowledgements and Monday.com / DRK destination prep |
| **3. Assignment** | Territory → case-manager matching (one / none / multi) |
| **4. Provider selection** | Company-provider suggestions and coverage exceptions |
| **5. Scheduling** | Route windows, one-hour response monitoring |
| **6. End-of-day check** | Unscheduled / inconsistent field exception list for management |
| **7. Weekly visit cycle** | Seen / not-seen, holds, healed/expired, discharge approvals |

Every stage tab (1–7) is split into two views:

| Sub-tab | Purpose |
| --- | --- |
| **Action** | Patients who need something *now* on this stage — one card per patient, primary action first |
| **Automation impact** | Time returned by this stage (Today / This week / This month), before→after comparison, and stage activity |

Clicking a stage Action resolves or escalates that patient’s open item, returns minutes, posts to the activity feed, and — if they are on a live patient path — **advances them to the next stage tab automatically**.

---

## Overview (open here first)

### Capacity returned
Tabs: **Today · This week · This month**

Shows time returned plus volume (patients, pages, destinations prepared, duplicates blocked, incomplete caught early, manual actions avoided).

**Important for the pitch:** stage impact boards **add up to Overview**. Intake + Handoff + Assignment + Provider + Scheduling + End-of-day + Weekly = Overview totals for the same period.

### Patients requiring attention
Replaces the old opaque “queues / live cases / open actions” summary.

- **One number that matters:** unique patients who need action (each patient counted once under their highest-priority open item)
- Split into **Ready to process · Needs follow-up · Blocked or awaiting approval**
- **Where the work is now** — bar chart across all seven stages; **click any stage to jump straight into that stage’s Action view** (scrolls to the top)

### Live activity
Cross-stage operational events from today’s work.

### WCW Network
Clickable counts (not a separate “View roster” button):

- **26** case managers  
- **380** company providers  
- **1,148** DRK facilities  

Each card opens the roster for that group.

### Annual capacity projection
Adjustable referrals/day, manual minutes, working days, etc.

- **Assisted minutes locked at 8** (focused review — not editable)
- “Full-time staff capacity returned” = time freed for the team (not a headcount cut)

### Live patient census (bottom of Overview)
Interactive spine for walking a real patient through Intake → Weekly.

- **24 patients** seeded across the seven stages with **distinct live queue paths** (ready confirm, missing fields, unreachable partner, territory conflict, no provider coverage, one-hour no-reply, end-of-day exceptions, third not-seen, healed/expired, holds, and more)
- Progress is real: Intake patients show **0 of 7**, mid-path patients show **2–5 of 7**, weekly patients show **6 of 7**
- **Choose patient** opens a searchable modal grouped by current stage
- Advance resolves the current open step, returns minutes, and jumps into the matching stage Action queue with that patient highlighted
- Click any earlier/later spine step to jump there without resolving
- PDF workspace does **not** auto-open when you land on Intake — only when staff click **Review Referral**

---

## Stage Action pages

Designed for a boss demo, not a dense branch catalog:

- **Action / Automation impact** tabs so the eye is not split between “what needs doing” and “what time came back”
- Action view: compact **patient worklist** (one card per patient, most urgent open item first)
- Filters: All / Ready / Attention / Blocked / Approval (only filters that exist on that stage)
- Automation impact view: stage impact board + before→after comparison + live activity
- Intake Action no longer shows the redundant “Process referral inbox / Reset day” strip — the worklist *is* the action surface
- Future steps on a patient’s path stay **upcoming** (hidden from Action counts) until the prior step is cleared

### Coverage leadership can walk

| Stage | Example paths in the live census |
| --- | --- |
| **Intake** | New packet, ready to confirm, missing fields, needs information, unreachable partner, duplicates, private review draft |
| **Handoff** | Acknowledgement prepared, destination write outcomes, not eligible for handoff |
| **Assignment** | One territory match, no match, multiple matches / facility vs residence conflict |
| **Provider** | Clear match, ambiguous match, no coverage, selected but not contacted |
| **Scheduling** | Route windows, confirm within hour, no confirm within one hour |
| **End-of-day** | Already notified, uncovered unscheduled, resolvable by CM/lead, management escalation |
| **Weekly** | Seen, early not-seen, third not-seen, healed QA, expired discharge, hold remain |

---

## What we intentionally avoided

- Demo / simulation / “illustrative only” chrome that breaks executive trust  
- The word **“scenario”** anywhere in the UI copy (queues, actions, and care paths instead)  
- Claiming the bot makes clinical or discharge decisions  
- Presenting capacity as headcount reduction  
- One combined “Handoff & assignment” or “Provider & scheduling” tab — those are separate so each automation’s time saved is visible  
- Auto-opening the PDF modal just because Intake was selected  

---

## How to walk the boss through it (suggested 8–10 min)

1. **Overview** — Today impact → This week → This month. Point at **Patients requiring attention** (unique patients, not opaque queue math). Click a stage bar to jump into Action.
2. **Live patient census** — Choose patient → pick someone mid-path (e.g. Assignment or Weekly). Show **X of 7 complete**. Advance once and land on the next Action tab.
3. **Intake Action** — Resolve a ready patient; watch them move to Handoff. Open PDF only via Review Referral if you want the extraction story.
4. **Assignment / Provider / Scheduling** — One match vs conflict vs no coverage; one-hour timer story. Emphasize human confirm.
5. **End-of-day** — Exception list and management escalations in Action; impact on Automation impact.
6. **Weekly** — Missed visits / holds / discharge *review* (approval stays human).
7. Back to **Overview** — stage times still roll up; patient counts update as you clear work; annual capacity if they want the yearly number.

---

## What’s real vs mock in this UI

| Real / grounded | Mock / demo-safe |
| --- | --- |
| WCW roster counts and names from loaded network data | No live Outlook / Monday.com / DRK API calls in the UI |
| Workflow rules mapped from Flow + pipeline docs | Sample patients and PDFs |
| Capacity math from assumptions (36 → 8 min model) | Historical week/month priors for the impact board |
| Human-control language everywhere decisions matter | Interactive “resolve” actions are local demo state |
| 24-patient census mapped onto real queue branches | Generated follow-through steps fill the rest of each path |

---

## Bottom line for leadership

This console shows **which patients need people right now**, **where those patients sit in the path**, and **that automation prepares work while WCW keeps control** — across intake through the weekly visit cycle, with impact that rolls from each stage up to the company Overview.
