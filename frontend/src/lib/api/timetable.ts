import client from './client';
import type { DayOfWeek } from './attendance';

export interface TimetableSlot {
  period_id: string;
  subject_id: string;
  subject_name: string;
  teacher_name: string | null;
}

export interface ImportRowResult {
  row: number;
  ref: string | null;
  status: string;
  error: string | null;
  warning: string | null;
}

export interface ImportBatchResult {
  batch_id: string;
  total_rows: number;
  created: number;
  failed: number;
  errors: ImportRowResult[];
  warnings: ImportRowResult[];
}

export interface ScheduleEntry {
  day_of_week: DayOfWeek;
  start_time: string;
  end_time: string;
  class_id: string;
  class_name: string;
  subject_id: string;
  subject_name: string;
}

export const getClassTimetable = (classId: string, yearId: string): Promise<TimetableSlot[]> =>
  client.get(`/academic/classes/${classId}/timetable`, { params: { year_id: yearId } }).then(r => r.data);

export const upsertTimetableSlot = (
  classId: string, periodId: string, yearId: string, subjectId: string,
): Promise<TimetableSlot> =>
  client.put(
    `/academic/classes/${classId}/timetable/${periodId}`,
    { subject_id: subjectId },
    { params: { year_id: yearId } },
  ).then(r => r.data);

export const deleteTimetableSlot = (classId: string, periodId: string, yearId: string): Promise<void> =>
  client.delete(`/academic/classes/${classId}/timetable/${periodId}`, { params: { year_id: yearId } });

// Omit yearId to let the backend default to the school's current academic year.
export const getMySchedule = (yearId?: string): Promise<ScheduleEntry[]> =>
  client.get('/timetable/my-schedule', { params: yearId ? { year_id: yearId } : undefined }).then(r => r.data);

// Bulk-creates/updates a whole school's TimetableSlot rows for one academic
// year from TTEK-SMS's own generic timetable CSV format (see
// TimetableImportModal.svelte for the column reference shown to admins).
export const bulkImportTimetable = (file: File, yearId: string): Promise<ImportBatchResult> => {
  const form = new FormData();
  form.append('file', file);
  return client
    .post<ImportBatchResult>('/academic/timetable/import', form, { params: { year_id: yearId } })
    .then(r => r.data);
};
