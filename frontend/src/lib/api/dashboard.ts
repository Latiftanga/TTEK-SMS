import client from './client';

export interface RoleBadge {
  role: 'teacher' | 'subject_teacher' | 'housemaster' | 'approver' | 'finance';
  label: string;
  detail: string;
  href: string;
}

// Present on every dashboard response regardless of which view is primary —
// a staff member can hold several responsibilities at once (e.g. Class
// Teacher + Housemaster), but the backend only ever returns ONE full view
// (chosen by seniority). is_class_teacher is computed independently of
// which view won (drives the sidebar's classTeacherOnly nav gating);
// other_roles is a compact "you also..." strip for every other
// responsibility the primary view doesn't already cover.
export interface DashboardExtras {
  is_class_teacher: boolean;
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

export interface TeacherDashboard extends DashboardExtras {
  view: 'teacher';
  greeting_name: string;
  today_iso: string;
  my_classes: ClassSnapshot[];
  pending_score_assessments: number;
}

export interface ClassAttendanceLine {
  class_id: string;
  name: string;
  total: number;
  present: number;
  pct: number;
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
  total_residents: number;
  pending_exeats: number;
  off_campus_count: number;
}

export interface HousemasterDashboard extends DashboardExtras {
  view: 'housemaster';
  greeting_name: string;
  my_houses: HouseSnapshot[];
}

export type DashboardData = TeacherDashboard | AdminDashboard | ApproverDashboard | FinanceDashboard | HousemasterDashboard;

export async function getDashboard(): Promise<DashboardData> {
  const { data } = await client.get<DashboardData>('/dashboard');
  return data;
}
