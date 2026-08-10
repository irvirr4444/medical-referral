import type { StageOpsFixture } from '../types'
import { ev } from './event'

export const END_OF_DAY_OPS_FIXTURE: StageOpsFixture = {
  stageId: 'end-of-day',
  events: [
    ev('end-of-day', 'due-reviewed', 'anita-gomez', 'Anita Gomez', 'August 10, 2026 at 5:00 PM', 'Due for scheduling review at cutoff', 'resolved'),
    ev('end-of-day', 'scheduled-consistent', 'anita-gomez', 'Anita Gomez', 'August 10, 2026 at 5:01 PM', 'Scheduled Yes · complete Yes · date Aug 13', 'resolved'),

    ev('end-of-day', 'due-reviewed', 'frank-owens', 'Frank Owens', 'August 10, 2026 at 5:00 PM', 'Due for scheduling review', 'resolved'),
    ev('end-of-day', 'inconsistencies', 'frank-owens', 'Frank Owens', 'August 10, 2026 at 5:01 PM', 'Appointment date present · scheduled status blank', 'open', 'Opened today'),
    ev('end-of-day', 'exceptions-opened', 'frank-owens', 'Frank Owens', 'August 10, 2026 at 5:02 PM', 'Inconsistency exception opened', 'open', 'Opened today'),
    ev('end-of-day', 'management-notified', 'frank-owens', 'Frank Owens', 'August 10, 2026 at 5:03 PM', 'Included in management summary', 'resolved'),

    ev('end-of-day', 'due-reviewed', 'susan-park', 'Susan Park', 'August 10, 2026 at 5:00 PM', 'Due for scheduling review', 'resolved'),
    ev('end-of-day', 'scheduled-consistent', 'susan-park', 'Susan Park', 'August 10, 2026 at 5:01 PM', 'All scheduling fields agree', 'resolved'),

    ev('end-of-day', 'due-reviewed', 'george-chen', 'George Chen', 'August 10, 2026 at 5:00 PM', 'Due for scheduling review', 'resolved'),
    ev('end-of-day', 'inconsistencies', 'george-chen', 'George Chen', 'August 10, 2026 at 5:01 PM', 'Complete flag No · appointment date set', 'open', 'Opened today'),
    ev('end-of-day', 'exceptions-opened', 'george-chen', 'George Chen', 'August 10, 2026 at 5:02 PM', 'Exception opened', 'open', 'Opened today'),

    ev('end-of-day', 'due-reviewed', 'linda-nguyen', 'Linda Nguyen', 'August 9, 2026 at 5:00 PM', 'Due for scheduling review', 'resolved'),
    ev('end-of-day', 'inconsistencies', 'linda-nguyen', 'Linda Nguyen', 'August 9, 2026 at 5:01 PM', 'Indeterminate scheduling fields', 'resolved'),
    ev('end-of-day', 'exceptions-opened', 'linda-nguyen', 'Linda Nguyen', 'August 9, 2026 at 5:02 PM', 'Exception opened Aug 9', 'open', 'Waiting 1d'),
    ev('end-of-day', 'management-notified', 'linda-nguyen', 'Linda Nguyen', 'August 9, 2026 at 5:03 PM', 'Included once in summary', 'resolved'),

    ev('end-of-day', 'due-reviewed', 'maria-alvarez', 'Maria Alvarez', 'August 9, 2026 at 5:00 PM', 'Due for scheduling review', 'resolved'),
    ev('end-of-day', 'scheduled-consistent', 'maria-alvarez', 'Maria Alvarez', 'August 9, 2026 at 5:01 PM', 'Scheduled · fields agree', 'resolved'),

    ev('end-of-day', 'due-reviewed', 'nancy-liu', 'Nancy Liu', 'August 8, 2026 at 5:00 PM', 'Due for scheduling review', 'resolved'),
    ev('end-of-day', 'scheduled-consistent', 'nancy-liu', 'Nancy Liu', 'August 8, 2026 at 5:01 PM', 'Consistent', 'resolved'),
    ev('end-of-day', 'management-notified', 'nancy-liu', 'Nancy Liu', 'August 8, 2026 at 5:03 PM', 'Excluded from exception summary', 'resolved'),

    ev('end-of-day', 'due-reviewed', 'helen-park', 'Helen Park', 'August 8, 2026 at 5:04 PM', 'Due for scheduling review', 'resolved'),
    ev('end-of-day', 'scheduled-consistent', 'helen-park', 'Helen Park', 'August 8, 2026 at 5:05 PM', 'Appointment Aug 12 · fields agree', 'resolved'),

    ev('end-of-day', 'due-reviewed', 'robert-williams', 'Robert Williams', 'August 10, 2026 at 5:04 PM', 'Due for scheduling review at cutoff', 'resolved'),
    ev('end-of-day', 'inconsistencies', 'robert-williams', 'Robert Williams', 'August 10, 2026 at 5:05 PM', 'Scheduled Yes · complete blank', 'open', 'Opened today'),
    ev('end-of-day', 'exceptions-opened', 'robert-williams', 'Robert Williams', 'August 10, 2026 at 5:06 PM', 'Inconsistency exception opened', 'open', 'Opened today'),
    ev('end-of-day', 'management-notified', 'robert-williams', 'Robert Williams', 'August 10, 2026 at 5:07 PM', 'Included in evening management digest', 'resolved'),
  ],
}
