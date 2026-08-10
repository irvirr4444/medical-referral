import type { StageOpsFixture } from '../types'
import { ev } from './event'

/** Intake ops fixture — Butler, Alva leads open/blocker sections. */
export const INTAKE_OPS_FIXTURE: StageOpsFixture = {
  stageId: 'intake',
  events: [
    // Butler — primary story
    ev('intake', 'emails-arrived', 'butler-alva', 'Butler, Alva', 'August 10, 2026 at 9:14 AM', 'Chart export PDF received in WCW inbox', 'resolved'),
    ev('intake', 'extracted', 'butler-alva', 'Butler, Alva', 'August 10, 2026 at 9:17 AM', 'Canonical referral extracted · 3 pages', 'resolved'),
    ev('intake', 'needs-information', 'butler-alva', 'Butler, Alva', 'August 10, 2026 at 9:17 AM', '6 of 7 fields complete · home-health agency missing', 'open', 'Waiting 8h'),
    ev('intake', 'awaiting-approval', 'butler-alva', 'Butler, Alva', 'August 10, 2026 at 9:18 AM', 'Review email sent · awaiting human reply', 'open', 'Waiting 8h'),
    ev('intake', 'destination-gated', 'butler-alva', 'Butler, Alva', 'August 10, 2026 at 9:18 AM', 'Monday and DRK writes blocked pending agency + approval', 'open', 'Waiting 8h'),

    // Aug 10 others
    ev('intake', 'emails-arrived', 'rosa-delgado', 'Rosa Delgado', 'August 10, 2026 at 8:42 AM', 'Wound care referral PDF from Coastal HH', 'resolved'),
    ev('intake', 'extracted', 'rosa-delgado', 'Rosa Delgado', 'August 10, 2026 at 8:45 AM', 'Canonical referral extracted', 'resolved'),
    ev('intake', 'awaiting-approval', 'rosa-delgado', 'Rosa Delgado', 'August 10, 2026 at 8:46 AM', 'Complete fields · review sent', 'open', 'Waiting 9h'),

    ev('intake', 'emails-arrived', 'samuel-ortiz', 'Samuel Ortiz', 'August 10, 2026 at 10:05 AM', 'Physician fax PDF attached', 'resolved'),
    ev('intake', 'extracted', 'samuel-ortiz', 'Samuel Ortiz', 'August 10, 2026 at 10:08 AM', 'Canonical referral extracted', 'resolved'),
    ev('intake', 'needs-information', 'samuel-ortiz', 'Samuel Ortiz', 'August 10, 2026 at 10:08 AM', 'Insurance missing', 'open', 'Waiting 7h'),
    ev('intake', 'awaiting-approval', 'samuel-ortiz', 'Samuel Ortiz', 'August 10, 2026 at 10:09 AM', 'Review highlights insurance gap', 'open', 'Waiting 7h'),

    ev('intake', 'emails-arrived', 'evelyn-brooks', 'Evelyn Brooks', 'August 10, 2026 at 11:20 AM', 'Hospital discharge packet', 'resolved'),
    ev('intake', 'extracted', 'evelyn-brooks', 'Evelyn Brooks', 'August 10, 2026 at 11:24 AM', 'Canonical referral extracted', 'resolved'),
    ev('intake', 'duplicate-risk', 'evelyn-brooks', 'Evelyn Brooks', 'August 10, 2026 at 11:25 AM', 'Probable Monday match · human review required', 'open', 'Waiting 6h'),
    ev('intake', 'awaiting-approval', 'evelyn-brooks', 'Evelyn Brooks', 'August 10, 2026 at 11:26 AM', 'Blocked on duplicate classification', 'open', 'Waiting 6h'),

    ev('intake', 'emails-arrived', 'thomas-reed', 'Thomas Reed', 'August 10, 2026 at 1:05 PM', 'New source document received', 'resolved'),
    ev('intake', 'extracted', 'thomas-reed', 'Thomas Reed', 'August 10, 2026 at 1:09 PM', 'Canonical referral extracted', 'resolved'),
    ev('intake', 'approved-rejected', 'thomas-reed', 'Thomas Reed', 'August 10, 2026 at 2:40 PM', 'Approved by reviewer', 'resolved'),
    ev('intake', 'destination-gated', 'thomas-reed', 'Thomas Reed', 'August 10, 2026 at 2:40 PM', 'Destination preparation authorized', 'resolved'),

    // Aug 9
    ev('intake', 'emails-arrived', 'patricia-johnson', 'Patricia Johnson', 'August 9, 2026 at 9:10 AM', 'Home health referral PDF', 'resolved'),
    ev('intake', 'extracted', 'patricia-johnson', 'Patricia Johnson', 'August 9, 2026 at 9:14 AM', 'Canonical referral extracted', 'resolved'),
    ev('intake', 'approved-rejected', 'patricia-johnson', 'Patricia Johnson', 'August 9, 2026 at 11:02 AM', 'Approved', 'resolved'),
    ev('intake', 'destination-gated', 'patricia-johnson', 'Patricia Johnson', 'August 9, 2026 at 11:02 AM', 'Authorized for handoff', 'resolved'),

    ev('intake', 'emails-arrived', 'robert-williams', 'Robert Williams', 'August 9, 2026 at 3:22 PM', 'Clinic referral email', 'resolved'),
    ev('intake', 'extracted', 'robert-williams', 'Robert Williams', 'August 9, 2026 at 3:26 PM', 'Canonical referral extracted', 'resolved'),
    ev('intake', 'needs-information', 'robert-williams', 'Robert Williams', 'August 9, 2026 at 3:26 PM', 'Phone and address incomplete', 'open', 'Waiting 1d'),
    ev('intake', 'awaiting-approval', 'robert-williams', 'Robert Williams', 'August 9, 2026 at 3:27 PM', 'Review sent for missing contact fields', 'open', 'Waiting 1d'),

    // Aug 8
    ev('intake', 'emails-arrived', 'irene-cho', 'Irene Cho', 'August 8, 2026 at 10:18 AM', 'Wound clinic packet', 'resolved'),
    ev('intake', 'extracted', 'irene-cho', 'Irene Cho', 'August 8, 2026 at 10:22 AM', 'Canonical referral extracted', 'resolved'),
    ev('intake', 'approved-rejected', 'irene-cho', 'Irene Cho', 'August 8, 2026 at 4:05 PM', 'Approved', 'resolved'),
    ev('intake', 'destination-gated', 'irene-cho', 'Irene Cho', 'August 8, 2026 at 4:05 PM', 'Authorized for handoff', 'resolved'),

    ev('intake', 'emails-arrived', 'frank-owens', 'Frank Owens', 'August 8, 2026 at 2:11 PM', 'Hospice partner referral', 'resolved'),
    ev('intake', 'extracted', 'frank-owens', 'Frank Owens', 'August 8, 2026 at 2:15 PM', 'Canonical referral extracted', 'resolved'),
    ev('intake', 'approved-rejected', 'frank-owens', 'Frank Owens', 'August 8, 2026 at 5:40 PM', 'Rejected · not a wound-care candidate', 'resolved'),
  ],
}
