import { getPendingItems, markSynced, markConflict, type OutboxItem } from '$lib/offline/outbox';
import { drainOutbox } from '$lib/api/sync';

export interface DrainResult { synced: number; conflicts: number; }

const ENTITY_TYPE: Record<OutboxItem['entity'], 'score' | 'attendance'> = {
  Score: 'score',
  Attendance: 'attendance',
};

export async function drainWriteOutbox(): Promise<DrainResult> {
  const pending = await getPendingItems();
  const syncable = pending.filter(item => item.id != null && item.entity in ENTITY_TYPE);
  if (!syncable.length) return { synced: 0, conflicts: 0 };

  const items = syncable.map(item => ({
    outbox_id: String(item.id!),
    client_op_id: item.client_op_id,
    entity_type: ENTITY_TYPE[item.entity],
    offline_session_started_at: item.offline_session_started_at,
    data: item.payload,
  }));

  try {
    const results = await drainOutbox(items);
    let synced = 0, conflicts = 0;
    for (const r of results) {
      const local = syncable.find(p => String(p.id) === r.outbox_id);
      if (!local?.id) continue;
      if (r.status === 'applied') {
        await markSynced(local.id);
        synced++;
      } else {
        await markConflict(local.id, r.conflict_id ?? 'conflict');
        conflicts++;
      }
    }
    return { synced, conflicts };
  } catch {
    return { synced: 0, conflicts: 0 };
  }
}
