import { api } from './client';
import type { CurriculumUnit } from './curriculumUnits';

// ── AI-generated structured content (LessonPlan.generated_content) ─────────

export interface LessonEntry {
  // Nullable together: a class with no real timetable for this week has no
  // real calendar day/period to attach to — such a lesson is a
  // teacher-declared placeholder identified by sequence_index instead.
  school_calendar_id: string | null;
  period_id: string | null;
  sequence_index: number | null;
  lesson_date: string | null;
  start_time: string | null;
  end_time: string | null;
  duration_minutes: number | null;
  introduction: string;
  main_lesson: string;
  closure: string;
  delivery_status: string;
}

export interface AssessmentSection { mode: string; task: string; }
export interface FormativeAssessment extends AssessmentSection { mark_scheme: string; }
export interface TranscriptAssessment extends AssessmentSection { rubric: string; }
export interface AssessmentBlock {
  formative: FormativeAssessment;
  transcript_assessment: TranscriptAssessment;
}

export interface GeneratedContent {
  essential_questions: string[];
  pedagogical_strategies: string[];
  teaching_learning_resources: string[];
  differentiation_notes: string | null;
  lessons: LessonEntry[];
  assessment: AssessmentBlock | null;
  occurrence_mismatch: boolean;
  generation_warnings: string[];
}

export type LessonPlanStatus = 'DRAFT' | 'APPROVED';

export interface LessonPlan {
  id: string;
  school_id: string;
  class_id: string;
  subject_id: string;
  academic_term_id: string;
  week_start_date: string;
  topic: string;
  content_standard: string | null;
  indicator: string | null;
  learning_objectives: string | null;
  core_competencies: string | null;
  teaching_resources: string | null;
  activities: string | null;
  assessment_strategy: string | null;
  reflection_notes: string | null;
  strand: string | null;
  sub_strand: string | null;
  created_by_id: string;
  curriculum_standard_id: string | null;
  curriculum_unit_id: string | null;
  generated_content: GeneratedContent | null;
  status: LessonPlanStatus;
  reviewed_by_staff_id: string | null;
  review_notes: string | null;
  reviewed_at: string | null;
}

export interface LessonPlanPayload {
  topic: string;
  content_standard?: string | null;
  indicator?: string | null;
  learning_objectives?: string | null;
  core_competencies?: string | null;
  teaching_resources?: string | null;
  activities?: string | null;
  assessment_strategy?: string | null;
  reflection_notes?: string | null;
  curriculum_standard_id?: string | null;
  curriculum_unit_id?: string | null;
}

export const listLessonPlans = (
  classId: string, subjectId: string, termId: string, weekStartDate: string,
): Promise<LessonPlan[]> =>
  api.get('/lesson-plans', {
    params: { class_id: classId, subject_id: subjectId, academic_term_id: termId, week_start_date: weekStartDate },
  }).then(r => r.data);

export const getLessonPlan = (id: string): Promise<LessonPlan> =>
  api.get(`/lesson-plans/${id}`).then(r => r.data);

export const createLessonPlan = (data: LessonPlanPayload & {
  class_id: string; subject_id: string; academic_term_id: string; week_start_date: string;
}): Promise<LessonPlan> =>
  api.post('/lesson-plans', data).then(r => r.data);

export const updateLessonPlan = (id: string, data: Partial<LessonPlanPayload>): Promise<LessonPlan> =>
  api.patch(`/lesson-plans/${id}`, data).then(r => r.data);

export const deleteLessonPlan = (id: string): Promise<void> =>
  api.delete(`/lesson-plans/${id}`);

export const draftLessonPlanWithAi = (
  classId: string, subjectId: string, topic: string,
): Promise<{ draft_text: string }> =>
  api.post('/lesson-plans/ai-draft', { class_id: classId, subject_id: subjectId, topic }).then(r => r.data);

// ── Staged AI generation — skeleton first (cheap to iterate), then expand ───

export const generateSkeleton = (id: string): Promise<LessonPlan> =>
  api.post(`/lesson-plans/${id}/generate-skeleton`).then(r => r.data);

// lessonCount is only consulted server-side when this class+subject
// genuinely has no real timetable for this week — whenever a real
// timetable exists, its count stays authoritative and this is ignored.
export const generateLessons = (id: string, lessonCount?: number): Promise<LessonPlan> =>
  api.post(`/lesson-plans/${id}/generate-lessons`, { lesson_count: lessonCount ?? null }).then(r => r.data);

// Either (schoolCalendarId, periodId) for a real-occurrence lesson, or
// sequenceIndex for a teacher-declared (no-timetable) placeholder.
export const regenerateLesson = (
  id: string, identity: { schoolCalendarId: string; periodId: string } | { sequenceIndex: number },
): Promise<LessonPlan> =>
  api.post(`/lesson-plans/${id}/regenerate-lesson`,
    'sequenceIndex' in identity
      ? { sequence_index: identity.sequenceIndex }
      : { school_calendar_id: identity.schoolCalendarId, period_id: identity.periodId },
  ).then(r => r.data);

export const regenerateAssessment = (id: string): Promise<LessonPlan> =>
  api.post(`/lesson-plans/${id}/regenerate-assessment`).then(r => r.data);

export const reviewLessonPlan = (
  id: string, data: { status: LessonPlanStatus; review_notes?: string | null },
): Promise<LessonPlan> =>
  api.patch(`/lesson-plans/${id}/review`, data).then(r => r.data);

// ── Curriculum standards ─────────────────────────────────────────────────────

export interface CurriculumStandard {
  id: string;
  school_id: string | null;
  subject_catalogue_id: string;
  level: string;
  year_group: number;
  strand: string;
  sub_strand: string;
  indicator_code: string;
  objective_text: string;
  is_active: boolean;
}

export const listCurriculumStandards = (params: {
  subject_catalogue_id?: string; level?: string; year_group?: number; q?: string;
}): Promise<CurriculumStandard[]> =>
  api.get('/curriculum-standards', { params }).then(r => r.data);

// ── Curriculum-grounded chat assistant ──────────────────────────────────────
// A genuine back-and-forth conversation, additive alongside the button-driven
// generate/expand/regenerate flow above — "finalize" converts the
// conversation into the same GeneratedContent shape those buttons produce.

export type ChatMessageRole = 'USER' | 'ASSISTANT';

export interface ChatMessage {
  id: string;
  role: ChatMessageRole;
  content: string;
  created_at: string;
}

export const listChatMessages = (lessonPlanId: string): Promise<ChatMessage[]> =>
  api.get(`/lesson-plans/${lessonPlanId}/chat`).then(r => r.data);

export const sendChatMessage = (lessonPlanId: string, message: string): Promise<ChatMessage[]> =>
  api.post(`/lesson-plans/${lessonPlanId}/chat`, { message }).then(r => r.data);

export const finalizeChat = (lessonPlanId: string, lessonCount?: number): Promise<LessonPlan> =>
  api.post(`/lesson-plans/${lessonPlanId}/chat/finalize`, { lesson_count: lessonCount ?? null }).then(r => r.data);

// ── Curriculum units (machine-extracted from an uploaded material) ─────────
// A second, independent "pick a unit" flow alongside curriculum standards —
// never auto-mapped from the calendar week, the teacher picks explicitly.

export const listCurriculumUnitsForPlanning = (
  classId: string, subjectId: string, termId: string,
): Promise<CurriculumUnit[]> =>
  api.get('/lesson-plans/curriculum-units', {
    params: { class_id: classId, subject_id: subjectId, academic_term_id: termId },
  }).then(r => r.data);
