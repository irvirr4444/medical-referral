import type { StageOpsFixture } from '../types'
import { ev } from './event'

export const END_OF_DAY_OPS_FIXTURE: StageOpsFixture = {
  stageId: 'end-of-day',
  events: [
    ev('end-of-day', 'due-reviewed', 'anita-gomez', 'Anita Gomez', 'August 12, 2026 at 5:00 PM', 'Due for scheduling review at cutoff', 'resolved'),
    ev('end-of-day', 'scheduled-consistent', 'anita-gomez', 'Anita Gomez', 'August 12, 2026 at 5:01 PM', 'Scheduled · Monday fields agree', 'resolved'),

    ev('end-of-day', 'due-reviewed', 'susan-park', 'Susan Park', 'August 12, 2026 at 5:00 PM', 'Due for scheduling review', 'resolved'),
    ev('end-of-day', 'scheduled-consistent', 'susan-park', 'Susan Park', 'August 12, 2026 at 5:01 PM', 'Scheduled · Monday fields agree', 'resolved'),

    ev('end-of-day', 'due-reviewed', 'nancy-liu', 'Nancy Liu', 'August 12, 2026 at 5:00 PM', 'Due for scheduling review', 'resolved'),
    ev('end-of-day', 'scheduled-consistent', 'nancy-liu', 'Nancy Liu', 'August 12, 2026 at 5:01 PM', 'Scheduled · Monday fields agree', 'resolved'),

    ev('end-of-day', 'due-reviewed', 'helen-park', 'Helen Park', 'August 12, 2026 at 5:00 PM', 'Due for scheduling review', 'resolved'),
    ev('end-of-day', 'scheduled-consistent', 'helen-park', 'Helen Park', 'August 12, 2026 at 5:01 PM', 'Scheduled · Monday fields agree', 'resolved'),

    ev('end-of-day', 'due-reviewed', 'maria-alvarez', 'Maria Alvarez', 'August 12, 2026 at 5:00 PM', 'Due · provider selected 36 hours ago', 'resolved'),
    ev('end-of-day', 'unscheduled-overdue', 'maria-alvarez', 'Maria Alvarez', 'August 12, 2026 at 5:01 PM', 'Not scheduled · CM notified on Teams', 'open', 'Opened today'),

    ev('end-of-day', 'due-reviewed', 'thomas-reed', 'Thomas Reed', 'August 12, 2026 at 5:00 PM', 'Due · provider selected 18 hours ago', 'resolved'),
    ev('end-of-day', 'unscheduled-overdue', 'thomas-reed', 'Thomas Reed', 'August 12, 2026 at 5:01 PM', 'Not scheduled · under 24 hours', 'open', 'Opened today'),

    ev('end-of-day', 'due-reviewed', 'james-carter', 'James Carter', 'August 12, 2026 at 5:00 PM', 'Due · provider selected 56 hours ago', 'resolved'),
    ev('end-of-day', 'unscheduled-overdue', 'james-carter', 'James Carter', 'August 12, 2026 at 5:01 PM', 'Not scheduled · Monday fields blank', 'open', 'Opened today'),

    ev('end-of-day', 'due-reviewed', 'frank-owens', 'Frank Owens', 'August 12, 2026 at 5:00 PM', 'Due · provider selected 51 hours ago', 'resolved'),
    ev('end-of-day', 'unscheduled-overdue', 'frank-owens', 'Frank Owens', 'August 12, 2026 at 5:01 PM', 'Not scheduled · appointment date only', 'open', 'Opened today'),
    ev('end-of-day', 'exceptions-opened', 'frank-owens', 'Frank Owens', 'August 12, 2026 at 5:02 PM', 'CM follow-up sent on Teams', 'open', 'Opened today'),

    ev('end-of-day', 'due-reviewed', 'george-chen', 'George Chen', 'August 12, 2026 at 5:00 PM', 'Due · provider selected 54 hours ago', 'resolved'),
    ev('end-of-day', 'unscheduled-overdue', 'george-chen', 'George Chen', 'August 12, 2026 at 5:01 PM', 'Not scheduled · complete flag No', 'open', 'Opened today'),
    ev('end-of-day', 'exceptions-opened', 'george-chen', 'George Chen', 'August 12, 2026 at 5:02 PM', 'CM follow-up sent on Teams', 'open', 'Opened today'),

    ev('end-of-day', 'due-reviewed', 'linda-nguyen', 'Linda Nguyen', 'August 12, 2026 at 5:00 PM', 'Due · provider selected 73 hours ago', 'resolved'),
    ev('end-of-day', 'unscheduled-overdue', 'linda-nguyen', 'Linda Nguyen', 'August 12, 2026 at 5:01 PM', 'Not scheduled · Monday fields blank', 'resolved'),
    ev('end-of-day', 'exceptions-opened', 'linda-nguyen', 'Linda Nguyen', 'August 12, 2026 at 5:02 PM', 'CM follow-up sent on Teams', 'open', 'Waiting 1d'),
    ev('end-of-day', 'management-notified', 'linda-nguyen', 'Linda Nguyen', 'August 12, 2026 at 5:03 PM', 'Escalated to management · still unresolved', 'open', 'Waiting 1d'),
  ],
}
