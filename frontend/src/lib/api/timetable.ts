import client from './client';
import type { DayOfWeek } from './attendance';

export interface TimetableSlot {
  period_id: string;
  subject_id: string;
  subject_name: string;
  teacher_name: string | null;
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
