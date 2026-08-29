import { api } from './client';
import type { SchoolClass } from './academic';
import type { ExcuseRequest } from './portal';
export type { ExcuseRequest } from './portal';

export type DayType =
  | 'SCHOOL_DAY' | 'PUBLIC_HOLIDAY' | 'SCHOOL_HOLIDAY'
  | 'HALF_DAY'   | 'WEEKEND'        | 'EXAM_DAY';

export type AttendanceStatus = 'PRESENT' | 'ABSENT' | 'LATE' | 'EXCUSED';

export type DayOfWeek = 'MON' | 'TUE' | 'WED' | 'THU' | 'FRI' | 'SAT' | 'SUN';

export interface ScheduleDay {
  id: string;
  day_of_week: DayOfWeek;
  is_school_day: boolean;
}

export interface CalendarDay {
  id: string;
  date: string;            // 'YYYY-MM-DD'
  day_type: DayType;
  notes: string | null;
  academic_term_id: string | null;
  is_manual_override: boolean;
}

export interface AttendanceRecord {
  id: string;
  student_id: string;
  school_calendar_id: string;
  class_id: string;
  period_id: string | null;
  status: AttendanceStatus;
  notes: string | null;
  recorded_by_id: string;
  recorded_at: string;
}

// One row of the period picker on the Mark Attendance page — additive to
// the always-available "Whole day" option, never shown at all unless the
// school has opted into period-level attendance.
export interface MarkablePeriod {
  period_id: string;
  name: string;
  start_time: string;
  end_time: string;
  subject_id: string;
  subject_name: string;
  teacher_name: string | null;
  can_mark: boolean;
  already_marked: boolean;
}

export interface AttendanceSummary {
  student_id: string;
  term_id: string;
  total_school_days: number;
  days_present: number;
  days_absent: number;
  days_late: number;
  days_excused: number;
  days_unmarked: number;
  attendance_rate: number;
}

export interface TodayStatus {
  calendar_day: CalendarDay | null;
  is_markable: boolean;
  record_count: number;
}

export interface StudentAbsenceSummary {
  student_id: string;
  days_absent: number;
  days_late: number;
  attendance_rate: number;
}

export interface ClassMarkingStatus {
  class_id: string;
  name: string;
  student_count: number;
  present: number;
  absent: number;
  marked: boolean;
  class_teacher_name: string | null;
}

export const listSchedule = (): Promise<ScheduleDay[]> =>
  api.get('/attendance/schedule').then(r => r.data);

export const upsertSchedule = (data: {
  day_of_week: string;
  is_school_day: boolean;
}): Promise<ScheduleDay> =>
  api.post('/attendance/schedule', data).then(r => r.data);

export const generateCalendar = (termId: string, force = false): Promise<CalendarDay[]> =>
  api.post('/attendance/calendar/generate', { term_id: termId, force }).then(r => r.data);

export const listCalendar = (termId: string): Promise<CalendarDay[]> =>
  api.get('/attendance/calendar', { params: { term_id: termId } }).then(r => r.data);

export const overrideCalendarDay = (calId: string, data: {
  day_type: string;
  notes?: string | null;
}): Promise<CalendarDay> =>
  api.patch(`/attendance/calendar/${calId}`, data).then(r => r.data);

// Mark every already-generated calendar day in a date range at once — e.g.
// a week-long mid-term break — instead of one overrideCalendarDay() call
// per day.
export const overrideCalendarRange = (data: {
  start_date: string;
  end_date: string;
  day_type: string;
  notes?: string | null;
}): Promise<CalendarDay[]> =>
  api.patch('/attendance/calendar/range', data).then(r => r.data);

export const markAttendance = (data: {
  school_calendar_id: string;
  class_id: string;
  records: { student_id: string; status: string; notes?: string }[];
  override_reason?: string;
  period_id?: string | null;
}): Promise<AttendanceRecord[]> =>
  api.post('/attendance/mark', data).then(r => r.data);

