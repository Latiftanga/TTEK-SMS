import { api } from './client';

export interface EnrollmentForReport {
  enrollment_id: string;
  student_id: string;
  admission_number: string;
  display_name: string;
  gender: 'MALE' | 'FEMALE' | null;
  class_id: string | null;
  class_display_name: string | null;
}

export interface BulkReportJob {
  job_id: string;
  class_id: string;
  academic_term_id: string;
  format: string;
  status: string;
}

export type ReportFormat = 'BASIC' | 'SHS' | 'ECM';

export const listClassEnrollments = (class_id: string, term_id: string): Promise<EnrollmentForReport[]> =>
  api.get('/report-cards/enrollments', { params: { class_id, term_id } }).then(r => r.data);

export const getReportCardBlob = (enrollment_id: string, format: ReportFormat): Promise<Blob> =>
  api.get(`/report-cards/${enrollment_id}`, { params: { format }, responseType: 'blob' }).then(r => r.data);

export const queueBulkReport = (class_id: string, academic_term_id: string, format: ReportFormat): Promise<BulkReportJob> =>
  api.post('/report-cards/bulk', { class_id, academic_term_id, format }).then(r => r.data);

export const downloadBulkReport = (job_id: string): Promise<Blob> =>
  api.get(`/report-cards/bulk/${job_id}/download`, { responseType: 'blob' }).then(r => r.data);
