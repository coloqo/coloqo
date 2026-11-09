import type { TimelineEntry } from '../api/client'

/** Timeline kinds the feed shows as lines of their own; the rest already have a line there. */
const OWN_LINE = new Set([
  'created',
  'assigned',
  'described',
  'linked',
  'retitled',
  'area',
  'period',
  'parent',
  'child_in',
  'child_out',
  'delivery',
  'works_for',
])

/** Whether a timeline entry gets a line of its own in the Topic's feed (decision 0033). */
export function ownLine(entry: TimelineEntry): boolean {
  if (OWN_LINE.has(entry.kind)) return true
  // A stage set by the migration or by a workflow edit left no line in the Topic.
  return entry.kind === 'stage' && Boolean(entry.data.migrated || entry.data.workflow)
}
