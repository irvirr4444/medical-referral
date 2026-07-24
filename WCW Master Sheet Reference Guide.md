# WCW Master Sheet Reference Guide

## What This Is

The Master Sheet is WCW's Monday.com operational board for referrals and their downstream workflow. Each row is a Monday item; columns are fields, statuses, links to other boards, or calculated values. This guide describes the exported schema, not a new database design.

## Accuracy Audit of the Local Snapshot

- The Master Sheet export contains **18,088 top-level items**. Pagination completed as 36 full 500-item pages plus one 88-item page.
- The exporter captured every displayed column value (`text`) and type for those items. It did not fetch item updates, attached-file contents, file assets, or nested subitems unless they exist as a separately exported related board.
- Relation and mirror columns may show no displayed text even when an underlying relation exists. Their schema relationship is accurate below, but their apparent population rate must not be read as a no-link rate.
- `Stage` should not be used as the historical lifecycle source of truth: almost every item remains `In intake`. The observed operating lifecycle is primarily in `Visit Status`.
- This is a direct-relation export, not a recursive copy of the whole Monday CRM. It includes the Master Sheet and each board directly referenced by its relation columns.
- A related board showing zero exported top-level items means this token's API query returned zero items. It does not, by itself, prove that WCW has no data in that business area.



## Exported Board Surface


| Board                    | ID           | Exported records | Result      |
| ------------------------ | ------------ | ---------------- | ----------- |
| Master Sheet             | `5815942462` | 18,088           | exported    |
| Accounts                 | `5886538756` | 0                | exported    |
| Leads                    | `5886538605` | 0                | exported    |
| ai Sales Targets         | `5815942404` | 7                | exported    |
| Unavailable board        | `5815942503` | -                | unavailable |
| Legal Requests           | `5815942417` | 7                | exported    |
| Provider List            | `5962941876` | 183              | exported    |
| WCW Outsource            | `5826165723` | 279              | exported    |
| Outsource 2 - Hold Calls | `5886464933` | 7                | exported    |
| Outsource 3 - Prog Notes | `6030227036` | 22               | exported    |
| Intake Team              | `5815942434` | 21,700           | exported    |
| Subitems of Accounts     | `6915397872` | 0                | exported    |




## How To Read the Dictionary

- **Stored directly** means the value belongs to this Master Sheet item and could be written only after its business owner approves automation.
- **Links** connect to another Monday board. They require a matching rule and must not be populated as free text.
- **Mirrors** show a value from a linked board. They are derived, not independent source fields.
- **Formulas** are calculated by Monday and are never write targets.
- **Observed coverage** is based on rendered text in this snapshot. It is reliable for direct fields; it is deliberately marked unreliable for links and mirrors.



## Key Interpretation Before Automation

For a first intake integration, create only the approved intake row and preserve human ownership of case-manager handoff, provider choice, scheduling, visit, hold, QA, and discharge statuses. The Master Sheet has no obvious dedicated field for diagnosis, insurance, requested services, or the original PDF; WCW must decide whether these belong in Monday, DRK, or both.

## Complete Column Dictionary



### Agency and source relationship


| Column                                 | Type     | What It Represents                                          | Relationship to Master Sheet               | Observed coverage | Configured choices                                                   |
| -------------------------------------- | -------- | ----------------------------------------------------------- | ------------------------------------------ | ----------------- | -------------------------------------------------------------------- |
| Thank Agency Contact (`text3__1`)      | `text`   | Free-text value for 'Thank Agency Contact'.                 | Stored directly on this Master Sheet item. | 16,423 (90.8%)    | -                                                                    |
| Agency Email (`email61__1`)            | `email`  | Email value for 'Agency Email'.                             | Stored directly on this Master Sheet item. | 13,520 (74.75%)   | -                                                                    |
| Territory (`text2__1`)                 | `text`   | Free-text value for 'Territory'.                            | Stored directly on this Master Sheet item. | 17,474 (96.61%)   | -                                                                    |
| Marketer Follow up? (`color_mm51kkcm`) | `status` | Controlled workflow/status value for 'Marketer Follow up?'. | Stored directly on this Master Sheet item. | 306 (1.69%)       | Marketer added; Response Received; Stuck; NOT NEEDED; Follow Up Sent |
| Agency Contact (`text6__1`)            | `text`   | Free-text value for 'Agency Contact'.                       | Stored directly on this Master Sheet item. | 15,607 (86.28%)   | -                                                                    |
| Agency Phone Number (`text41__1`)      | `text`   | Free-text value for 'Agency Phone Number'.                  | Stored directly on this Master Sheet item. | 15,768 (87.17%)   | -                                                                    |




