# **Referral → Scheduling → Visit Workflow**

## **1\. Referral Intake**

1. **Referral arrives** — email or fax (PDF attached) Sources: SNF · ALF · hospital · home health · physician office · self-referral

2. **Open PDF, extract the so mentioned “6 required fields**  
3. **Call referral partner** (every referral): thank · confirm · request anything missing  
4. **Referral partner reachable?**   
   * **No →** Forward PDF to the source's assigned Marketer to follow up (address unverified \= can't schedule) → proceeds to Step 5  
   * **Yes →** proceeds to Step 5

**Questions:**  
\- In which email are the pdfs supposed to arrive? Can we have access to that email?  
\- Is there a predefined format of the pdf other than the 7 pdf we have initially retrieved?  
\- What are the 6 required fields in the referral intake pdf?  
\- Who is supposed to call the referral partner after the pdf is taken? And how do we get notified if the referral was confirmed or anything was missing?

## **2\. Handoff & Assignment**

5. **Ready to hand off**   
6. **Email referrals**: send an acknowledgement to the source, CC the assigned case manager  
7. Splits into two parallel actions:  
   * **Email the assigned case manager \+ PDF** (CM chosen by patient location)  
   * **Forward PDF to face sheet team** — build chart in DRK  
8. **Log info-box half of monday.com** (after both forwards done)  
9. **Case manager owns the patient**

**Questions:**  
\- How is the case manager assigned? And how do we know who?  
\- What is DRK? And can we have access?   
\- Who sends the email to the assigned CM?

## **3\. Provider Selection & Scheduling**

10. **CM selects the appropriate company provider** from their list of assigned providers in their area 

11. **Provider available in that area?**  
    * **No →** (no provider assigned, or too far from territory) → Nicole reviews → **Discharge (DC)**  
    * **Yes →** continue  
12. **Provider confirms within 1 hour?**  
    * **No →** CM places patient where it best fits the provider's schedule → proceeds to Step 14  
    * **Yes →** **Schedule per provider's availability**  
13. → **Patient scheduled (24–48 hrs)**  
14. **CM fills CM-half of monday.com \+ DRK**

**Questions:**  
\- Where do we see the provider’s schedule?  
\- What is the communication channel between CM and the provider?

## **4\. End-of-Day Check**

15. **End of day: patient scheduled?**  
    * **Blank →** Lead follows up with CM over Teams: why not scheduled  
      * **Resolvable by CM/lead?**  
        * **No →** Escalate to leadership → proceeds to Step 16  
        * **Yes →** proceeds to Step 16  
    * **Scheduled →** proceeds to Step 16  
16. **Patient enters the weekly schedule**

**Questions:**  
\-How can we know that the patient's decision is resolvable by the CM/lead?

## **5\. Weekly Visit Cycle**

17. **Weekly visit on Masters \+ route mgmt**  
18. **Visit completed?** (DRK progress note) 

     **Not seen →** **Mark NOT seen, reschedule weekly**   
    * **3 weeks in a row not seen?**  
      * **Yes →** CM sends referral to upper mgmt for **Discharge (DC)** approval, reason: noncompliance  
        * **No →** loops back to Step 17 (Weekly visit) — *unless the patient is placed on hold, in which case they exit this loop and move to Step 20 (Patient on hold)*  
    * **Seen →** **Initial visit: mark SEEN on monday.com** ①

       🗒️ *Expert note: This is the initial visit only — marked SEEN on the monday.com CRM by the case manager. Subsequent visits do not re-trigger a monday.com update (see correction above).*

19. **Wound healed or patient expired?**  
    * **Healed / expired →**  
      * Healed: provider → QA → discharge  
      * Expired: CM removes from schedule → DC approval  
    * **(neither) →** continue to Step 20  
20. **Patient on hold?** (hospital / vacation / other)  
    * **Yes →** **Move to holds team \+ holds list**  
      * **Ready to return?**  
        * **No →** loops back to holds list  
        * **Yes →** loops back into the weekly visit cycle (Step 17\)  
    * **No →** loops back into the weekly visit cycle (Step 17\)

## Additional Questions

1. Are there any other Saas/Tools that matter in the workflow besides Monday and DRK?   
   How would you rank these tools in terms of dependency from Critical (The workflow stops without these tools) to supplementary (The workflow continuous normally without these tools)  
2. Where do you store the PDFs in the long-term (Google Drive or any other cloud service)? Who has access to that storage? Do you have backup plans?  
3. How large is this storage (GBs, pdf files, image, text, specify any unit) and when did you start using these storages?

