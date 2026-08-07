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
| **Overview** | Company-wide impact (today / week / month), command summary, live activity, WCW network, annual capacity projection |
| **1. Referral intake** | Inbox processing, live work queues, exceptions, referral workspace + PDFs |
| **2. Handoff** | Acknowledgements, Monday.com / DRK destination prep |
| **3. Assignment** | Territory → case-manager matching (one / none / multi) |
| **4. Provider selection** | Company-provider suggestions and coverage exceptions |
| **5. Scheduling** | Route windows, one-hour response monitoring |
| **6. End-of-day check** | Unscheduled / inconsistent field exception list for management |
| **7. Weekly visit cycle** | Seen / not-seen, holds, healed/expired, discharge approvals |

Every stage tab also has:

- **Stage impact board** — time returned by *this* part of the workflow (Today / This week / This month)
- **Before → With automation** comparison for that stage
- **Live work queue** — interactive cases the boss can click through
- **Stage-specific live activity**

---

## Overview (open here first)

### Capacity returned
Tabs: **Today · This week · This month**

Shows time returned plus volume (patients, pages, destinations prepared, duplicates blocked, incomplete caught early, manual actions avoided).

**Important for the pitch:** stage impact boards **add up to Overview**. Intake + Handoff + Assignment + Provider + Scheduling + End-of-day + Weekly = Overview totals for the same period.

### Live workflow command summary
Cross-stage queue counts: queues, live cases, open actions, approval / blocked queues.

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

---

## Stage pages — live work queues

Each stage has a **Live work queue** (not labeled “scenarios”).

- Filter: All / Ready / Attention / Blocked / Approval (only filters that exist on that stage)
- Sub-tabs: one documented branch at a time
- Cases: patient, rule, owner, minutes returned, human-controlled where needed
- Clicking an action completes or escalates the case, returns minutes, and posts to that stage’s activity feed

### Coverage built so far (examples per branch)

| Stage | What leadership sees |
| --- | --- |
| **Intake** | New docs, field classification, complete vs needs info, unreachable partner, duplicates, private review draft |
| **Handoff** | Not eligible, acknowledgement, destination writes |
| **Assignment** | One territory match, no match, multiple matches |
| **Provider** | Clear match, ambiguous, no coverage, selected but not contacted |
| **Scheduling** | Route windows, confirm within hour, no confirm |
| **End-of-day** | Consistent fields, blank/conflict, exception list, resolvable vs escalate |
| **Weekly** | Visit outcomes, missed visits, healed/expired, holds, return-ready, discharge approval |

**Active exceptions & approvals** sit on each stage (intake and others), scoped to that stage — not dumped on Overview.

---

## Intake extras (tab 1)

- **Process referral inbox** / **Reset day**
- Hybrid non-zero start: board already shows mid-morning work; Process inbox *adds* to totals
- Workflow spine, today’s impact strip, referral inbox queue
- Referral workspace with extracted fields + source PDF review (sample PDFs)

---

## What we intentionally avoided

- Demo / simulation / “illustrative only” chrome that breaks executive trust  
- Claiming the bot makes clinical or discharge decisions  
- Presenting capacity as headcount reduction  
- One combined “Handoff & assignment” or “Provider & scheduling” tab — those are separate so each automation’s time saved is visible  

---

## How to walk the boss through it (suggested 8–10 min)

1. **Overview** — Today impact → This week → This month. Point at network cards. Open capacity projection; note assisted minutes fixed at 8 and “staff capacity returned.”
2. **Intake** — Process inbox once. Open a live queue branch. Resolve one ready case and one exception. Show PDF vs extracted fields.
3. **Assignment** — One match vs no match vs multi match. Emphasize human confirm.
4. **Provider + Scheduling** — Suggestion vs send/confirm remains human-controlled; one-hour timer story.
5. **End-of-day** — One exception list instead of auditing every board.
6. **Weekly** — Missed visits / holds / discharge *review* (approval stays human).
7. Back to **Overview** — stage times still roll up; annual capacity if they want the yearly number.

---

## What’s real vs mock in this UI

| Real / grounded | Mock / demo-safe |
| --- | --- |
| WCW roster counts and names from loaded network data | No live Outlook / Monday.com / DRK API calls in the UI |
| Workflow rules mapped from Flow + pipeline docs | Sample patients and PDFs |
| Capacity math from assumptions (36 → 8 min model) | Historical week/month priors for the impact board |
| Human-control language everywhere decisions matter | Interactive “resolve” actions are local demo state |

---

## Bottom line for leadership

This console shows **where time comes back**, **which cases still need people**, and **that automation prepares work while WCW keeps control** — across intake through the weekly visit cycle, with impact that rolls from each stage up to the company Overview.
