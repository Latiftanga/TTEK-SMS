import client from './client';

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

export interface TeacherDashboard {
  view: 'teacher';
  greeting_name: string;
  today_iso: string;
  my_class: ClassSnapshot | null;
  pending_score_assessments: number;
}

export interface ClassAttendanceLine {
  class_id: string;
  name: string;
  total: number;
  present: number;
  pct: number;
}

export interface AdminDashboard {
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

export interface ApproverDashboard {
  view: 'approver';
  greeting_name: string;
  pending_approvals: number;
  assessments_this_term: number;
}

export interface FinanceDashboard {
  view: 'finance';
  greeting_name: string;
  term_expected: number;
  term_collected: number;
  collection_pct: number;
  payments_today: number;
  outstanding_students: number;
}

export type DashboardData = TeacherDashboard | AdminDashboard | ApproverDashboard | FinanceDashboard;

export async function getDashboard(): Promise<DashboardData> {
  const { data } = await client.get<DashboardData>('/dashboard');
  return data;
}
