# Gmail alerts — final catalog

**11 emails.** Recipients are **per patient** (`AlertContext.case_emails`) at send time, not role env vars. Demo sink: `GMAIL_ALERT_DEFAULT_TO`.

| Kind | Meaning |
| --- | --- |
| **Decide** | Human must act; body ends with a calm CTA (button text = template label) |
| **Notify** | Read and act offline; **no** button |

## Design rules

- **3-second read:** who (patient) → why (one summary) → what next (CTA or clear next step in the summary).
- **Chrome:** patient (hero) → reason → hairline → fields → optional CTA.
- **No badges** (no OVERDUE / ASSIGNED / SENT pills). Urgency lives in the **subject**.
- **No em dashes** or ` - ` pauses in reasons/labels (reads as AI copy).
- **No “case” jargon** in patient-facing copy (say patient / chart). “Case manager” stays only as the job title.
- Subject patterns: `Immediate attention · {Person}` · `New assignment · {Person}` · `New referral · {Person}`.

---

## 1. Confirm all information is correct

| | |
| --- | --- |
| **ID** | `confirm-intake-review` |
| **Kind** | Decide → intake lead |
| **When** | Extract ran; confirm timer passed without confirm |
| **Prerequisites** | Referral PDF received → extract produced 7 fields → human has not confirmed |
| **Reason** | The chart isn’t confirmed so nothing can move. |

**Looks like**

```
Subject: Immediate attention · Eric Gonzalez

Eric Gonzalez
The chart isn’t confirmed so nothing can move.

Identity / Threshold / Completeness / Missing / Unclear
+ 7 required fields (name, DOB, phone, address, HH, wound, insurance)

[ Confirm all information is correct ]
```

---

## 2. Confirm partner is contacted

| | |
| --- | --- |
| **ID** | `confirm-partner-contacted` |
| **Kind** | Decide → intake lead |
| **When** | Partner outreach due; contact not confirmed before timer |
| **Prerequisites** | Intake extract exists → partner call/email owed → not marked contacted |
| **Reason** | The referral partner still hasn’t been reached. |

**Looks like**

```
Subject: Immediate attention · Alva Butler

Alva Butler
The referral partner still hasn’t been reached.

Referral partner: … (email)
Partner replied?: …

[ Confirm partner is contacted ]
```

---

## 3. CM assigned (you own this patient)

| | |
| --- | --- |
| **ID** | `cm-assigned` |
| **Kind** | Notify → assigned CM |
| **When** | CM ownership is written (assign confirm or Monday CM set) |
| **Prerequisites** | Intake ready to hand off → CM chosen → ownership written |
| **Reason** | This patient is yours. Pick a provider. |

**Looks like**

```
Subject: New assignment · Marcus Feldman

Marcus Feldman
This patient is yours. Pick a provider.

Case manager: … (email)
Area: …
Wound or clinical information: …
Next step: Select provider
PDF: …

(no button)
```

---

## 4. No provider confirmed

| | |
| --- | --- |
| **ID** | `use-fallback-provider` |
| **Kind** | Decide → assigned CM |
| **When** | Providers exist in area; none confirmed before timer |
| **Prerequisites** | CM assigned → location known → ≥1 eligible company provider → timer expired with none confirmed |
| **Reason** | Providers are available but none are confirmed yet. |

