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

// Fixed 3-way split — core assessment theory, not per-school configurable.
// DIAGNOSTIC never enters term aggregation or report-card output at all —
// it identifies a learning gap or guides a decision (e.g. placement into
// the right programme/subject combination), administered whenever a
// teacher or admin decides it's needed rather than on a schedule.
export type AssessmentCategory = 'DIAGNOSTIC' | 'FORMATIVE' | 'SUMMATIVE';

// How multiple recorded entries for one type collapse into a single score.
// Only meaningful when allow_multiple_entries is true — NONE otherwise.
export type AggregationStrategy = 'NONE' | 'BEST_OF' | 'AVERAGE' | 'SUM_NORMALIZE';

export interface AssessmentType {
  id: string;
  name: string;
  code: string;
  weight: number;
  category: AssessmentCategory;
  allow_multiple_entries: boolean;
  aggregation_strategy: AggregationStrategy;
  is_active: boolean;
}

export interface AssessmentTypePreset {
  name: string;
  code: string;
  weight: number;
  category: AssessmentCategory;
  allow_multiple_entries: boolean;
  aggregation_strategy: AggregationStrategy;
}

export interface Assessment {
  id: string;
  school_id: string;
  class_id: string;
  subject_id: string;
  assessment_type_id: string;
  academic_term_id: string;
  description: string | null;
  recorded_date: string;
  max_score: number;
  due_date: string | null;
  is_published: boolean;
}

// An assessment's identity is its category (AssessmentType) + the date it
// was recorded, not a teacher-typed name — mirrors the en-GH date format
// already used in dashboard/TeacherView.svelte.
export const formatAssessmentDate = (iso: string): string =>
  new Date(iso).toLocaleDateString('en-GH', { day: 'numeric', month: 'short' });

export const assessmentLabel = (a: Assessment, categoryName: string): string =>
  `${categoryName} — ${formatAssessmentDate(a.recorded_date)}`;

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
  name?: string; description?: string; is_default?: boolean; is_active?: boolean;
}): Promise<GradingScale> =>
  api.patch(`/assessments/grading-scales/${scaleId}`, data).then(r => r.data);

// Hard-deletes the scale — only succeeds when it isn't the active default
// (backend returns 409 naming the scale otherwise). Deactivate via
// updateGradingScale({ is_active: false }) works for a scale that IS default
// too, since that safely falls back to the next scale in priority order.
export const deleteGradingScale = (scaleId: string): Promise<void> =>
  api.delete(`/assessments/grading-scales/${scaleId}`).then(() => undefined);

export const addGrade = (scaleId: string, data: Omit<Grade, 'id'>): Promise<Grade> =>
  api.post(`/assessments/grading-scales/${scaleId}/grades`, data).then(r => r.data);

export const deleteGrade = (scaleId: string, gradeId: string): Promise<void> =>
  api.delete(`/assessments/grading-scales/${scaleId}/grades/${gradeId}`).then(() => undefined);

// ── Assessment types ───────────────────────────────────────────────────────────

export const listAssessmentTypes = (): Promise<AssessmentType[]> =>
  api.get('/assessments/types').then(r => r.data);

export const createAssessmentType = (data: {
  name: string; code: string; weight: number;
  category: AssessmentCategory;
  allow_multiple_entries: boolean; aggregation_strategy: AggregationStrategy;
}): Promise<AssessmentType> =>
  api.post('/assessments/types', data).then(r => r.data);

export const updateAssessmentType = (typeId: string, data: {
  name?: string; code?: string; weight?: number;
  category?: AssessmentCategory;
  allow_multiple_entries?: boolean; aggregation_strategy?: AggregationStrategy;
  is_active?: boolean;
}): Promise<AssessmentType> =>
  api.patch(`/assessments/types/${typeId}`, data).then(r => r.data);

// Hard-deletes the type — only succeeds when zero assessments reference it
// (backend returns 409 naming the count otherwise). Deactivate via
// updateAssessmentType({ is_active: false }) is the safe default for a type
// with real data.
export const deleteAssessmentType = (typeId: string): Promise<void> =>
  api.delete(`/assessments/types/${typeId}`).then(() => undefined);

// Static, school-agnostic pre-fill config for the type-creation form — see
// backend/app/services/assessment_type_presets.py. Picking one just fills
// the form fields; nothing here is special-cased once a type is created.
export const listTypePresets = (): Promise<Record<string, AssessmentTypePreset[]>> =>
  api.get('/assessments/type-presets').then(r => r.data);

// ── Assessments ───────────────────────────────────────────────────────────────

export const listAssessments = (classId: string, termId: string): Promise<Assessment[]> =>
  api.get('/assessments', { params: { class_id: classId, term_id: termId } }).then(r => r.data);

export interface MySubjectAssignment {
  class_id: string;
  class_name: string;
  subject_id: string;
  subject_name: string;
}

// (class, subject) combos the caller can create assessments/enter scores
// for — scoped to their own SubjectTeacher assignment(s) unless they hold
// assessments.approve_scores (the backend returns every active class+subject
// pairing in the school for those callers instead).
export const listMySubjects = (termId: string): Promise<MySubjectAssignment[]> =>
  api.get('/assessments/my-subjects', { params: { term_id: termId } }).then(r => r.data);

export const getAssessment = (id: string): Promise<Assessment> =>
  api.get(`/assessments/${id}`).then(r => r.data);

export const createAssessment = (data: {
  class_id: string; subject_id: string; assessment_type_id: string;
  academic_term_id: string; description?: string; max_score: number; due_date?: string;
}, overrideReason?: string): Promise<Assessment> =>
  api.post('/assessments', { ...data, override_reason: overrideReason }).then(r => r.data);

export const updateAssessment = (id: string, data: {
  description?: string; max_score?: number; due_date?: string | null;
}, overrideReason?: string): Promise<Assessment> =>
  api.patch(`/assessments/${id}`, { ...data, override_reason: overrideReason }).then(r => r.data);

export const deleteAssessment = (id: string): Promise<void> =>
  api.delete(`/assessments/${id}`).then(() => undefined);

export const publishAssessment = (id: string): Promise<Assessment> =>
  api.post(`/assessments/${id}/publish`).then(r => r.data);

export const unpublishAssessment = (id: string, reason: string): Promise<Assessment> =>
  api.post(`/assessments/${id}/unpublish`, { reason }).then(r => r.data);

export interface BulkPublishResult {
  published: number;
  skipped_unapproved: number;
  already_published: number;
}

export const bulkPublishAssessments = (classId: string, academicTermId: string): Promise<BulkPublishResult> =>
  api.post('/assessments/bulk-publish', { class_id: classId, academic_term_id: academicTermId }).then(r => r.data);

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
