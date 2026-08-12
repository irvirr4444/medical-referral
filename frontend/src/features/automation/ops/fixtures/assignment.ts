import type { StageOpsFixture } from '../types'
import { ev } from './event'

export const ASSIGNMENT_OPS_FIXTURE: StageOpsFixture = {
  stageId: 'assignment',
  events: [
    ev('assignment', 'ready-assignment', 'marcus-feldman', 'Marcus Feldman', 'August 10, 2026 at 9:30 AM', 'Intake approved · ready to assign case manager', 'open', 'Waiting 8h'),
    ev('assignment', 'territory-matched', 'marcus-feldman', 'Marcus Feldman', 'August 10, 2026 at 9:31 AM', 'Gardena territory · Cole Winfield suggested', 'resolved'),
    ev('assignment', 'needs-owner-confirm', 'marcus-feldman', 'Marcus Feldman', 'August 10, 2026 at 9:32 AM', 'Case-manager branch awaiting owner confirmation', 'open', 'Waiting 8h'),

    ev('assignment', 'ready-assignment', 'david-ruiz', 'David Ruiz', 'August 10, 2026 at 11:00 AM', 'Ready to assign', 'open', 'Waiting 6h'),
    ev('assignment', 'territory-matched', 'david-ruiz', 'David Ruiz', 'August 10, 2026 at 11:01 AM', 'Coastal LA · Carla Bustillo suggested', 'resolved'),
    ev('assignment', 'needs-owner-confirm', 'david-ruiz', 'David Ruiz', 'August 10, 2026 at 11:02 AM', 'Case-manager branch has two territory candidates', 'open', 'Waiting 6h'),

    ev('assignment', 'ready-assignment', 'patricia-johnson', 'Patricia Johnson', 'August 9, 2026 at 12:00 PM', 'Ready to assign', 'resolved'),
    ev('assignment', 'territory-matched', 'patricia-johnson', 'Patricia Johnson', 'August 9, 2026 at 12:01 PM', 'Gardena · Cole', 'resolved'),
    ev('assignment', 'assignment-confirmed', 'patricia-johnson', 'Patricia Johnson', 'August 9, 2026 at 12:20 PM', 'Cole confirmed', 'resolved'),
    ev('assignment', 'assignment-written', 'patricia-johnson', 'Patricia Johnson', 'August 9, 2026 at 12:21 PM', 'Owner written to Monday and DRK', 'resolved'),

    ev('assignment', 'ready-assignment', 'thomas-reed', 'Thomas Reed', 'August 10, 2026 at 3:00 PM', 'Ready to assign', 'resolved'),
    ev('assignment', 'territory-matched', 'thomas-reed', 'Thomas Reed', 'August 10, 2026 at 3:01 PM', 'Riverside · Ana', 'resolved'),
    ev('assignment', 'assignment-confirmed', 'thomas-reed', 'Thomas Reed', 'August 10, 2026 at 3:15 PM', 'Ana confirmed', 'resolved'),
    ev('assignment', 'assignment-written', 'thomas-reed', 'Thomas Reed', 'August 10, 2026 at 3:16 PM', 'Assignment written', 'resolved'),

    ev('assignment', 'ready-assignment', 'helen-park', 'Helen Park', 'August 9, 2026 at 3:30 PM', 'Ready to assign', 'resolved'),
    ev('assignment', 'territory-matched', 'helen-park', 'Helen Park', 'August 9, 2026 at 3:31 PM', 'South Bay · Cole', 'resolved'),
    ev('assignment', 'assignment-confirmed', 'helen-park', 'Helen Park', 'August 9, 2026 at 3:45 PM', 'Cole confirmed', 'resolved'),
    ev('assignment', 'assignment-written', 'helen-park', 'Helen Park', 'August 9, 2026 at 3:46 PM', 'Assignment written', 'resolved'),

    ev('assignment', 'ready-assignment', 'betty-hayes', 'Betty Hayes', 'August 8, 2026 at 1:10 PM', 'Missing address requires source follow-up', 'open', 'Waiting 2d'),
    ev('assignment', 'territory-matched', 'betty-hayes', 'Betty Hayes', 'August 8, 2026 at 1:11 PM', 'Referral-source marketer Linda matched', 'resolved'),
    ev('assignment', 'needs-owner-confirm', 'betty-hayes', 'Betty Hayes', 'August 8, 2026 at 1:12 PM', 'Marketer follow-up branch awaiting confirmation', 'open', 'Waiting 2d'),

    ev('assignment', 'ready-assignment', 'maria-alvarez', 'Maria Alvarez', 'August 10, 2026 at 10:15 AM', 'Ready after Monday create', 'open', 'Waiting 7h'),
    ev('assignment', 'territory-matched', 'maria-alvarez', 'Maria Alvarez', 'August 10, 2026 at 10:16 AM', 'Riverside · Donessa Ruiz suggested', 'resolved'),
  ],
}
