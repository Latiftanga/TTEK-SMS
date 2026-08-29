import client from './client';
import type { ScheduleEntry } from './timetable';

export interface RoleBadge {
  role: 'teacher' | 'subject_teacher' | 'housemaster' | 'approver' | 'finance';
  label: string;
  detail: string;
  href: string;
}

// Present on every dashboard response regardless of which view is primary —
// a staff member can hold several responsibilities at once (e.g. Class
// Teacher + Housemaster). The three booleans are computed independently of
// which view won — they drive the sidebar's teachingOnly/classTeacherOnly/
// housemasterOnly nav gating, not the `view` string itself. other_roles is a
// compact "you also..." strip, only populated for the admin/finance/
// approver views (the 'staff' view already shows all three as full sections).
export interface DashboardExtras {
  is_class_teacher: boolean;
  is_subject_teacher: boolean;
  is_housemaster: boolean;
  other_roles: RoleBadge[];
}

export interface AbsentStudent {
  id: string;
  name: string;
  admission_number: string;
}

export interface ClassSnapshot {
  id: string;
  name: string;
  student_count: number;
  present_today: number;
  absent_today: number;
  attendance_marked_today: boolean;
  absent_students: AbsentStudent[];
}

export interface SubjectSnapshot {
  class_id: string;
  class_name: string;
  subject_id: string;
  subject_name: string;
  pending_score_assessments: number;
}

export interface ClassAttendanceLine {
  class_id: string;
  name: string;
  total: number;
  present: number;
  pct: number;
  marked: boolean;
}

export interface AdminDashboard extends DashboardExtras {
  view: 'admin';
  greeting_name: string;
  school_name: string;
  total_students: number;
  today_present: number;
  today_total: number;
  attendance_pct: number;
  term_collection_pct: number;
  term_collected: number;
  term_expected: number;
  pending_approvals: number;
  class_attendance: ClassAttendanceLine[];
}

export interface ApproverDashboard extends DashboardExtras {
  view: 'approver';
  greeting_name: string;
  pending_approvals: number;
  assessments_this_term: number;
}

export interface FinanceDashboard extends DashboardExtras {
  view: 'finance';
  greeting_name: string;
  term_expected: number;
  term_collected: number;
  collection_pct: number;
  payments_today: number;
  outstanding_students: number;
}

export interface HouseSnapshot {
  id: string;
  name: string;
  capacity: number | null;
  total_residents: number;
  pending_exeats: number;
  off_campus_count: number;
}

// The composed dashboard for anyone who isn't admin/finance/approver —
// replaces the old separate TeacherDashboard/HousemasterDashboard. Each
// section is populated independently from the caller's real assignment
// rows, not from a single "winning" role.
export interface StaffDashboard extends DashboardExtras {
  view: 'staff';
  greeting_name: string;
  today_iso: string;
  my_classes: ClassSnapshot[];
  pending_score_assessments: number;
  my_subjects: SubjectSnapshot[];
  my_houses: HouseSnapshot[];
  // "What do I teach tomorrow?" — tomorrow_schedule is always [] when
  // tomorrow_is_school_day is false (a real holiday/weekend), even if the
  // caller's recurring weekly timetable would otherwise have entries.
  tomorrow_schedule: ScheduleEntry[];
  tomorrow_is_school_day: boolean;
}

export type DashboardData = StaffDashboard | AdminDashboard | ApproverDashboard | FinanceDashboard;

export async function getDashboard(): Promise<DashboardData> {
  const { data } = await client.get<DashboardData>('/dashboard');
  return data;
}