*Not* the no-territory path (see #5).

**Looks like**

```
Subject: Immediate attention · Maria Alvarez

Maria Alvarez
Providers are available but none are confirmed yet.

Patient location / Eligible providers: Yes / Suggested provider
Provider confirmed?: No / Case manager

[ No provider confirmed ]
```

---

## 5. No company provider in area

| | |
| --- | --- |
| **ID** | `no-area-provider` |
| **Kind** | Notify → management (CC CM) |
| **When** | No company provider in patient territory |
| **Prerequisites** | CM assigned → location known → roster finds **zero** in-area company providers |
| **Reason** | No provider in this area. This needs your call. |

**Looks like**

```
Subject: Immediate attention · Betty Hayes

Betty Hayes
No provider in this area. This needs your call.

Patient location / Eligible: No / Territory / Case manager / Next step

(no button)
```

---

## 6. New patient referral (to provider)

| | |
| --- | --- |
| **ID** | `send-referral-provider` |
| **Kind** | Notify → provider (CC CM) |
| **When** | Stage Ops “Send Referral to Provider” |
| **Prerequisites** | Provider confirmed → referral packet ready → send step runs |
| **Reason** | A new referral packet is ready. Confirm and schedule. |

**Looks like**

```
Subject: New referral · Maria Alvarez

Maria Alvarez
A new referral packet is ready. Confirm and schedule.

Patient / Provider / Case manager / Location / Clinical / Packet / Next step

(no button)
```

---

## 7. Patient still unscheduled

| | |
| --- | --- |
| **ID** | `eod-follow-up-cm` |
| **Kind** | Notify → assigned CM |
| **When** | ~24h after provider selected; scheduled status still blank |
| **Prerequisites** | Provider selected → scheduled status blank → ~24h window passed |
| **Reason** | The provider is set but the patient still isn’t scheduled. |

**Looks like**

```
Subject: Immediate attention · Thomas Reed

Thomas Reed
The provider is set but the patient still isn’t scheduled.

Provider / Case manager / Provider selected / Hours since / Scheduled status

(no button)
```

---

## 8. Still unscheduled needs escalation

| | |
| --- | --- |
| **ID** | `eod-escalate` |
| **Kind** | Notify → management (CC scheduling lead) |
| **When** | ~48h still unscheduled after CM follow-up |
| **Prerequisites** | Provider selected → still not scheduled → CM follow-up already sent → ~48h unresolved |
| **Reason** | Still unscheduled after follow up. This needs escalation. |

**Looks like**

```
Subject: Immediate attention · Frank Owens

Frank Owens
Still unscheduled after follow up. This needs escalation.

Provider / Case manager / timing / Scheduled status / CM follow-up

(no button)
```

---

## 9. Patient not seen 1 week

| | |
| --- | --- |
| **ID** | `not-seen-week-1` |
| **Kind** | Notify → assigned CM |
| **When** | Visit status = not seen, consecutive count = 1 |
| **Prerequisites** | On weekly schedule → visit due → Visit Status not seen → consecutive = 1 |
| **Reason** | Not seen this week. Reschedule is owed. |

**Looks like**

```
Subject: Immediate attention · Patricia Johnson

Patricia Johnson
Not seen this week. Reschedule is owed.

Provider / Case manager / Visit status / Consecutive / Last visit

(no button)
```

---

## 10. Patient not seen 2 weeks in a row

| | |
| --- | --- |
| **ID** | `not-seen-week-2` |
| **Kind** | Notify → assigned CM |
| **When** | Consecutive not seen = 2 |
| **Prerequisites** | Weekly cycle → not seen again → consecutive = 2 |
| **Reason** | Not seen two weeks running. Reschedule now. |

**Looks like**

```
Subject: Immediate attention · Margaret Ellis

Margaret Ellis
Not seen two weeks running. Reschedule now.

Provider / Case manager / Visit status / Consecutive / Last visit

(no button)
```

---

## 11. Patient not seen 3 weeks discharge risk

| | |
| --- | --- |
| **ID** | `not-seen-week-3` |
| **Kind** | Notify → management (CC CM) |
| **When** | Consecutive not seen = 3 |
| **Prerequisites** | Weekly cycle → not seen 3 weeks in a row → discharge path open |
| **Reason** | Not seen three weeks. This needs a discharge decision. |

**Looks like**

```
Subject: Immediate attention · Walter Grant

Walter Grant
Not seen three weeks. This needs a discharge decision.

Provider / Case manager / Visit status / Consecutive / Last visit / Next step

(no button)
```

---

## Not emailed (by design)

| Situation | Instead |
| --- | --- |
| Confirm CM / confirm provider / schedule (happy path) | Auto or in-app; CM gets #3 on assign |
| Manual placement confirm | Removed |
| Healed → QA, expired → remove, hold → holds, reschedule confirm | Auto when Monday Visit Status changes |
| Partner source acknowledgement (flow step 6) | Separate future notify if needed |

## Who gets mail (summary)

| Audience | Emails |
| --- | --- |
| Intake lead | #1, #2 |
| Assigned CM | #3, #4, #7, #9, #10 (+ CC on #5, #6, #11) |
| Provider | #6 |
| Management | #5, #8, #11 |

## Code

- Catalog + reasons: `src/gmail_alert/catalog.py`
- Bodies: `src/gmail_alert/feed_bodies.py`
- HTML chrome: `src/gmail_alert/render.py`
- Recipients: `AlertContext.case_emails` (demo seeds in `case_emails.py`)
- Demo send: `PYTHONPATH=src python3.11 -m gmail_alert`