### Board relationships


| Column                                             | Type             | What It Represents                                       | Relationship to Master Sheet                                | Observed coverage                  | Configured choices |
| -------------------------------------------------- | ---------------- | -------------------------------------------------------- | ----------------------------------------------------------- | ---------------------------------- | ------------------ |
| Referring Agency (`connect_boards8`)               | `board_relation` | Board relation field for 'Referring Agency'.             | Links this item to Accounts, Leads.                         | Not reliable from text-only export | -                  |
| Current HH/Hospice (`connect_boards__1`)           | `board_relation` | Board relation field for 'Current HH/Hospice'.           | Links this item to Accounts.                                | Not reliable from text-only export | -                  |
| *Rep Name (`connect_boards`)                       | `board_relation` | Board relation field for '*Rep Name'.                    | Links this item to Sales Targets.                           | Not reliable from text-only export | -                  |
| *Accounts (`connect_boards31`)                     | `board_relation` | Board relation field for ' *Accounts'.                   | Links this item to board 5815942503.                        | Not reliable from text-only export | -                  |
| Legal Request (`connect_boards41`)                 | `board_relation` | Board relation field for 'Legal Request'.                | Links this item to Legal Requests.                          | Not reliable from text-only export | -                  |
| Provider (`connect_boards7`)                       | `board_relation` | Board relation field for 'Provider'.                     | Links this item to Provider List.                           | Not reliable from text-only export | -                  |
| WCW Outsource (`connect_boards9`)                  | `board_relation` | Board relation field for 'WCW Outsource'.                | Links this item to WCW Outsource, Outsource 2 - Hold Calls. | Not reliable from text-only export | -                  |
| Outsource 3 - Prog Notes (`connect_boards0`)       | `board_relation` | Board relation field for 'Outsource 3 - Prog Notes'.     | Links this item to Outsource 3 - Prog Notes.                | Not reliable from text-only export | -                  |
| Intake process (`connect_boards2`)                 | `board_relation` | Board relation field for 'Intake process'.               | Links this item to Intake Team.                             | Not reliable from text-only export | -                  |
| link to Subitems of Accounts (`board_relation__1`) | `board_relation` | Board relation field for 'link to Subitems of Accounts'. | Links this item to Subitems of Accounts.                    | Not reliable from text-only export | -                  |




### Derived and linked data


