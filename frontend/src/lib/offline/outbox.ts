/**
 * Dexie WriteOutbox — queued write operations.
 *
 * When a POST/PATCH to the API fails (network error), the operation is
 * queued here. The outbox drains automatically when the network returns.
 * Score entries are the only thing that goes offline today — attendance
 * marking has no offline queueing (there's no backend support for it).
 *
 * Every outbox item carries offline_session_started_at so the server
 * can detect conflicts when syncing, and client_op_id — a globally-unique
 * id generated once at queue time — so a retried or duplicated drain can't
 * get double-processed server-side (see OutboxProcessedItem).
 */
import Dexie, { type Table } from 'dexie';

export type OutboxStatus = 'pending' | 'syncing' | 'failed' | 'conflict';

export interface OutboxItem {
  id?: number;                          // auto-increment local ID — unique per device only
  entity: 'Score';
  method: 'POST' | 'PATCH';
  endpoint: string;                     // e.g. /api/attendance
  payload: Record<string, unknown>;
  offline_session_started_at: string;   // ISO datetime — sent to server for conflict detection
  client_op_id: string;                 // globally-unique idempotency key — see module docstring
  school_id: string;
  created_at: number;                   // Unix timestamp — drain in order
  retry_count: number;
  status: OutboxStatus;
  last_error: string | null;
}

class WriteOutboxDB extends Dexie {
  items!: Table<OutboxItem>;

  constructor() {
    super('ttek_write_outbox');
    this.version(1).stores({
      items: '++id, entity, school_id, status, created_at',
    });
  }
}

export const writeOutbox = new WriteOutboxDB();

/** Queue a write operation for later sync. */
export async function queueWrite(
  item: Omit<OutboxItem, 'id' | 'retry_count' | 'status' | 'last_error' | 'created_at' | 'client_op_id'>
): Promise<void> {
  await writeOutbox.items.add({
    ...item,
    client_op_id: crypto.randomUUID(),
    created_at: Date.now(),
    retry_count: 0,
    status: 'pending',
    last_error: null,
  });
}

/** Returns all pending items ordered by creation time. */
export async function getPendingItems(): Promise<OutboxItem[]> {
  return writeOutbox.items
    .where('status')
    .equals('pending')
    .sortBy('created_at');
}

/** Returns count of pending items for the offline indicator UI. */
export async function getPendingCount(): Promise<number> {
  return writeOutbox.items.where('status').equals('pending').count();
}

/** Mark an item as successfully synced — remove it from outbox. */
export async function markSynced(id: number): Promise<void> {
  await writeOutbox.items.delete(id);
}

/** Mark an item as conflicted — pause further processing until resolved. */
export async function markConflict(id: number, error: string): Promise<void> {
  await writeOutbox.items.update(id, {
    status: 'conflict',
    last_error: error,
  });
}

/** Mark an item as failed with error message. */
export async function markFailed(id: number, error: string): Promise<void> {
  const item = await writeOutbox.items.get(id);
  if (!item) return;
  await writeOutbox.items.update(id, {
    status: item.retry_count >= 3 ? 'failed' : 'pending',
    retry_count: item.retry_count + 1,
    last_error: error,
  });
}
