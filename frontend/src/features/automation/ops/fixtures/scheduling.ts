import type { StageOpsFixture } from '../types'
import { ev } from './event'

export const SCHEDULING_OPS_FIXTURE: StageOpsFixture = {
  stageId: 'scheduling',
  events: [
    ev('scheduling', 'ready-schedule', 'maria-alvarez', 'Maria Alvarez', 'August 10, 2026 at 10:05 AM', 'Provider confirmed · ready to schedule', 'open', 'Waiting 7h'),
    ev('scheduling', 'windows-proposed', 'maria-alvarez', 'Maria Alvarez', 'August 10, 2026 at 10:06 AM', 'Referral sent to selected provider', 'resolved'),
    ev('scheduling', 'awaiting-response', 'maria-alvarez', 'Maria Alvarez', 'August 10, 2026 at 10:07 AM', 'Awaiting provider response', 'open', 'Waiting 7h'),

    ev('scheduling', 'ready-schedule', 'nancy-liu', 'Nancy Liu', 'August 10, 2026 at 8:30 AM', 'Ready to schedule', 'resolved'),
    ev('scheduling', 'windows-proposed', 'nancy-liu', 'Nancy Liu', 'August 10, 2026 at 8:31 AM', 'Two route-compatible windows', 'resolved'),
    ev('scheduling', 'appointment-confirmed', 'nancy-liu', 'Nancy Liu', 'August 10, 2026 at 9:10 AM', 'Fri 11:00 AM accepted', 'resolved'),
    ev('scheduling', 'appointment-written', 'nancy-liu', 'Nancy Liu', 'August 10, 2026 at 9:11 AM', 'Monday and DRK appointment updated', 'resolved'),

    ev('scheduling', 'ready-schedule', 'james-carter', 'James Carter', 'August 10, 2026 at 9:00 AM', 'Ready to schedule', 'open', 'Waiting 8h'),
    ev('scheduling', 'windows-proposed', 'james-carter', 'James Carter', 'August 10, 2026 at 9:01 AM', 'Referral sent to selected provider', 'resolved'),
    ev('scheduling', 'awaiting-response', 'james-carter', 'James Carter', 'August 10, 2026 at 9:02 AM', 'Provider response window started', 'resolved'),
    ev('scheduling', 'scheduling-exception', 'james-carter', 'James Carter', 'August 10, 2026 at 10:05 AM', 'No provider reply after one hour - Carla notified', 'open', 'Waiting 7h'),

    ev('scheduling', 'ready-schedule', 'patricia-johnson', 'Patricia Johnson', 'August 9, 2026 at 2:00 PM', 'Ready to schedule', 'resolved'),
    ev('scheduling', 'windows-proposed', 'patricia-johnson', 'Patricia Johnson', 'August 9, 2026 at 2:01 PM', 'Fri 11:00 AM ranked first', 'resolved'),
    ev('scheduling', 'appointment-confirmed', 'patricia-johnson', 'Patricia Johnson', 'August 9, 2026 at 3:18 PM', 'Fri 11:00 AM accepted after 18 minutes', 'resolved'),
    ev('scheduling', 'appointment-written', 'patricia-johnson', 'Patricia Johnson', 'August 9, 2026 at 3:19 PM', 'Appointment written', 'resolved'),

    ev('scheduling', 'ready-schedule', 'thomas-reed', 'Thomas Reed', 'August 10, 2026 at 3:45 PM', 'Ready to schedule', 'open', 'Waiting 2h'),
    ev('scheduling', 'windows-proposed', 'thomas-reed', 'Thomas Reed', 'August 10, 2026 at 3:46 PM', 'Referral sent to selected provider', 'resolved'),
    ev('scheduling', 'awaiting-response', 'thomas-reed', 'Thomas Reed', 'August 10, 2026 at 3:47 PM', 'Awaiting provider response', 'open', 'Waiting 2h'),

    ev('scheduling', 'ready-schedule', 'linda-nguyen', 'Linda Nguyen', 'August 9, 2026 at 4:00 PM', 'Ready to schedule', 'open', 'Waiting 1d'),
    ev('scheduling', 'windows-proposed', 'linda-nguyen', 'Linda Nguyen', 'August 9, 2026 at 4:01 PM', 'Two windows', 'resolved'),
    ev('scheduling', 'scheduling-exception', 'linda-nguyen', 'Linda Nguyen', 'August 9, 2026 at 5:30 PM', 'Patient declined both windows', 'open', 'Waiting 1d'),

    ev('scheduling', 'ready-schedule', 'helen-park', 'Helen Park', 'August 8, 2026 at 5:00 PM', 'Ready to schedule', 'resolved'),
    ev('scheduling', 'appointment-confirmed', 'helen-park', 'Helen Park', 'August 8, 2026 at 5:40 PM', 'Sat 9:00 AM confirmed', 'resolved'),
    ev('scheduling', 'appointment-written', 'helen-park', 'Helen Park', 'August 8, 2026 at 5:41 PM', 'Appointment written', 'resolved'),
  ],
}