| Column                                             | Type       | What It Represents                                 | Relationship to Master Sheet                                                                             | Observed coverage                  | Configured choices |
| -------------------------------------------------- | ---------- | -------------------------------------------------- | -------------------------------------------------------------------------------------------------------- | ---------------------------------- | ------------------ |
| Subitems (`subitems__1`)                           | `subtasks` | Subtasks field for 'Subitems'.                     | Contains or exposes subitems from board 7165733741.                                                      | Not reliable from text-only export | -                  |
| Date/Time of Referral Received (`lookup_mm4m58bm`) | `mirror`   | Mirror field for 'Date/Time of Referral Received'. | Mirrors Intake Team: Date/Time of Referral Received through Intake process.                              | Not reliable from text-only export | -                  |
| Address (`lookup_mm4mvzxq`)                        | `mirror`   | Mirror field for 'Address'.                        | Mirrors Accounts: Address; Leads: linked value through Referring Agency.                                 | Not reliable from text-only export | -                  |
| City (`lookup_mm4mz18y`)                           | `mirror`   | Mirror field for 'City'.                           | Mirrors Accounts: City; Leads: linked value through Referring Agency.                                    | Not reliable from text-only export | -                  |
| Zip (`lookup_mm4mxhrb`)                            | `mirror`   | Mirror field for 'Zip'.                            | Mirrors Accounts: Zip; Leads: linked value through Referring Agency.                                     | Not reliable from text-only export | -                  |
| State (`lookup_mm4myta5`)                          | `mirror`   | Mirror field for 'State'.                          | Mirrors Accounts: State; Leads: linked value through Referring Agency.                                   | Not reliable from text-only export | -                  |
| Main Phone Number (`lookup_mm4m7qx9`)              | `mirror`   | Mirror field for 'Main Phone Number'.              | Mirrors Accounts: Main Phone #; Leads: linked value through Referring Agency.                            | Not reliable from text-only export | -                  |
| Fax Number (`lookup_mm4mn07s`)                     | `mirror`   | Mirror field for 'Fax Number'.                     | Mirrors Accounts: Fax Number; Leads: linked value through Referring Agency.                              | Not reliable from text-only export | -                  |
| Comm Pref (`lookup_mm17tpbz`)                      | `mirror`   | Mirror field for 'Comm Pref'.                      | Mirrors Accounts: Comm Pref; Leads: linked value through Referring Agency.                               | Not reliable from text-only export | -                  |
| Comm Status (`mirror0`)                            | `mirror`   | Mirror field for 'Comm Status'.                    | Mirrors Accounts: status_1; Leads: lead_status through Referring Agency.                                 | Not reliable from text-only export | -                  |
| Agency Type (`mirror3`)                            | `mirror`   | Mirror field for 'Agency Type'.                    | Mirrors Accounts: Agency Type; Leads: Agency Type through Referring Agency.                              | Not reliable from text-only export | -                  |
| Primary Contact (`mirror4`)                        | `mirror`   | Mirror field for 'Primary Contact'.                | Mirrors Accounts: connect_boards; Leads: Do not edit *Duplicated Lead Detector through Referring Agency. | Not reliable from text-only export | -                  |
| HH/Agency Type (`mirror__1`)                       | `mirror`   | Mirror field for 'HH/Agency Type'.                 | Mirrors Accounts: Agency Type through Current HH/Hospice.                                                | Not reliable from text-only export | -                  |
| Marketer (`mirror`)                                | `mirror`   | Mirror field for 'Marketer'.                       | Mirrors Accounts: Marketer; Leads: Marketer through Referring Agency.                                    | Not reliable from text-only export | -                  |
| Rep's Team (`mirror32`)                            | `mirror`   | Mirror field for 'Rep's Team'.                     | Mirrors Sales Targets: Team through *Rep Name.                                                           | Not reliable from text-only export | -                  |
| Legal Status (`mirror27`)                          | `mirror`   | Mirror field for 'Legal Status'.                   | Mirrors Legal Requests: Status through Legal Request.                                                    | Not reliable from text-only export | -                  |
| Provider name (`mirror03__1`)                      | `mirror`   | Mirror field for 'Provider name'.                  | Mirrors Provider List: Provider name copy through Provider.                                              | Not reliable from text-only export | -                  |
| Provider Email (`mirror8`)                         | `mirror`   | Mirror field for 'Provider Email'.                 | Mirrors Provider List: Email through Provider.                                                           | Not reliable from text-only export | -                  |




### Intake handoff and assignment


| Column                                   | Type     | What It Represents                                                | Relationship to Master Sheet               | Observed coverage | Configured choices          |
| ---------------------------------------- | -------- | ----------------------------------------------------------------- | ------------------------------------------ | ----------------- | --------------------------- |
| Case Manager (`deal_owner`)              | `people` | Monday user/person assignment for 'Case Manager'.                 | Stored directly on this Master Sheet item. | 17,117 (94.63%)   | -                           |
| Sent to CM (`status7__1`)                | `status` | Controlled workflow/status value for 'Sent to CM'.                | Stored directly on this Master Sheet item. | 16,901 (93.44%)   | Yes; No                     |
| Time Sent to CM (`time_sent_to_cm__1`)   | `date`   | Date or date/time value for 'Time Sent to CM'.                    | Stored directly on this Master Sheet item. | 15,075 (83.34%)   | -                           |
| Sent By (`people0`)                      | `people` | Monday user/person assignment for 'Sent By'.                      | Stored directly on this Master Sheet item. | 17,456 (96.51%)   | -                           |
| Referral Sent to Provider (`status3__1`) | `status` | Controlled workflow/status value for 'Referral Sent to Provider'. | Stored directly on this Master Sheet item. | 16,687 (92.25%)   | Yes; No                     |
| Sent to Nexus (`status89`)               | `status` | Controlled workflow/status value for 'Sent to Nexus'.             | Stored directly on this Master Sheet item. | 16,935 (93.63%)   | Yes; No                     |
| Time Sent to Nexus (`date5__1`)          | `date`   | Date or date/time value for 'Time Sent to Nexus'.                 | Stored directly on this Master Sheet item. | 16,891 (93.38%)   | -                           |
| Intake Group Copy (`status_11__1`)       | `status` | Controlled workflow/status value for 'Intake Group Copy'.         | Stored directly on this Master Sheet item. | 18,088 (100.0%)   | Follow Up Patients; Done; . |




