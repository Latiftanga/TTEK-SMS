import { api } from './client';

// ── AI-generated structured content (LessonPlan.generated_content) ─────────

export interface LessonEntry {
  school_calendar_id: string;
  period_id: string;
  lesson_date: string;
  start_time: string;
  end_time: string;
  duration_minutes: number;
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
  created_by_id: string;
  curriculum_standard_id: string | null;
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

export const generateLessons = (id: string): Promise<LessonPlan> =>
  api.post(`/lesson-plans/${id}/generate-lessons`).then(r => r.data);

export const regenerateLesson = (
  id: string, schoolCalendarId: string, periodId: string,
): Promise<LessonPlan> =>
  api.post(`/lesson-plans/${id}/regenerate-lesson`, {
    school_calendar_id: schoolCalendarId, period_id: periodId,
  }).then(r => r.data);

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

export const finalizeChat = (lessonPlanId: string): Promise<LessonPlan> =>
  api.post(`/lesson-plans/${lessonPlanId}/chat/finalize`).then(r => r.data);
