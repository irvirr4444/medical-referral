import type { StageOpsFixture } from '../types'
import { ev } from './event'

export const WEEKLY_OPS_FIXTURE: StageOpsFixture = {
  stageId: 'weekly',
  events: [
    ev('weekly', 'patients-checked', 'gloria-bennett', 'Gloria Bennett', 'August 10, 2026 at 6:00 PM', 'Active linked patient checked', 'resolved'),
    ev('weekly', 'visit-seen', 'gloria-bennett', 'Gloria Bennett', 'August 10, 2026 at 6:01 PM', 'New DRK visit recorded as Seen', 'resolved'),

    ev('weekly', 'patients-checked', 'arthur-kim', 'Arthur Kim', 'August 10, 2026 at 6:00 PM', 'Active linked patient checked', 'resolved'),
    ev('weekly', 'on-hold', 'arthur-kim', 'Arthur Kim', 'August 10, 2026 at 6:02 PM', 'Hospitalization hold recorded', 'open', 'Opened today'),
    ev('weekly', 'weekly-exceptions', 'arthur-kim', 'Arthur Kim', 'August 10, 2026 at 6:03 PM', 'Hold-tracking exception opened', 'open', 'Opened today'),

    ev('weekly', 'patients-checked', 'margaret-ellis', 'Margaret Ellis', 'August 10, 2026 at 6:00 PM', 'Active linked patient checked', 'resolved'),
    ev('weekly', 'not-seen', 'margaret-ellis', 'Margaret Ellis', 'August 10, 2026 at 6:01 PM', 'Not Seen count incremented to 2', 'open', 'Opened today'),
    ev('weekly', 'review-required', 'margaret-ellis', 'Margaret Ellis', 'August 10, 2026 at 6:02 PM', 'Approach review threshold', 'open', 'Opened today'),

    ev('weekly', 'patients-checked', 'walter-grant', 'Walter Grant', 'August 10, 2026 at 6:00 PM', 'Active linked patient checked', 'resolved'),
    ev('weekly', 'not-seen', 'walter-grant', 'Walter Grant', 'August 10, 2026 at 6:01 PM', 'Not Seen count incremented to 3', 'open', 'Opened today'),
    ev('weekly', 'review-required', 'walter-grant', 'Walter Grant', 'August 10, 2026 at 6:02 PM', 'Review required', 'open', 'Opened today'),
    ev('weekly', 'weekly-exceptions', 'walter-grant', 'Walter Grant', 'August 10, 2026 at 6:03 PM', 'Not-seen exception opened', 'open', 'Opened today'),

    ev('weekly', 'patients-checked', 'dorothy-lane', 'Dorothy Lane', 'August 9, 2026 at 6:00 PM', 'Active linked patient checked', 'resolved'),
    ev('weekly', 'visit-seen', 'dorothy-lane', 'Dorothy Lane', 'August 9, 2026 at 6:01 PM', 'Patient seen', 'resolved'),

    ev('weekly', 'patients-checked', 'helen-park', 'Helen Park', 'August 9, 2026 at 6:04 PM', 'Active linked patient checked', 'resolved'),
    ev('weekly', 'visit-seen', 'helen-park', 'Helen Park', 'August 9, 2026 at 6:05 PM', 'New visit_seen event', 'resolved'),

    ev('weekly', 'patients-checked', 'patricia-johnson', 'Patricia Johnson', 'August 8, 2026 at 6:00 PM', 'Active linked patient checked', 'resolved'),
    ev('weekly', 'not-seen', 'patricia-johnson', 'Patricia Johnson', 'August 8, 2026 at 6:01 PM', 'Not Seen count = 1', 'resolved'),

    ev('weekly', 'patients-checked', 'james-carter', 'James Carter', 'August 8, 2026 at 6:02 PM', 'Active linked patient checked', 'resolved'),
    ev('weekly', 'visit-seen', 'james-carter', 'James Carter', 'August 8, 2026 at 6:03 PM', 'Patient expired', 'open', 'Opened today'),
    ev('weekly', 'weekly-exceptions', 'james-carter', 'James Carter', 'August 8, 2026 at 6:04 PM', 'Expired · pending DC approval', 'open', 'Opened today'),

    ev('weekly', 'patients-checked', 'nancy-liu', 'Nancy Liu', 'August 10, 2026 at 6:04 PM', 'Active linked patient checked', 'resolved'),
    ev('weekly', 'visit-seen', 'nancy-liu', 'Nancy Liu', 'August 10, 2026 at 6:05 PM', 'Wound healed', 'open', 'Opened today'),
    ev('weekly', 'weekly-exceptions', 'nancy-liu', 'Nancy Liu', 'August 10, 2026 at 6:06 PM', 'QA discharge path pending', 'open', 'Opened today'),

    ev('weekly', 'patients-checked', 'linda-nguyen', 'Linda Nguyen', 'August 9, 2026 at 6:06 PM', 'Active linked patient checked', 'resolved'),
    ev('weekly', 'on-hold', 'linda-nguyen', 'Linda Nguyen', 'August 9, 2026 at 6:07 PM', 'Facility hold · monitoring paused', 'open', 'Waiting 1d'),
    ev('weekly', 'weekly-exceptions', 'linda-nguyen', 'Linda Nguyen', 'August 9, 2026 at 6:08 PM', 'Hold exception remains open', 'open', 'Waiting 1d'),
  ],
}