### Other operational fields


| Column                                | Type            | What It Represents                                                                                | Relationship to Master Sheet               | Observed coverage | Configured choices                                                                                                                                                       |
| ------------------------------------- | --------------- | ------------------------------------------------------------------------------------------------- | ------------------------------------------ | ----------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Wx Order Included? (`color_mkzdev37`) | `status`        | Controlled workflow/status value for 'Wx Order Included?'.                                        | Stored directly on this Master Sheet item. | 701 (3.88%)       | Working on getting; YES; UNABLE TO REACH; Sent To Nadine                                                                                                                 |
| *Current stage start date (`date1`)   | `date`          | Date or date/time value for '*Current stage start date'.                                          | Stored directly on this Master Sheet item. | 18,086 (99.99%)   | -                                                                                                                                                                        |
| Stage (`deal_stage`)                  | `status`        | Current intake marker in the observed data. It is not reliable as the historical lifecycle state. | Stored directly on this Master Sheet item. | 18,085 (99.98%)   | In intake; Complete; Lost; QA Hold; New - Schedule; Return from QA Hold - Schedule; Short Term - Hospitalized; Long Term Hold; Deceased; Opt Out; Returning - Scheduling |
| Comments (`text00__1`)                | `text`          | Free-text operational comments.                                                                   | Stored directly on this Master Sheet item. | 9,611 (53.13%)    | -                                                                                                                                                                        |
| F/up Comments (`text81__1`)           | `text`          | Free-text value for 'F/up Comments'.                                                              | Stored directly on this Master Sheet item. | 498 (2.75%)       | -                                                                                                                                                                        |
| Last update (`date`)                  | `date`          | Date or date/time value for 'Last update'.                                                        | Stored directly on this Master Sheet item. | 1,980 (10.95%)    | -                                                                                                                                                                        |
| Time Since Entry (`time_tracking`)    | `time_tracking` | Time-tracking value for 'Time Since Entry'.                                                       | Stored directly on this Master Sheet item. | 18,086 (99.99%)   | -                                                                                                                                                                        |
| Kathy Email (`email0`)                | `email`         | Email value for 'Kathy Email'.                                                                    | Stored directly on this Master Sheet item. | 18,085 (99.98%)   | -                                                                                                                                                                        |
| Due Date (`date_mm2gybh5`)            | `date`          | Date or date/time value for 'Due Date'.                                                           | Stored directly on this Master Sheet item. | 3,967 (21.93%)    | -                                                                                                                                                                        |
| ACT Ready (`color_mm5bx27n`)          | `status`        | Controlled workflow/status value for 'ACT Ready'.                                                 | Stored directly on this Master Sheet item. | 512 (2.83%)       | ACT Delay; ACT Ready; DO NOT CALL                                                                                                                                        |




### Patient and referral intake


| Column                                | Type       | What It Represents                                                           | Relationship to Master Sheet               | Observed coverage | Configured choices                                                                                |
| ------------------------------------- | ---------- | ---------------------------------------------------------------------------- | ------------------------------------------ | ----------------- | ------------------------------------------------------------------------------------------------- |
| Name (`name`)                         | `name`     | Primary label for the Master Sheet item; this is the row's visible identity. | Stored directly on this Master Sheet item. | 18,088 (100.0%)   | -                                                                                                 |
| Patient DoB (`date12`)                | `date`     | Patient date of birth.                                                       | Stored directly on this Master Sheet item. | 17,911 (99.02%)   | -                                                                                                 |
| Date/Time Referral Received (`date7`) | `date`     | Date/time WCW recorded the referral as received.                             | Stored directly on this Master Sheet item. | 17,646 (97.56%)   | -                                                                                                 |
| POS (`status_1__1`)                   | `status`   | Point of service/location category used by WCW.                              | Stored directly on this Master Sheet item. | 15,753 (87.09%)   | SNF; ALF; HOME; Fresno clinic; Northridge clinic; Inglewood clinic; Visalia Clinic; Austin Clinic |
| Patient Contacted (`status__1`)       | `status`   | Controlled workflow/status value for 'Patient Contacted'.                    | Stored directly on this Master Sheet item. | 16,492 (91.18%)   | LVM; Yes; No; VM FULL/VM NOT SET UP                                                               |




