import { api } from './client';

export type Severity = 'LOW' | 'MEDIUM' | 'HIGH';

export const SEVERITY_LABELS: Record<Severity, string> = {
  LOW: 'Low', MEDIUM: 'Medium', HIGH: 'High',
};

export interface BehaviourRecord {
  id: string;
  student_id: string;
  academic_term_id: string;
  incident_type: string;
  description: string;
  severity: Severity;
  action_taken: string | null;
  incident_date: string;
  recorded_by_id: string;
  created_at: string;
}

export const listBehaviourRecords = (studentId: string, termId: string): Promise<BehaviourRecord[]> =>
  api.get('/behaviour', { params: { student_id: studentId, term_id: termId } }).then(r => r.data);

export const createBehaviourRecord = (data: {
  student_id: string;
  academic_term_id: string;
  incident_type: string;
  description: string;
  severity: Severity;
  action_taken?: string;
  incident_date: string;
  override_reason?: string;
}): Promise<BehaviourRecord> =>
  api.post('/behaviour', data).then(r => r.data);

export const deleteBehaviourRecord = (recordId: string, overrideReason?: string): Promise<void> =>
  api.delete(`/behaviour/${recordId}`, {
    params: overrideReason ? { override_reason: overrideReason } : undefined,
  }).then(() => undefined);
