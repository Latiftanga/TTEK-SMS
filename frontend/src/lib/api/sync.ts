import { api } from './client';

export interface ScoreData {
  assessment_id: string;
  student_id: string;
  raw_score: number;
}

export interface AttendanceData {
  student_id: string;
  school_calendar_id: string;
  class_id: string;
  status: string;
  notes?: string | null;
  period_id?: string | null;
}

export type ConflictResolution = 'CLIENT_WINS' | 'SERVER_WINS' | 'MERGED' | 'DISCARDED';

export interface SyncConflict {
  id: string;
  outbox_id: string;
  entity_type: 'score' | 'attendance' | string;
  // Score conflicts: {assessment_id, student_id, raw_score} (client) /
  // {raw_score, submitted_at, is_approved} (server). Attendance conflicts:
  // {student_id, school_calendar_id, class_id, status, notes} (client) /
  // {status, recorded_at, notes} (server) — shapes genuinely differ between
  // client_data and server_data even within one entity_type, so both are
  // loosely typed and read defensively by entity_type in the UI.
  client_data: Record<string, unknown>;
  server_data: Record<string, unknown>;
  conflict_type: string;
  resolution: ConflictResolution | null;
  resolved_at: string | null;
  created_at: string;
}

export interface OutboxSyncItem {
  outbox_id: string;
  client_op_id: string;
  entity_type: 'score' | 'attendance';
  offline_session_started_at: string;
  data: Record<string, unknown>;
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
  mergedData?: ScoreData | AttendanceData,
): Promise<SyncConflict> =>
  api.post(`/sync/conflicts/${conflictId}/resolve`, {
    resolution,
    merged_data: mergedData ?? null,
  }).then(r => r.data);
