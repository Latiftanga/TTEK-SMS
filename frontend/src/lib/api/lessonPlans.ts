import { api } from './client';

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
