import { api } from './client';

export type DayType =
  | 'SCHOOL_DAY' | 'PUBLIC_HOLIDAY' | 'SCHOOL_HOLIDAY'
  | 'HALF_DAY'   | 'WEEKEND'        | 'EXAM_DAY';

export type AttendanceStatus = 'PRESENT' | 'ABSENT' | 'LATE' | 'EXCUSED';

export type DayOfWeek = 'MON' | 'TUE' | 'WED' | 'THU' | 'FRI' | 'SAT' | 'SUN';

export interface ScheduleDay {
  id: string;
  day_of_week: DayOfWeek;
  is_school_day: boolean;
  start_time: string | null;
  end_time: string | null;
}

export interface CalendarDay {
  id: string;
  date: string;            // 'YYYY-MM-DD'
  day_type: DayType;
  notes: string | null;
  academic_term_id: string | null;
}

export interface AttendanceRecord {
  id: string;
  student_id: string;
  school_calendar_id: string;
  class_id: string;
  status: AttendanceStatus;
  notes: string | null;
  recorded_by_id: string;
  recorded_at: string;
}

export interface AttendanceSummary {
  student_id: string;
  term_id: string;
  total_school_days: number;
  days_present: number;
  days_absent: number;
  days_late: number;
  days_excused: number;
  attendance_rate: number;
}

export const listSchedule = (): Promise<ScheduleDay[]> =>
  api.get('/attendance/schedule').then(r => r.data);

export const upsertSchedule = (data: {
  day_of_week: string;
  is_school_day: boolean;
  start_time?: string | null;
  end_time?: string | null;
}): Promise<ScheduleDay> =>
  api.post('/attendance/schedule', data).then(r => r.data);

export const generateCalendar = (termId: string): Promise<CalendarDay[]> =>
  api.post('/attendance/calendar/generate', { term_id: termId }).then(r => r.data);

export const listCalendar = (termId: string): Promise<CalendarDay[]> =>
  api.get('/attendance/calendar', { params: { term_id: termId } }).then(r => r.data);

export const overrideCalendarDay = (calId: string, data: {
  day_type: string;
  notes?: string | null;
}): Promise<CalendarDay> =>
  api.patch(`/attendance/calendar/${calId}`, data).then(r => r.data);

export const markAttendance = (data: {
  school_calendar_id: string;
  class_id: string;
  records: { student_id: string; status: string; notes?: string }[];
}): Promise<AttendanceRecord[]> =>
  api.post('/attendance/mark', data).then(r => r.data);

export const listAttendanceRecords = (
  calendarId: string,
  classId: string,
): Promise<AttendanceRecord[]> =>
  api.get('/attendance/records', { params: { calendar_id: calendarId, class_id: classId } }).then(r => r.data);

export const getAttendanceSummary = (
  studentId: string,
  termId: string,
): Promise<AttendanceSummary> =>
  api.get('/attendance/summary', { params: { student_id: studentId, term_id: termId } }).then(r => r.data);
