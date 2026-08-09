import { api } from './client';
import type { SchoolClass } from './academic';

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
  status: string;
}

export const listClassEnrollments = (class_id: string, term_id: string): Promise<EnrollmentForReport[]> =>
  api.get('/report-cards/enrollments', { params: { class_id, term_id } }).then(r => r.data);

export const getReportCardBlob = (enrollment_id: string): Promise<Blob> =>
  api.get(`/report-cards/${enrollment_id}`, { responseType: 'blob' }).then(r => r.data);

export const queueBulkReport = (class_id: string, academic_term_id: string): Promise<BulkReportJob> =>
  api.post('/report-cards/bulk', { class_id, academic_term_id }).then(r => r.data);

export const downloadBulkReport = (job_id: string): Promise<Blob> =>
  api.get(`/report-cards/bulk/${job_id}/download`, { responseType: 'blob' }).then(r => r.data);

export const getTranscriptBlob = (student_id: string): Promise<Blob> =>
  api.get(`/students/${student_id}/transcript`, { responseType: 'blob' }).then(r => r.data);

// Classes the caller can view/generate report cards for — scoped to their
// own ClassTeacher assignment(s) unless they hold assessments.approve_scores.
export const listMyReportClasses = (term_id: string): Promise<SchoolClass[]> =>
  api.get('/report-cards/my-classes', { params: { term_id } }).then(r => r.data);
