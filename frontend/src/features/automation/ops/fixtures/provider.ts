import type { StageOpsFixture } from '../types'
import { ev } from './event'

export const PROVIDER_OPS_FIXTURE: StageOpsFixture = {
  stageId: 'provider',
  events: [
    ev('provider', 'needs-provider', 'helen-park', 'Helen Park', 'August 10, 2026 at 8:50 AM', 'Assignment complete · select provider', 'open', 'Waiting 9h'),
    ev('provider', 'shortlist-ready', 'helen-park', 'Helen Park', 'August 10, 2026 at 8:51 AM', '3 credentialed providers ranked', 'resolved'),
    ev('provider', 'needs-provider-confirm', 'helen-park', 'Helen Park', 'August 10, 2026 at 8:52 AM', 'Awaiting marketer pick', 'open', 'Waiting 9h'),

    ev('provider', 'needs-provider', 'irene-cho', 'Irene Cho', 'August 10, 2026 at 9:20 AM', 'Needs provider', 'open', 'Waiting 8h'),
    ev('provider', 'shortlist-ready', 'irene-cho', 'Irene Cho', 'August 10, 2026 at 9:21 AM', '2 providers in service radius', 'resolved'),
    ev('provider', 'needs-provider-confirm', 'irene-cho', 'Irene Cho', 'August 10, 2026 at 9:22 AM', 'Preferred provider at capacity', 'open', 'Waiting 8h'),

    ev('provider', 'needs-provider', 'betty-hayes', 'Betty Hayes', 'August 9, 2026 at 2:00 PM', 'Needs provider', 'open', 'Waiting 1d'),
    ev('provider', 'shortlist-ready', 'betty-hayes', 'Betty Hayes', 'August 9, 2026 at 2:01 PM', 'Empty shortlist · expand radius', 'resolved'),
    ev('provider', 'needs-provider-confirm', 'betty-hayes', 'Betty Hayes', 'August 9, 2026 at 2:02 PM', 'No eligible provider · human search', 'open', 'Waiting 1d'),

    ev('provider', 'needs-provider', 'patricia-johnson', 'Patricia Johnson', 'August 9, 2026 at 12:30 PM', 'Needs provider', 'resolved'),
    ev('provider', 'shortlist-ready', 'patricia-johnson', 'Patricia Johnson', 'August 9, 2026 at 12:31 PM', '4 providers ranked', 'resolved'),
    ev('provider', 'provider-confirmed', 'patricia-johnson', 'Patricia Johnson', 'August 9, 2026 at 1:05 PM', 'Dr. Nguyen confirmed', 'resolved'),
    ev('provider', 'provider-written', 'patricia-johnson', 'Patricia Johnson', 'August 9, 2026 at 1:06 PM', 'Provider written to destinations', 'resolved'),

    ev('provider', 'needs-provider', 'thomas-reed', 'Thomas Reed', 'August 10, 2026 at 3:20 PM', 'Needs provider', 'resolved'),
    ev('provider', 'shortlist-ready', 'thomas-reed', 'Thomas Reed', 'August 10, 2026 at 3:21 PM', '3 providers ranked', 'resolved'),
    ev('provider', 'provider-confirmed', 'thomas-reed', 'Thomas Reed', 'August 10, 2026 at 3:40 PM', 'Dr. Patel confirmed', 'resolved'),
    ev('provider', 'provider-written', 'thomas-reed', 'Thomas Reed', 'August 10, 2026 at 3:41 PM', 'Provider written', 'resolved'),

    ev('provider', 'needs-provider', 'maria-alvarez', 'Maria Alvarez', 'August 10, 2026 at 10:20 AM', 'Needs provider after assignment match', 'open', 'Waiting 7h'),
    ev('provider', 'shortlist-ready', 'maria-alvarez', 'Maria Alvarez', 'August 10, 2026 at 10:21 AM', '5 providers ranked for Riverside', 'resolved'),

    ev('provider', 'needs-provider', 'nancy-liu', 'Nancy Liu', 'August 8, 2026 at 4:00 PM', 'Needs provider', 'resolved'),
    ev('provider', 'provider-confirmed', 'nancy-liu', 'Nancy Liu', 'August 8, 2026 at 4:30 PM', 'Dr. Kim confirmed', 'resolved'),
    ev('provider', 'provider-written', 'nancy-liu', 'Nancy Liu', 'August 8, 2026 at 4:31 PM', 'Provider written', 'resolved'),
  ],
}