### Provider and scheduling


| Column                                                      | Type      | What It Represents                                                                      | Relationship to Master Sheet               | Observed coverage | Configured choices         |
| ----------------------------------------------------------- | --------- | --------------------------------------------------------------------------------------- | ------------------------------------------ | ----------------- | -------------------------- |
| Appointment Date (`date9__1`)                               | `date`    | Date or date/time value for 'Appointment Date'.                                         | Stored directly on this Master Sheet item. | 15,291 (84.54%)   | -                          |
| Scheduling Complete (`status0__1`)                          | `status`  | Controlled workflow/status value for 'Scheduling Complete'.                             | Stored directly on this Master Sheet item. | 16,679 (92.21%)   | Yes; No                    |
| Scheduled Status (`color_mkq3gga`)                          | `status`  | Controlled workflow/status value for 'Scheduled Status'.                                | Stored directly on this Master Sheet item. | 18,088 (100.0%)   | Scheduled; Not Scheduled   |
| Provider Change (`label`)                                   | `status`  | Controlled workflow/status value for 'Provider Change'.                                 | Stored directly on this Master Sheet item. | 18,088 (100.0%)   | Complete; OK; Requested    |




### Visit, hold, and discharge


| Column                                 | Type       | What It Represents                                                                                                            | Relationship to Master Sheet               | Observed coverage | Configured choices                                                                                                                                                                                                                                          |
| -------------------------------------- | ---------- | ----------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------ | ----------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| QA Hold Reason (`label99`)             | `status`   | Controlled workflow/status value for 'QA Hold Reason'.                                                                        | Stored directly on this Master Sheet item. | 18,088 (100.0%)   | Hospitalized; Deceased; Billing Issue; Agency Issue; Intake Issue; Not on Hold; No Comm log updated; Immediate Discharge; Not on wound expert; Pending Visit; Healed; Pt Issue (+1 more)                                                                    |
| LEAD FOLLOWUP (`color_mkxwsx63`)       | `status`   | Controlled workflow/status value for 'LEAD FOLLOWUP'.                                                                         | Stored directly on this Master Sheet item. | 1,138 (6.29%)     | for CM follow up; Being Seen; waiting on other                                                                                                                                                                                                              |
| Visit Status (`status5__1`)            | `status`   | Primary observed operational lifecycle signal in the snapshot, including seen, hold, scheduled, and discharge-related values. | Stored directly on this Master Sheet item. | 18,088 (100.0%)   | Scheduled; Seen; Declined; Pending; Hospitalized; .; Deceased; On Holds List; Pending - Can't Reach Patient; Pending - No Provider; Immediate DC; Being seen in the clinic (+10 more)                                                                       |
| DC reason (`color_mm1mssvv`)           | `status`   | Controlled workflow/status value for 'DC reason'.                                                                             | Stored directly on this Master Sheet item. | 18,088 (100.0%)   | NONCOMPLIANT; QA - WX HEALED; CANCELLED SERVICE; MOVED AWAY; Hospice/HH to Manage; NOT DISCHARGED; 4 HOLDS CALL ATTEMPTS; REF SOURCE CANCEL; OUT OF ROUTE/DUE TO DISTANCE; UNSAFE ENVIRONMENT/SAFETY RISK; ANOTHER WX CARE CO; DECLINED SERVICES (+3 more)  |
| Visit Status TEST (`color_mm1ms88r`)   | `status`   | Controlled workflow/status value for 'Visit Status TEST'.                                                                     | Stored directly on this Master Sheet item. | 18,088 (100.0%)   | DC - NEW REFERRAL; DC - FOLLOW UP; DC - ON HOLDS; test 2; TEST                                                                                                                                                                                              |
| Discharge Reason (`dropdown_mm1t7rd3`) | `dropdown` | Configured discharge reason selection; useful only after an appropriate discharge decision.                                   | Stored directly on this Master Sheet item. | 1,803 (9.97%)     | QA - WX HEALED; CANCELLED SERVICES; DECLINED SERVICES; OUT OF ROUTE / DUE TO DISTANCE; NONCOMPLIANT; ANOTHER WX CARE CO; HOSPICE/HH TO MANAGE; 4 HOLDS CALL ATTEMPTS; REF SOURCE CANCELLATION; UNSAFE ENVIRONMENT; MOVED AWAY; UNDER 18 YEARS OLD (+7 more) |


