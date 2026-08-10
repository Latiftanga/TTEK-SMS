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

// A student's diagnostic-assessment history — category=DIAGNOSTIC scores are
// already fully excluded from the report card/transcript/class rank, so this
// is the only place they're visible at all. No letter grade — diagnostics
// were never meant to be graded like coursework, this is a raw record of
// what was found. Full lifetime history, no term filter.
export interface DiagnosticRecord {
  id: string;
  assessment_name: string;
  subject_name: string;
  recorded_date: string;
  raw_score: number;
  max_score: number;
  notes: string | null;
}

export const listDiagnosticRecords = (student_id: string): Promise<DiagnosticRecord[]> =>
  api.get(`/students/${student_id}/diagnostics`).then(r => r.data);

// Classes the caller can view/generate report cards for — scoped to their
// own ClassTeacher assignment(s) unless they hold assessments.approve_scores.
export const listMyReportClasses = (term_id: string): Promise<SchoolClass[]> =>
  api.get('/report-cards/my-classes', { params: { term_id } }).then(r => r.data);