export const listAttendanceRecords = (
  calendarId: string,
  classId: string,
  periodId?: string | null,
): Promise<AttendanceRecord[]> =>
  api.get('/attendance/records', {
    params: { calendar_id: calendarId, class_id: classId, ...(periodId ? { period_id: periodId } : {}) },
  }).then(r => r.data);

// Periods the caller can mark attendance for on this class+day — [] when
// the school hasn't enabled period-level attendance, or the day has none.
export const getMarkablePeriods = (classId: string, calendarId: string): Promise<MarkablePeriod[]> =>
  api.get('/attendance/markable-periods', { params: { class_id: classId, calendar_id: calendarId } }).then(r => r.data);

export const getTodayStatus = (classId: string): Promise<TodayStatus> =>
  api.get('/attendance/today', { params: { class_id: classId } }).then(r => r.data);

export const getClassSummaries = (classId: string, termId: string): Promise<StudentAbsenceSummary[]> =>
  api.get('/attendance/class-summaries', { params: { class_id: classId, term_id: termId } }).then(r => r.data);

export const getAttendanceSummary = (
  studentId: string,
  termId: string,
): Promise<AttendanceSummary> =>
  api.get('/attendance/summary', { params: { student_id: studentId, term_id: termId } }).then(r => r.data);

// Classes the caller can mark attendance for — scoped to their own
// ClassTeacher assignment(s) unless they hold attendance.approve (the
// backend returns the full school-wide list for those callers instead).
export const listMyAttendanceClasses = (termId: string): Promise<SchoolClass[]> =>
  api.get('/attendance/my-classes', { params: { term_id: termId } }).then(r => r.data);

// Every visible class' marking status for one calendar day — "who's marked,
// who hasn't," same scope as listMyAttendanceClasses.
export const getMarkingStatus = (calendarId: string): Promise<ClassMarkingStatus[]> =>
  api.get('/attendance/marking-status', { params: { calendar_id: calendarId } }).then(r => r.data);

// ── Chronic-absenteeism early warning ───────────────────────────────────────

export type RiskTier = 'WATCH' | 'AT_RISK' | 'SEVERE';

export interface AtRiskStudent {
  student_id: string;
  name: string;
  class_id: string | null;
  class_name: string | null;
  present: number;
  total: number;
  rate: number;
  tier: RiskTier;
}

export const getAtRiskStudents = (termId: string): Promise<AtRiskStudent[]> =>
  api.get('/attendance/at-risk', { params: { term_id: termId } }).then(r => r.data);

// ── Guardian/student absence excuse requests (staff side) ──────────────────

export const listPendingExcuseRequests = (): Promise<ExcuseRequest[]> =>
  api.get('/attendance/excuse-requests').then(r => r.data);

export const reviewExcuseRequest = (
  requestId: string,
  data: { status: 'APPROVED' | 'REJECTED'; review_notes?: string; override_reason?: string },
): Promise<ExcuseRequest> =>
  api.patch(`/attendance/excuse-requests/${requestId}/review`, data).then(r => r.data);

// ── Trends + export ──────────────────────────────────────────────────────────

export interface AttendanceTrendPoint {
  date: string;
  present: number;
  total: number;
  rate: number;
}

export const getAttendanceTrend = (termId: string, classId?: string): Promise<AttendanceTrendPoint[]> =>
  api.get('/attendance/trends', { params: { term_id: termId, ...(classId ? { class_id: classId } : {}) } }).then(r => r.data);

export const getAttendanceExportBlob = (
  termId: string, fmt: 'csv' | 'excel' | 'pdf', classId?: string,
): Promise<Blob> =>
  api.get('/attendance/export', {
    params: { term_id: termId, fmt, ...(classId ? { class_id: classId } : {}) },
    responseType: 'blob',
  }).then(r => r.data);
