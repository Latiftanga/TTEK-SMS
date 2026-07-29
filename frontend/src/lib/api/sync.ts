import { api } from './client';

export interface ScoreData {
  assessment_id: string;
  student_id: string;
  raw_score: number;
}

export type ConflictResolution = 'CLIENT_WINS' | 'SERVER_WINS' | 'MERGED' | 'DISCARDED';

export interface SyncConflict {
  id: string;
  outbox_id: string;
  entity_type: string;
  client_data: ScoreData;
  server_data: ScoreData;
  conflict_type: string;
  resolution: ConflictResolution | null;
  resolved_at: string | null;
  created_at: string;
}

export interface OutboxSyncItem {
  outbox_id: string;
  client_op_id: string;
  entity_type: 'score';
  offline_session_started_at: string;
  data: ScoreData;
}

export interface SyncResult {
  outbox_id: string;
  status: 'applied' | 'conflict';
  conflict_id: string | null;
}

export const drainOutbox = (items: OutboxSyncItem[]): Promise<SyncResult[]> =>
  api.post('/sync/outbox', { items }).then(r => r.data);

export const listConflicts = (): Promise<SyncConflict[]> =>
  api.get('/sync/conflicts').then(r => r.data);

export const resolveConflict = (
  conflictId: string,
  resolution: ConflictResolution,
  mergedData?: ScoreData,
): Promise<SyncConflict> =>
  api.post(`/sync/conflicts/${conflictId}/resolve`, {
    resolution,
    merged_data: mergedData ?? null,
  }).then(r => r.data);
