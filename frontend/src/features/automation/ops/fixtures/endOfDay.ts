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

    ev('end-of-day', 'due-reviewed', 'patricia-johnson', 'Patricia Johnson', 'August 11, 2026 at 5:18 PM', 'Due · provider selected 40 hours ago', 'resolved'),
    ev('end-of-day', 'scheduled-consistent', 'patricia-johnson', 'Patricia Johnson', 'August 11, 2026 at 5:20 PM', 'Scheduled after CM follow-up', 'resolved'),
    ev('end-of-day', 'exceptions-opened', 'patricia-johnson', 'Patricia Johnson', 'August 11, 2026 at 5:19 PM', 'CM follow-up sent on Teams', 'resolved'),

    ev('end-of-day', 'due-reviewed', 'irene-cho', 'Irene Cho', 'August 12, 2026 at 5:14 PM', 'Due · provider selected 32 hours ago', 'resolved'),
    ev('end-of-day', 'scheduled-consistent', 'irene-cho', 'Irene Cho', 'August 12, 2026 at 5:16 PM', 'Scheduled after CM follow-up', 'resolved'),
    ev('end-of-day', 'exceptions-opened', 'irene-cho', 'Irene Cho', 'August 12, 2026 at 5:15 PM', 'CM follow-up sent on Teams', 'resolved'),

    ev('end-of-day', 'due-reviewed', 'arthur-kim', 'Arthur Kim', 'August 11, 2026 at 4:36 PM', 'Due · provider selected 52 hours ago', 'resolved'),
    ev('end-of-day', 'scheduled-consistent', 'arthur-kim', 'Arthur Kim', 'August 11, 2026 at 4:42 PM', 'Scheduled after management escalation', 'resolved'),
    ev('end-of-day', 'exceptions-opened', 'arthur-kim', 'Arthur Kim', 'August 11, 2026 at 4:38 PM', 'CM follow-up sent on Teams', 'resolved'),
    ev('end-of-day', 'management-notified', 'arthur-kim', 'Arthur Kim', 'August 11, 2026 at 4:40 PM', 'Escalated to management · now scheduled', 'resolved'),

    ev('end-of-day', 'due-reviewed', 'maria-alvarez', 'Maria Alvarez', 'August 12, 2026 at 5:00 PM', 'Due · provider selected 36 hours ago', 'resolved'),
    ev('end-of-day', 'unscheduled-overdue', 'maria-alvarez', 'Maria Alvarez', 'August 12, 2026 at 5:01 PM', 'Not scheduled · CM notified on Teams', 'open', 'Opened today'),

    ev('end-of-day', 'due-reviewed', 'thomas-reed', 'Thomas Reed', 'August 12, 2026 at 5:00 PM', 'Due · provider selected 18 hours ago', 'resolved'),
    ev('end-of-day', 'unscheduled-overdue', 'thomas-reed', 'Thomas Reed', 'August 12, 2026 at 5:01 PM', 'Not scheduled · under 24 hours', 'open', 'Opened today'),

    ev('end-of-day', 'due-reviewed', 'marcus-feldman', 'Marcus Feldman', 'August 12, 2026 at 4:46 PM', 'Due · provider selected 28 hours ago', 'resolved'),
    ev('end-of-day', 'unscheduled-overdue', 'marcus-feldman', 'Marcus Feldman', 'August 12, 2026 at 4:47 PM', 'Not scheduled · CM notified on Teams', 'open', 'Opened today'),
    ev('end-of-day', 'exceptions-opened', 'marcus-feldman', 'Marcus Feldman', 'August 12, 2026 at 4:48 PM', 'CM follow-up sent on Teams', 'open', 'Opened today'),

    ev('end-of-day', 'due-reviewed', 'david-ruiz', 'David Ruiz', 'August 12, 2026 at 5:08 PM', 'Due · provider selected 41 hours ago', 'resolved'),
    ev('end-of-day', 'unscheduled-overdue', 'david-ruiz', 'David Ruiz', 'August 12, 2026 at 5:09 PM', 'Not scheduled · CM notified on Teams', 'open', 'Opened today'),
    ev('end-of-day', 'exceptions-opened', 'david-ruiz', 'David Ruiz', 'August 12, 2026 at 5:10 PM', 'CM follow-up sent on Teams', 'open', 'Opened today'),

    ev('end-of-day', 'due-reviewed', 'james-carter', 'James Carter', 'August 12, 2026 at 5:00 PM', 'Due · provider selected 56 hours ago', 'resolved'),
    ev('end-of-day', 'unscheduled-overdue', 'james-carter', 'James Carter', 'August 12, 2026 at 5:01 PM', 'Not scheduled · Monday fields blank', 'open', 'Opened today'),
    ev('end-of-day', 'exceptions-opened', 'james-carter', 'James Carter', 'August 12, 2026 at 5:02 PM', 'CM follow-up sent on Teams', 'open', 'Opened today'),

    ev('end-of-day', 'due-reviewed', 'frank-owens', 'Frank Owens', 'August 12, 2026 at 5:00 PM', 'Due · provider selected 51 hours ago', 'resolved'),
    ev('end-of-day', 'unscheduled-overdue', 'frank-owens', 'Frank Owens', 'August 12, 2026 at 5:01 PM', 'Not scheduled · appointment date only', 'open', 'Opened today'),
    ev('end-of-day', 'exceptions-opened', 'frank-owens', 'Frank Owens', 'August 12, 2026 at 5:02 PM', 'CM follow-up sent on Teams', 'open', 'Opened today'),

    ev('end-of-day', 'due-reviewed', 'george-chen', 'George Chen', 'August 12, 2026 at 5:00 PM', 'Due · provider selected 54 hours ago', 'resolved'),
    ev('end-of-day', 'unscheduled-overdue', 'george-chen', 'George Chen', 'August 12, 2026 at 5:01 PM', 'Not scheduled · complete flag No', 'open', 'Opened today'),
    ev('end-of-day', 'exceptions-opened', 'george-chen', 'George Chen', 'August 12, 2026 at 5:02 PM', 'CM follow-up sent on Teams', 'open', 'Opened today'),

    ev('end-of-day', 'due-reviewed', 'betty-hayes', 'Betty Hayes', 'August 11, 2026 at 6:16 PM', 'Due · provider selected 62 hours ago', 'resolved'),
    ev('end-of-day', 'unscheduled-overdue', 'betty-hayes', 'Betty Hayes', 'August 11, 2026 at 6:18 PM', 'Not scheduled · Monday fields blank', 'open', 'Waiting 1d'),
    ev('end-of-day', 'exceptions-opened', 'betty-hayes', 'Betty Hayes', 'August 11, 2026 at 6:19 PM', 'CM follow-up sent on Teams', 'open', 'Waiting 1d'),
    ev('end-of-day', 'management-notified', 'betty-hayes', 'Betty Hayes', 'August 11, 2026 at 6:20 PM', 'Escalated to management · still unresolved', 'open', 'Waiting 1d'),

    ev('end-of-day', 'due-reviewed', 'walter-grant', 'Walter Grant', 'August 11, 2026 at 5:06 PM', 'Due · provider selected 80 hours ago', 'resolved'),
    ev('end-of-day', 'unscheduled-overdue', 'walter-grant', 'Walter Grant', 'August 11, 2026 at 5:08 PM', 'Not scheduled · appointment date only', 'open', 'Waiting 1d'),
    ev('end-of-day', 'exceptions-opened', 'walter-grant', 'Walter Grant', 'August 11, 2026 at 5:09 PM', 'CM follow-up sent on Teams', 'open', 'Waiting 1d'),
    ev('end-of-day', 'management-notified', 'walter-grant', 'Walter Grant', 'August 11, 2026 at 5:10 PM', 'Escalated to management · still unresolved', 'open', 'Waiting 1d'),

    ev('end-of-day', 'due-reviewed', 'gloria-bennett', 'Gloria Bennett', 'August 11, 2026 at 5:40 PM', 'Due · provider selected 58 hours ago', 'resolved'),
    ev('end-of-day', 'unscheduled-overdue', 'gloria-bennett', 'Gloria Bennett', 'August 11, 2026 at 5:41 PM', 'Not scheduled · Monday fields blank', 'open', 'Waiting 1d'),
    ev('end-of-day', 'exceptions-opened', 'gloria-bennett', 'Gloria Bennett', 'August 11, 2026 at 5:41 PM', 'CM follow-up sent on Teams', 'open', 'Waiting 1d'),
    ev('end-of-day', 'management-notified', 'gloria-bennett', 'Gloria Bennett', 'August 11, 2026 at 5:42 PM', 'Escalated to management · still unresolved', 'open', 'Waiting 1d'),

    ev('end-of-day', 'due-reviewed', 'dorothy-lane', 'Dorothy Lane', 'August 11, 2026 at 3:28 PM', 'Due · provider selected 67 hours ago', 'resolved'),
    ev('end-of-day', 'unscheduled-overdue', 'dorothy-lane', 'Dorothy Lane', 'August 11, 2026 at 3:29 PM', 'Not scheduled · appointment date only', 'open', 'Waiting 1d'),
    ev('end-of-day', 'exceptions-opened', 'dorothy-lane', 'Dorothy Lane', 'August 11, 2026 at 3:29 PM', 'CM follow-up sent on Teams', 'open', 'Waiting 1d'),
    ev('end-of-day', 'management-notified', 'dorothy-lane', 'Dorothy Lane', 'August 11, 2026 at 3:30 PM', 'Escalated to management · still unresolved', 'open', 'Waiting 1d'),

    ev('end-of-day', 'due-reviewed', 'margaret-ellis', 'Margaret Ellis', 'August 11, 2026 at 7:12 PM', 'Due · provider selected 71 hours ago', 'resolved'),
    ev('end-of-day', 'unscheduled-overdue', 'margaret-ellis', 'Margaret Ellis', 'August 11, 2026 at 7:13 PM', 'Not scheduled · Monday fields blank', 'open', 'Waiting 1d'),
    ev('end-of-day', 'exceptions-opened', 'margaret-ellis', 'Margaret Ellis', 'August 11, 2026 at 7:13 PM', 'CM follow-up sent on Teams', 'open', 'Waiting 1d'),
    ev('end-of-day', 'management-notified', 'margaret-ellis', 'Margaret Ellis', 'August 11, 2026 at 7:14 PM', 'Escalated to management · still unresolved', 'open', 'Waiting 1d'),

    ev('end-of-day', 'due-reviewed', 'linda-nguyen', 'Linda Nguyen', 'August 12, 2026 at 5:00 PM', 'Due · provider selected 73 hours ago', 'resolved'),
    ev('end-of-day', 'unscheduled-overdue', 'linda-nguyen', 'Linda Nguyen', 'August 12, 2026 at 5:01 PM', 'Not scheduled · Monday fields blank', 'resolved'),
    ev('end-of-day', 'exceptions-opened', 'linda-nguyen', 'Linda Nguyen', 'August 12, 2026 at 5:02 PM', 'CM follow-up sent on Teams', 'open', 'Waiting 1d'),
    ev('end-of-day', 'management-notified', 'linda-nguyen', 'Linda Nguyen', 'August 12, 2026 at 5:03 PM', 'Escalated to management · still unresolved', 'open', 'Waiting 1d'),
  ],
}
