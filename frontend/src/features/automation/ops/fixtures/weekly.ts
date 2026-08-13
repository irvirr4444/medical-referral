import type { StageOpsFixture } from '../types'
import { ev } from './event'

export const WEEKLY_OPS_FIXTURE: StageOpsFixture = {
  stageId: 'weekly',
  events: [
    ev('weekly', 'patients-checked', 'gloria-bennett', 'Gloria Bennett', 'August 10, 2026 at 6:00 PM', 'Active linked patient checked', 'resolved'),
    ev('weekly', 'visit-seen', 'gloria-bennett', 'Gloria Bennett', 'August 10, 2026 at 6:01 PM', 'New DRK visit recorded as Seen', 'resolved'),

    ev('weekly', 'patients-checked', 'arthur-kim', 'Arthur Kim', 'August 10, 2026 at 6:00 PM', 'Active linked patient checked', 'resolved'),
    ev('weekly', 'on-hold', 'arthur-kim', 'Arthur Kim', 'August 10, 2026 at 6:02 PM', 'Hospitalization hold recorded', 'open', 'Opened today'),
    ev('weekly', 'weekly-exceptions', 'arthur-kim', 'Arthur Kim', 'August 10, 2026 at 6:03 PM', 'Hold-team follow-up prepared', 'open', 'Opened today'),

    ev('weekly', 'patients-checked', 'margaret-ellis', 'Margaret Ellis', 'August 10, 2026 at 6:00 PM', 'Active linked patient checked', 'resolved'),
    ev('weekly', 'not-seen', 'margaret-ellis', 'Margaret Ellis', 'August 10, 2026 at 6:01 PM', 'Not Seen count incremented to 2', 'open', 'Opened today'),
    ev('weekly', 'review-required', 'margaret-ellis', 'Margaret Ellis', 'August 10, 2026 at 6:02 PM', 'Approach review threshold', 'open', 'Opened today'),

    ev('weekly', 'patients-checked', 'walter-grant', 'Walter Grant', 'August 10, 2026 at 6:00 PM', 'Active linked patient checked', 'resolved'),
    ev('weekly', 'not-seen', 'walter-grant', 'Walter Grant', 'August 10, 2026 at 6:01 PM', 'Not Seen count incremented to 3', 'open', 'Opened today'),
    ev('weekly', 'review-required', 'walter-grant', 'Walter Grant', 'August 10, 2026 at 6:02 PM', 'Discharge review required', 'open', 'Opened today'),
    ev('weekly', 'weekly-exceptions', 'walter-grant', 'Walter Grant', 'August 10, 2026 at 6:03 PM', 'Management review action prepared', 'open', 'Opened today'),

    ev('weekly', 'patients-checked', 'dorothy-lane', 'Dorothy Lane', 'August 9, 2026 at 6:00 PM', 'Active linked patient checked', 'resolved'),
    ev('weekly', 'visit-seen', 'dorothy-lane', 'Dorothy Lane', 'August 9, 2026 at 6:01 PM', 'Patient seen', 'resolved'),

    ev('weekly', 'patients-checked', 'helen-park', 'Helen Park', 'August 9, 2026 at 6:04 PM', 'Active linked patient checked', 'resolved'),
    ev('weekly', 'visit-seen', 'helen-park', 'Helen Park', 'August 9, 2026 at 6:05 PM', 'New visit_seen event', 'resolved'),

    ev('weekly', 'patients-checked', 'patricia-johnson', 'Patricia Johnson', 'August 8, 2026 at 6:00 PM', 'Active linked patient checked', 'resolved'),
    ev('weekly', 'not-seen', 'patricia-johnson', 'Patricia Johnson', 'August 8, 2026 at 6:01 PM', 'Not Seen count = 1', 'resolved'),

    ev('weekly', 'patients-checked', 'james-carter', 'James Carter', 'August 8, 2026 at 6:02 PM', 'Active linked patient checked', 'resolved'),
    ev('weekly', 'visit-seen', 'james-carter', 'James Carter', 'August 8, 2026 at 6:03 PM', 'Patient expired', 'open', 'Opened today'),
    ev('weekly', 'weekly-exceptions', 'james-carter', 'James Carter', 'August 8, 2026 at 6:04 PM', 'Expired · pending DC approval', 'open', 'Opened today'),

    ev('weekly', 'patients-checked', 'maria-alvarez', 'Maria Alvarez', 'August 10, 2026 at 5:38 PM', 'Active linked patient checked', 'resolved'),
    ev('weekly', 'visit-seen', 'maria-alvarez', 'Maria Alvarez', 'August 10, 2026 at 5:40 PM', 'Patient expired', 'open', 'Opened today'),
    ev('weekly', 'weekly-exceptions', 'maria-alvarez', 'Maria Alvarez', 'August 10, 2026 at 5:41 PM', 'Expired · pending DC approval', 'open', 'Opened today'),

    ev('weekly', 'patients-checked', 'thomas-reed', 'Thomas Reed', 'August 9, 2026 at 5:18 PM', 'Active linked patient checked', 'resolved'),
    ev('weekly', 'visit-seen', 'thomas-reed', 'Thomas Reed', 'August 9, 2026 at 5:20 PM', 'Patient expired', 'open', 'Opened today'),
    ev('weekly', 'weekly-exceptions', 'thomas-reed', 'Thomas Reed', 'August 9, 2026 at 5:21 PM', 'Expired · pending DC approval', 'open', 'Opened today'),

    ev('weekly', 'patients-checked', 'marcus-feldman', 'Marcus Feldman', 'August 10, 2026 at 4:52 PM', 'Active linked patient checked', 'resolved'),
    ev('weekly', 'visit-seen', 'marcus-feldman', 'Marcus Feldman', 'August 10, 2026 at 4:55 PM', 'Patient expired', 'open', 'Opened today'),
    ev('weekly', 'weekly-exceptions', 'marcus-feldman', 'Marcus Feldman', 'August 10, 2026 at 4:56 PM', 'Expired · pending DC approval', 'open', 'Opened today'),

    ev('weekly', 'patients-checked', 'nancy-liu', 'Nancy Liu', 'August 10, 2026 at 6:04 PM', 'Active linked patient checked', 'resolved'),
    ev('weekly', 'visit-seen', 'nancy-liu', 'Nancy Liu', 'August 10, 2026 at 6:05 PM', 'Wound healed', 'open', 'Opened today'),
    ev('weekly', 'weekly-exceptions', 'nancy-liu', 'Nancy Liu', 'August 10, 2026 at 6:06 PM', 'QA discharge path pending', 'open', 'Opened today'),

    ev('weekly', 'patients-checked', 'irene-cho', 'Irene Cho', 'August 10, 2026 at 5:10 PM', 'Active linked patient checked', 'resolved'),
    ev('weekly', 'visit-seen', 'irene-cho', 'Irene Cho', 'August 10, 2026 at 5:12 PM', 'Wound healed', 'open', 'Opened today'),
    ev('weekly', 'weekly-exceptions', 'irene-cho', 'Irene Cho', 'August 10, 2026 at 5:13 PM', 'QA discharge path pending', 'open', 'Opened today'),

    ev('weekly', 'patients-checked', 'betty-hayes', 'Betty Hayes', 'August 9, 2026 at 4:45 PM', 'Active linked patient checked', 'resolved'),
    ev('weekly', 'visit-seen', 'betty-hayes', 'Betty Hayes', 'August 9, 2026 at 4:48 PM', 'Wound healed', 'open', 'Opened today'),
    ev('weekly', 'weekly-exceptions', 'betty-hayes', 'Betty Hayes', 'August 9, 2026 at 4:49 PM', 'QA discharge path pending', 'open', 'Opened today'),

    ev('weekly', 'patients-checked', 'david-ruiz', 'David Ruiz', 'August 10, 2026 at 3:28 PM', 'Active linked patient checked', 'resolved'),
    ev('weekly', 'visit-seen', 'david-ruiz', 'David Ruiz', 'August 10, 2026 at 3:30 PM', 'Wound healed', 'open', 'Opened today'),
    ev('weekly', 'weekly-exceptions', 'david-ruiz', 'David Ruiz', 'August 10, 2026 at 3:31 PM', 'QA discharge path pending', 'open', 'Opened today'),

    ev('weekly', 'patients-checked', 'linda-nguyen', 'Linda Nguyen', 'August 9, 2026 at 6:06 PM', 'Active linked patient checked', 'resolved'),
    ev('weekly', 'on-hold', 'linda-nguyen', 'Linda Nguyen', 'August 9, 2026 at 6:07 PM', 'Facility hold · monitoring paused', 'open', 'Waiting 1d'),
    ev('weekly', 'weekly-exceptions', 'linda-nguyen', 'Linda Nguyen', 'August 9, 2026 at 6:08 PM', 'Hold exception remains open', 'open', 'Waiting 1d'),

    ev('weekly', 'patients-checked', 'george-chen', 'George Chen', 'August 10, 2026 at 5:02 PM', 'Active linked patient checked', 'resolved'),
    ev('weekly', 'on-hold', 'george-chen', 'George Chen', 'August 10, 2026 at 5:05 PM', 'Vacation hold recorded', 'open', 'Opened today'),
    ev('weekly', 'weekly-exceptions', 'george-chen', 'George Chen', 'August 10, 2026 at 5:06 PM', 'Hold-tracking exception opened', 'open', 'Opened today'),

    ev('weekly', 'patients-checked', 'rodriguez-anita', 'Anita Rodriguez', 'August 9, 2026 at 4:18 PM', 'Active linked patient checked', 'resolved'),
    ev('weekly', 'on-hold', 'rodriguez-anita', 'Anita Rodriguez', 'August 9, 2026 at 4:20 PM', 'Patient request hold recorded', 'open', 'Waiting 1d'),
    ev('weekly', 'weekly-exceptions', 'rodriguez-anita', 'Anita Rodriguez', 'August 9, 2026 at 4:21 PM', 'Hold exception remains open', 'open', 'Waiting 1d'),

    ev('weekly', 'patients-checked', 'sardina-frank', 'Frank Sardina', 'August 8, 2026 at 5:42 PM', 'Active linked patient checked', 'resolved'),
    ev('weekly', 'on-hold', 'sardina-frank', 'Frank Sardina', 'August 8, 2026 at 5:45 PM', 'Family request hold recorded', 'open', 'Waiting 2d'),
    ev('weekly', 'weekly-exceptions', 'sardina-frank', 'Frank Sardina', 'August 8, 2026 at 5:46 PM', 'Hold exception remains open', 'open', 'Waiting 2d'),
  ],
}
