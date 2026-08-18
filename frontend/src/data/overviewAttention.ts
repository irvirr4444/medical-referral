/** Curated demo queues for the Overview “needs attention” strip. */

export interface AttentionItem {
  id: string
  name: string
  detail: string
  stageId: string
  stageLabel: string
}

export interface AttentionBucket {
  id: string
  title: string
  tone: 'ready' | 'attention' | 'blocked'
  items: AttentionItem[]
}

export const OVERVIEW_ATTENTION_BUCKETS: AttentionBucket[] = [
  {
    id: 'ready-for-review',
    title: 'Ready for review',
    tone: 'ready',
    items: [
      {
        id: 'att-ready-1',
        name: 'Maria Alvarez',
        detail: '7/7 fields verified · confirm Monday.com',
        stageId: 'intake',
        stageLabel: 'Intake',
      },
      {
        id: 'att-ready-2',
        name: 'Patricia Johnson',
        detail: 'PDF validated · destination prep ready',
        stageId: 'intake',
        stageLabel: 'Intake',
      },
      {
        id: 'att-ready-3',
        name: 'Samuel Ortiz',
        detail: 'CM match ready · awaiting confirm',
        stageId: 'assignment',
        stageLabel: 'Assignment & handoff',
      },
      {
        id: 'att-ready-4',
        name: 'James Carter',
        detail: 'Route window offered · confirm visit',
        stageId: 'scheduling',
        stageLabel: 'Scheduling',
      },
      {
        id: 'att-ready-5',
        name: 'Irene Cho',
        detail: 'DRK draft ready for send',
        stageId: 'assignment',
        stageLabel: 'Assignment & handoff',
      },
    ],
  },
  {
    id: 'caution',
    title: 'Caution',
    tone: 'attention',
    items: [
      {
        id: 'att-warn-1',
        name: 'Linda Nguyen',
        detail: 'Missing insurance · partner follow-up',
        stageId: 'intake',
        stageLabel: 'Intake',
      },
      {
        id: 'att-warn-2',
        name: 'Riverside ZIP case',
        detail: 'Two CM matches · human selection',
        stageId: 'assignment',
        stageLabel: 'Assignment & handoff',
      },
      {
        id: 'att-warn-3',
        name: 'Helen Park',
        detail: 'No territory match · escalate',
        stageId: 'assignment',
        stageLabel: 'Assignment & handoff',
      },
      {
        id: 'att-warn-4',
        name: 'Unscheduled exception',
        detail: 'End-of-day scan flagged',
        stageId: 'end-of-day',
        stageLabel: 'End-of-day',
      },
    ],
  },
  {
    id: 'blocked',
    title: 'Blocked',
    tone: 'blocked',
    items: [
      {
        id: 'att-block-1',
        name: 'Robert Williams',
        detail: 'Probable duplicate · human review',
        stageId: 'intake',
        stageLabel: 'Intake',
      },
      {
        id: 'att-block-2',
        name: 'Evelyn Brooks',
        detail: 'Phone unclear · handoff held',
        stageId: 'assignment',
        stageLabel: 'Assignment & handoff',
      },
      {
        id: 'att-block-3',
        name: 'Exact chart match',
        detail: 'DRK/Monday create blocked',
        stageId: 'intake',
        stageLabel: 'Intake',
      },
    ],
  },
]
