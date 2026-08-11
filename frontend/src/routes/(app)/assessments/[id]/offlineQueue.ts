import { get } from 'svelte/store';
import { auth } from '$lib/stores/auth';
import { queueWrite } from '$lib/offline/outbox';
import { refreshOutboxCount } from '$lib/offline/sync';

/** Queues score submissions for later sync when the network is unreachable —
 * see lib/offline/outbox.ts's module docstring: Score is the only entity
 * that goes offline today. */
export async function queueScoresOffline(
  assessmentId: string, entries: { student_id: string; raw_score: number }[],
): Promise<void> {
  const schoolId = get(auth).schoolId ?? '';
  const osa = auth.offlineSessionStartedAt ?? new Date().toISOString();
  for (const e of entries) {
    await queueWrite({
      entity: 'Score', method: 'POST', endpoint: `/assessments/${assessmentId}/scores`,
      payload: { assessment_id: assessmentId, student_id: e.student_id, raw_score: e.raw_score },
      offline_session_started_at: osa, school_id: schoolId,
    });
  }
  await refreshOutboxCount();
}
