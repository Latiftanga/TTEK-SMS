import { api } from './client';

export interface PortalProfile {
  student_id: string;
  admission_number: string;
  display_name: string;
  current_class_name: string | null;
  school_name: string;
}

export interface PortalTermEnrollment {
  id: string;
  academic_term_id: string;
  term_name: string;
  academic_year_name: string;
  is_current: boolean;
  is_published: boolean;
  // null = no fees assigned for this term yet, not a zero balance.
  fee_total_due: string | null;
  fee_total_paid: string | null;
  fee_balance: string | null;
  fee_last_payment_date: string | null;
}

export const getMyPortalProfile = (): Promise<PortalProfile> =>
  api.get('/portal/me').then(r => r.data);

// Guardian accounts only — the children they can switch between.
export const listMyChildren = (): Promise<PortalProfile[]> =>
  api.get('/portal/children').then(r => r.data);

// studentId is only needed (and only accepted server-side) for a guardian account —
// a student's own login resolves to themself regardless of what's passed here.
export const listMyTermEnrollments = (studentId?: string): Promise<PortalTermEnrollment[]> =>
  api.get('/portal/term-enrollments', { params: studentId ? { student_id: studentId } : {} }).then(r => r.data);

export const getMyReportCardBlob = (enrollmentId: string, studentId?: string): Promise<Blob> =>
  api.get(`/portal/report-cards/${enrollmentId}`, {
    params: studentId ? { student_id: studentId } : {},
    responseType: 'blob',
  }).then(r => r.data);
