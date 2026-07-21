import { api } from './client';

export interface Grade {
  id: string;
  min_score: number;
  max_score: number;
  letter_grade: string;
  label: string;
  gpa_points: number | null;
  remarks: string | null;
}

export interface GradingScale {
  id: string;
  school_id: string | null;
  name: string;
  description: string | null;
  is_active: boolean;
  is_default: boolean;
  grades: Grade[];
}

export interface AssessmentType {
  id: string;
  name: string;
  code: string;
  weight: number;
  is_active: boolean;
}

export interface Assessment {
  id: string;
  school_id: string;
  class_id: string;
  subject_id: string;
  assessment_type_id: string;
  academic_term_id: string;
  name: string;
  max_score: number;
  due_date: string | null;
  is_published: boolean;
}

export interface Score {
  id: string;
  assessment_id: string;
  student_id: string;
  raw_score: number;
  cached_grade_label: string | null;
  is_approved: boolean;
  entered_by_id: string;
  approved_by_id: string | null;
  submitted_at: string | null;
  approved_at: string | null;
}

// ── Grading scales ─────────────────────────────────────────────────────────────

export const listGradingScales = (): Promise<GradingScale[]> =>
  api.get('/assessments/grading-scales').then(r => r.data);

export const createGradingScale = (data: {
  name: string; description?: string; is_default?: boolean;
}): Promise<GradingScale> =>
  api.post('/assessments/grading-scales', data).then(r => r.data);

export const updateGradingScale = (scaleId: string, data: {
  name?: string; description?: string; is_default?: boolean;
}): Promise<GradingScale> =>
  api.patch(`/assessments/grading-scales/${scaleId}`, data).then(r => r.data);

export const addGrade = (scaleId: string, data: Omit<Grade, 'id'>): Promise<Grade> =>
  api.post(`/assessments/grading-scales/${scaleId}/grades`, data).then(r => r.data);

export const deleteGrade = (scaleId: string, gradeId: string): Promise<void> =>
  api.delete(`/assessments/grading-scales/${scaleId}/grades/${gradeId}`).then(() => undefined);

// ── Assessment types ───────────────────────────────────────────────────────────

export const listAssessmentTypes = (): Promise<AssessmentType[]> =>
  api.get('/assessments/types').then(r => r.data);

export const createAssessmentType = (data: {
  name: string; code: string; weight: number;
}): Promise<AssessmentType> =>
  api.post('/assessments/types', data).then(r => r.data);

export const updateAssessmentType = (typeId: string, data: {
  name?: string; code?: string; weight?: number;
}): Promise<AssessmentType> =>
  api.patch(`/assessments/types/${typeId}`, data).then(r => r.data);

// ── Assessments ───────────────────────────────────────────────────────────────

export const listAssessments = (classId: string, termId: string): Promise<Assessment[]> =>
  api.get('/assessments', { params: { class_id: classId, term_id: termId } }).then(r => r.data);

export const getAssessment = (id: string): Promise<Assessment> =>
  api.get(`/assessments/${id}`).then(r => r.data);

export const createAssessment = (data: {
  class_id: string; subject_id: string; assessment_type_id: string;
  academic_term_id: string; name: string; max_score: number; due_date?: string;
}): Promise<Assessment> =>
  api.post('/assessments', data).then(r => r.data);

export const updateAssessment = (id: string, data: {
  name?: string; max_score?: number; due_date?: string | null;
}, overrideReason?: string): Promise<Assessment> =>
  api.patch(`/assessments/${id}`, { ...data, override_reason: overrideReason }).then(r => r.data);

export const deleteAssessment = (id: string): Promise<void> =>
  api.delete(`/assessments/${id}`).then(() => undefined);

export const publishAssessment = (id: string): Promise<Assessment> =>
  api.post(`/assessments/${id}/publish`).then(r => r.data);

export interface RosterStudent {
  id: string;
  display_name: string;
  admission_number: string;
}

// Students eligible to be scored for this assessment's subject — not just
// "everyone in the class" once subject registration splits them (electives).
export const getAssessmentRoster = (id: string): Promise<RosterStudent[]> =>
  api.get(`/assessments/${id}/roster`).then(r => r.data);

// ── Scores ────────────────────────────────────────────────────────────────────

export const listScores = (assessmentId: string): Promise<Score[]> =>
  api.get(`/assessments/${assessmentId}/scores`).then(r => r.data);

export const submitScores = (
  assessmentId: string,
  scores: { student_id: string; raw_score: number }[],
  overrideReason?: string,
): Promise<Score[]> =>
  api.post(`/assessments/${assessmentId}/scores`, { scores, override_reason: overrideReason }).then(r => r.data);

export const approveScores = (
  assessmentId: string,
  scoreIds: string[],
  overrideReason?: string,
): Promise<Score[]> =>
  api.post(`/assessments/${assessmentId}/scores/approve`, { score_ids: scoreIds, override_reason: overrideReason }).then(r => r.data);
