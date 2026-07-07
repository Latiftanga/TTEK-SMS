/**
 * Offline sync service — drains the WriteOutbox when connectivity returns.
 *
 * Call initOfflineSync() once from the app layout.
 * pendingOutboxCount is a reactive store that drives the offline indicator.
 */
import { writable } from 'svelte/store';
import { browser } from '$app/environment';
import { api } from '$lib/api/client';
import { getPendingItems, getPendingCount, markSynced, markConflict } from './outbox';

export const pendingOutboxCount = writable(0);

let initialized = false;

export async function refreshOutboxCount(): Promise<void> {
  if (!browser) return;
  pendingOutboxCount.set(await getPendingCount());
}

export async function drainOutbox(): Promise<void> {
  if (!browser || !navigator.onLine) return;

  const items = await getPendingItems();
  if (!items.length) return;

  const payload = {
    items: items.map(item => ({
      outbox_id: String(item.id),
      entity_type: item.entity === 'Score' ? 'score' : 'attendance_record',
      offline_session_started_at: item.offline_session_started_at,
      data: item.payload,
    })),
  };

  try {
    const res = await api.post('/sync/outbox', payload);
    const results = res.data as Array<{
      outbox_id: string;
      status: 'applied' | 'conflict';
      conflict_id?: string;
    }>;

    for (const result of results) {
      const item = items.find(i => String(i.id) === result.outbox_id);
      if (!item?.id) continue;
      if (result.status === 'applied') {
        await markSynced(item.id);
      } else {
        await markConflict(item.id, `conflict:${result.conflict_id ?? 'unknown'}`);
      }
    }
  } catch {
    // Network still unavailable — items stay pending, retry on next online event.
  }

  await refreshOutboxCount();
}

export function initOfflineSync(): void {
  if (!browser || initialized) return;
  initialized = true;

  refreshOutboxCount();

  // Drain any items left from a previous offline session.
  if (navigator.onLine) drainOutbox();

  window.addEventListener('online', () => drainOutbox());
}
