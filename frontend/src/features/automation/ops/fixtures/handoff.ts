import type { StageOpsFixture } from '../types'
import { ev } from './event'

export const HANDOFF_OPS_FIXTURE: StageOpsFixture = {
  stageId: 'handoff',
  events: [
    ev('handoff', 'plans-loaded', 'maria-alvarez', 'Maria Alvarez', 'August 10, 2026 at 10:05 AM', 'Approved intake plan locked', 'resolved'),
    ev('handoff', 'monday-created', 'maria-alvarez', 'Maria Alvarez', 'August 10, 2026 at 10:07 AM', 'Master Sheet item created', 'resolved'),
    ev('handoff', 'drk-prepared', 'maria-alvarez', 'Maria Alvarez', 'August 10, 2026 at 10:09 AM', 'DRK chart draft ready for assisted entry', 'open', 'Waiting 7h'),
    ev('handoff', 'destinations-linked', 'maria-alvarez', 'Maria Alvarez', 'August 10, 2026 at 10:09 AM', 'Monday ID linked · DRK pending', 'open', 'Waiting 7h'),

    ev('handoff', 'plans-loaded', 'james-carter', 'James Carter', 'August 10, 2026 at 9:40 AM', 'Approved intake plan locked', 'resolved'),
    ev('handoff', 'agency-unresolved', 'james-carter', 'James Carter', 'August 10, 2026 at 9:42 AM', 'Two Accounts matches · relation withheld', 'open', 'Waiting 8h'),
    ev('handoff', 'handoff-verified', 'james-carter', 'James Carter', 'August 10, 2026 at 9:42 AM', 'Partial failure · agency relation blocked', 'open', 'Waiting 8h'),

    ev('handoff', 'plans-loaded', 'linda-nguyen', 'Linda Nguyen', 'August 10, 2026 at 11:15 AM', 'Approved intake plan locked', 'resolved'),
    ev('handoff', 'monday-created', 'linda-nguyen', 'Linda Nguyen', 'August 10, 2026 at 11:17 AM', 'Master Sheet item created', 'resolved'),
    ev('handoff', 'drk-prepared', 'linda-nguyen', 'Linda Nguyen', 'August 10, 2026 at 11:20 AM', 'DRK Create Patient prepared', 'open', 'Waiting 6h'),

    ev('handoff', 'plans-loaded', 'patricia-johnson', 'Patricia Johnson', 'August 9, 2026 at 11:10 AM', 'Approved intake plan locked', 'resolved'),
    ev('handoff', 'monday-created', 'patricia-johnson', 'Patricia Johnson', 'August 9, 2026 at 11:12 AM', 'Master Sheet item created', 'resolved'),
    ev('handoff', 'drk-prepared', 'patricia-johnson', 'Patricia Johnson', 'August 9, 2026 at 11:18 AM', 'DRK chart entered', 'resolved'),
    ev('handoff', 'destinations-linked', 'patricia-johnson', 'Patricia Johnson', 'August 9, 2026 at 11:19 AM', 'Monday and DRK linked', 'resolved'),
    ev('handoff', 'handoff-verified', 'patricia-johnson', 'Patricia Johnson', 'August 9, 2026 at 11:20 AM', 'Handoff verified', 'resolved'),

    ev('handoff', 'plans-loaded', 'thomas-reed', 'Thomas Reed', 'August 10, 2026 at 2:45 PM', 'Approved intake plan locked', 'resolved'),
    ev('handoff', 'monday-created', 'thomas-reed', 'Thomas Reed', 'August 10, 2026 at 2:47 PM', 'Master Sheet item created', 'resolved'),
    ev('handoff', 'drk-prepared', 'thomas-reed', 'Thomas Reed', 'August 10, 2026 at 2:52 PM', 'DRK chart entered', 'resolved'),
    ev('handoff', 'destinations-linked', 'thomas-reed', 'Thomas Reed', 'August 10, 2026 at 2:53 PM', 'Identifiers linked', 'resolved'),
    ev('handoff', 'handoff-verified', 'thomas-reed', 'Thomas Reed', 'August 10, 2026 at 2:54 PM', 'Handoff verified', 'resolved'),

    ev('handoff', 'plans-loaded', 'irene-cho', 'Irene Cho', 'August 8, 2026 at 4:20 PM', 'Approved intake plan locked', 'resolved'),
    ev('handoff', 'monday-created', 'irene-cho', 'Irene Cho', 'August 8, 2026 at 4:22 PM', 'Master Sheet item created', 'resolved'),
    ev('handoff', 'agency-unresolved', 'irene-cho', 'Irene Cho', 'August 8, 2026 at 4:23 PM', 'Zero agency matches', 'open', 'Waiting 2d'),
    ev('handoff', 'handoff-verified', 'irene-cho', 'Irene Cho', 'August 8, 2026 at 4:23 PM', 'Pending agency resolution', 'open', 'Waiting 2d'),

    ev('handoff', 'plans-loaded', 'helen-park', 'Helen Park', 'August 9, 2026 at 3:05 PM', 'Approved intake plan locked', 'resolved'),
    ev('handoff', 'monday-created', 'helen-park', 'Helen Park', 'August 9, 2026 at 3:07 PM', 'Master Sheet item created', 'resolved'),
    ev('handoff', 'drk-prepared', 'helen-park', 'Helen Park', 'August 9, 2026 at 3:12 PM', 'DRK chart entered', 'resolved'),
    ev('handoff', 'destinations-linked', 'helen-park', 'Helen Park', 'August 9, 2026 at 3:13 PM', 'Linked', 'resolved'),
    ev('handoff', 'handoff-verified', 'helen-park', 'Helen Park', 'August 9, 2026 at 3:14 PM', 'Verified', 'resolved'),
  ],
}
