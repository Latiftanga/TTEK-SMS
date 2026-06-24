import { getPendingItems, markSynced, markConflict } from '$lib/offline/outbox';
import { drainOutbox } from '$lib/api/sync';

export interface DrainResult { synced: number; conflicts: number; }

export async function drainWriteOutbox(): Promise<DrainResult> {
  const pending = await getPendingItems();
  if (!pending.length) return { synced: 0, conflicts: 0 };

  const scoreItems = pending.filter(item => item.entity === 'Score' && item.id != null);
  if (!scoreItems.length) return { synced: 0, conflicts: 0 };

  const items = scoreItems.map(item => ({
    outbox_id: String(item.id!),
    entity_type: 'score' as const,
    offline_session_started_at: item.offline_session_started_at,
    data: item.payload as { assessment_id: string; student_id: string; raw_score: number },
  }));

  try {
    const results = await drainOutbox(items);
    let synced = 0, conflicts = 0;
    for (const r of results) {
      const local = scoreItems.find(p => String(p.id) === r.outbox_id);
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
