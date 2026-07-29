/**
 * Offline sync — reactive state, and the single place that triggers a drain.
 *
 * Call initOfflineSync() once from the app layout. Every other component
 * (OfflineBanner, the /sync page) reads pendingOutboxCount/isOnline/isSyncing
 * or calls drainOutbox() here rather than draining independently — two
 * separate triggers previously raced on the same outbox items, submitting
 * the same score twice and surfacing phantom "conflicts" against itself.
 * The actual send/mark-synced mechanics live in $lib/sync/drainer.ts.
 */
import { writable } from 'svelte/store';
import { browser } from '$app/environment';
import { getPendingCount } from './outbox';
import { drainWriteOutbox } from '$lib/sync/drainer';

export const pendingOutboxCount = writable(0);
export const isOnline  = writable(browser ? navigator.onLine : true);
export const isSyncing = writable(false);

let initialized = false;

export async function refreshOutboxCount(): Promise<void> {
  if (!browser) return;
  pendingOutboxCount.set(await getPendingCount());
}

export async function drainOutbox(): Promise<void> {
  if (!browser || !navigator.onLine) return;
  isSyncing.set(true);
  try {
    await drainWriteOutbox();
  } finally {
    isSyncing.set(false);
    await refreshOutboxCount();
  }
}

export function initOfflineSync(): void {
  if (!browser || initialized) return;
  initialized = true;

  refreshOutboxCount();

  if (navigator.onLine) drainOutbox();

  window.addEventListener('online',  () => { isOnline.set(true);  drainOutbox(); });
  window.addEventListener('offline', () => { isOnline.set(false); });
}
