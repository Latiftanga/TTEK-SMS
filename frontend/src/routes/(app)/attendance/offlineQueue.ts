import { get } from 'svelte/store';
import { auth } from '$lib/stores/auth';
import { queueWrite } from '$lib/offline/outbox';
import { refreshOutboxCount } from '$lib/offline/sync';
import type { AttendanceStatus } from '$lib/api/attendance';

/** Queues attendance marks for later sync when the network is unreachable —
 * one outbox item per student record, mirroring queueScoresOffline's
 * per-student shape (the backend's offline contract is one entity write
 * per outbox item, not a whole batch). */
export async function queueAttendanceOffline(
  schoolCalendarId: string, classId: string,
  records: { student_id: string; status: AttendanceStatus }[],
): Promise<void> {
  const schoolId = get(auth).schoolId ?? '';
  const osa = auth.offlineSessionStartedAt ?? new Date().toISOString();
  for (const r of records) {
    await queueWrite({
      entity: 'Attendance', method: 'POST', endpoint: '/attendance/mark',
      payload: {
        student_id: r.student_id, school_calendar_id: schoolCalendarId,
        class_id: classId, status: r.status,
      },
      offline_session_started_at: osa, school_id: schoolId,
    });
  }
  await refreshOutboxCount();
}
