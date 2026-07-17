# Reviewed Gold Set Notes

## BUTLER, ALVA demo.json
- Status: fixed
- Confidence: medium
- Notes: Confirmed from text-layer chart. This is not a clean referral form; medication list intentionally excluded from requested_services, and the provider street address was not treated as a facility name.

## EC - REFERRAL FORM.json
- Status: fixed
- Confidence: high
- Notes: Confirmed from handwritten West Coast referral form. Laurie Peercy is PCP contact, not the referring provider; the referring source is Accent Care Home Health.

## fax20260710-1422744-nkqbp2.json
- Status: fixed
- Confidence: medium
- Notes: Re-audited against pages 3, 5, and 6. Page 3 confirms the demographics, clinic, Pedram Shawn Abdian signature, DME order, and the 90044-5608 address normalization. Pages 5-6 show the cough/XR chest and GERD/H. pylori stool orders in the same outpatient packet, so they remain in requested_services.

## fax20260711-48483-ougwp2.json
- Status: fixed
- Confidence: medium
- Notes: Confirmed from encounter sheet, outpatient referral form, insurance page, and discharge summary. Used the handwritten recuperative-care address as the active discharge destination and moved the crossed-out San Pedro address into notes.

## fax20260713-16377-syrmla.json
- Status: fixed
- Confidence: medium
- Notes: Re-audited against pages 1-2. Page 1 is the DNA fax cover with the agency phone/fax and the wound-care request; page 2 lists Referral Source / Primary Physician as ROJAS, ARBIS and shows the PT/Skilled Nursing assignments plus diagnosis list. Kept ROJAS as referring_provider_name and DNA Home Health Services as referring_facility/contact, which remains a sender-versus-provider split.

## fax20260713-2485963-94q8kc.json
- Status: fixed
- Confidence: medium
- Notes: Re-audited against pages 1, 3, 4, 5, and 8. Page 3 explicitly labels GEVORGIAN HRANT as the referring physician; page 4 shows a HOME HLTH case-management order annotated "wound care"; page 5 contains the daily wound-care order; page 8 supports case-management / post-hospitalization planning. The placeholder phone number and homeless Barstow address both appear verbatim in the source.

## fax20260713-620-tw3x6v.json
- Status: fixed
- Confidence: medium
- Notes: Corrected the patient first name to Khojagul and set the facility from the fax header. The clinician/aide lines were not treated as requested services because this one-page fax does not contain an explicit service order.
