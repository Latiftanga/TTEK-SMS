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
}

export type ReportFormat = 'BASIC' | 'SHS' | 'ECM';

export const getMyPortalProfile = (): Promise<PortalProfile> =>
  api.get('/portal/me').then(r => r.data);

export const listMyTermEnrollments = (): Promise<PortalTermEnrollment[]> =>
  api.get('/portal/term-enrollments').then(r => r.data);

export const getMyReportCardBlob = (enrollmentId: string, format: ReportFormat = 'BASIC'): Promise<Blob> =>
  api.get(`/portal/report-cards/${enrollmentId}`, { params: { format }, responseType: 'blob' }).then(r => r.data);
