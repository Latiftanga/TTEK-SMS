import { api } from './client';

export type Gender = 'MALE' | 'FEMALE';
export type OrphanStatus = 'NONE' | 'HALF_ORPHAN' | 'FULL_ORPHAN';

export interface StudentSummary {
  id: string;
  school_id: string;
  admission_number: string;
  first_name: string;
  middle_name: string | null;
  last_name: string;
  display_name: string;
  gender: Gender | null;
  is_active: boolean;
  is_boarding: boolean;
  current_class_name: string | null;
  current_class_id: string | null;
}

export interface MedicalRecord {
  id: string;
  blood_group: string | null;
  allergies: string | null;
  chronic_conditions: string | null;
  medications: string | null;
  emergency_notes: string | null;
}

export interface Guardian {
  guardian_id: string;
  first_name: string;
  last_name: string;
  phone: string;
  email: string | null;
  address: string | null;
  occupation: string | null;
  relation_type: string;
  is_primary: boolean;
}

export interface StudentDetail extends StudentSummary {
  date_of_birth: string | null;
  nationality: string | null;
  religion: string | null;
  hometown: string | null;
  residential_address: string | null;
  nhis_number: string | null;
  ghana_card_number: string | null;
  orphan_status: OrphanStatus;
  disability: string | null;
  photo_path: string | null;
  has_portal_access: boolean;
  medical_record: MedicalRecord | null;
  guardians: Guardian[];
}

export interface PortalAccessResult {
  has_portal_access: boolean;
  admission_number: string;
  sms_sent: boolean;
}

export interface StudentClassAssignmentRead {
  id: string;
  student_id: string;
  class_id: string;
  academic_year_id: string;
  class_display_name: string;
  is_active: boolean;
  created_at: string;
}

export interface TermEnrollmentRead {
  id: string;
  student_id: string;
  academic_term_id: string;
  class_id: string | null;
  class_display_name: string | null;
  is_active: boolean;
  created_at: string;
}

export interface StudentCreate {
  admission_number: string;
  first_name: string;
  middle_name?: string;
  last_name: string;
  date_of_birth?: string;
  gender?: Gender;
  nationality?: string;
  religion?: string;
  hometown?: string;
  residential_address?: string;
  nhis_number?: string;
  ghana_card_number?: string;
  is_boarding?: boolean;
  orphan_status?: OrphanStatus;
  disability?: string;
}

export interface GuardianCreate {
  first_name: string;
  last_name: string;
  phone: string;
  email?: string;
  occupation?: string;
  address?: string;
  relation_type: string;
  is_primary?: boolean;
}

export interface GuardianUpdate {
  first_name?: string;
  last_name?: string;
  phone?: string;
  email?: string | null;
  occupation?: string | null;
  address?: string | null;
  relation_type?: string;
  is_primary?: boolean;
}

export interface MedicalRecordUpsert {
  blood_group?: string;
  allergies?: string;
  chronic_conditions?: string;
  medications?: string;
  emergency_notes?: string;
}

export interface ImportBatchResult {
  batch_id: string;
  total_rows: number;
  created: number;
  skipped: number;
  errors: { row: number; reason: string }[];
}

export interface StudentListParams {
  active_only?: boolean;
  skip?: number;
  limit?: number;
  search?: string;
  class_id?: string;
  term_id?: string;
  gender?: string;
  level?: string;
}

export const listStudents = (params: StudentListParams = {}): Promise<StudentSummary[]> =>
  api.get('/students', { params }).then(r => r.data);

export const getStudent = (id: string): Promise<StudentDetail> =>
  api.get(`/students/${id}`).then(r => r.data);

export const createStudent = (data: StudentCreate): Promise<StudentDetail> =>
  api.post('/students', data).then(r => r.data);

export const updateStudent = (id: string, data: Partial<StudentCreate & { is_active: boolean }>): Promise<StudentDetail> =>
  api.patch(`/students/${id}`, data).then(r => r.data);

export const addGuardian = (studentId: string, data: GuardianCreate): Promise<Guardian> =>
  api.post(`/students/${studentId}/guardians`, data).then(r => r.data);

export const updateGuardian = (studentId: string, guardianId: string, data: GuardianUpdate): Promise<Guardian> =>
  api.patch(`/students/${studentId}/guardians/${guardianId}`, data).then(r => r.data);

export const removeGuardian = (studentId: string, guardianId: string): Promise<void> =>
  api.delete(`/students/${studentId}/guardians/${guardianId}`).then(r => r.data);

export const removeSubjectRegistration = (teId: string, regId: string): Promise<void> =>
  api.delete(`/students/term-enrollments/${teId}/subjects/${regId}`).then(() => undefined);

export const upsertMedical = (studentId: string, data: MedicalRecordUpsert): Promise<MedicalRecord> =>
  api.put(`/students/${studentId}/medical`, data).then(r => r.data);

export interface SubjectRegistrationRead {
  id: string;
  subject_id: string;
  registration_type: 'CORE' | 'ELECTIVE';
}

export const listClassAssignments = (studentId: string): Promise<StudentClassAssignmentRead[]> =>
  api.get(`/students/${studentId}/class-assignments`).then(r => r.data);

export const assignStudentToClass = (req: { student_id: string; class_id: string; academic_year_id: string }): Promise<StudentClassAssignmentRead> =>
  api.post('/students/class-assignments', req).then(r => r.data);

export const bulkAssignStudentsToClass = (items: { student_id: string; class_id: string; academic_year_id: string }[]) =>
  api.post('/students/class-assignments/bulk', { items }).then(r => r.data);

export const listTermEnrollments = (studentId: string): Promise<TermEnrollmentRead[]> =>
  api.get(`/students/${studentId}/term-enrollments`).then(r => r.data);

export const enrollStudent = (req: { student_id: string; academic_term_id: string }): Promise<TermEnrollmentRead> =>
  api.post('/students/term-enrollments', req).then(r => r.data);

export const listSubjectRegistrations = (teId: string): Promise<SubjectRegistrationRead[]> =>
  api.get(`/students/term-enrollments/${teId}/subjects`).then(r => r.data);

export const registerSubjects = (teId: string, items: { subject_id: string; registration_type: string }[]): Promise<SubjectRegistrationRead[]> =>
  api.post(`/students/term-enrollments/${teId}/subjects`, items).then(r => r.data);

export const bulkEnrollStudents = (items: { student_id: string; academic_term_id: string }[]) =>
  api.post('/students/bulk-term-enrollments', { items }).then(r => r.data);

export const downloadImportTemplate = () =>
  api.get('/students/import/template', { responseType: 'blob' }).then(r => r.data);

export const importStudents = (file: File): Promise<ImportBatchResult> => {
  const fd = new FormData();
  fd.append('file', file);
  return api.post('/students/import', fd, { headers: { 'Content-Type': 'multipart/form-data' } }).then(r => r.data);
};

export const exportStudentsCsv = (params: StudentListParams = {}): Promise<Blob> =>
  api.get('/students/export', { params, responseType: 'blob' }).then(r => r.data);

export const grantPortalAccess = (studentId: string): Promise<PortalAccessResult> =>
  api.post<PortalAccessResult>(`/students/${studentId}/grant-portal-access`).then(r => r.data);

export const revokePortalAccess = (studentId: string): Promise<void> =>
  api.delete(`/students/${studentId}/revoke-portal-access`).then(() => undefined);

// ── Transfers ─────────────────────────────────────────────────────────────────

export type TransferStatus = 'PENDING' | 'APPROVED' | 'REJECTED' | 'WITHDRAWN';

export interface TransferRequest {
  id: string;
  student_id: string;
  student_name: string | null;
  admission_number: string | null;
  status: TransferStatus;
  reason: string | null;
  requesting_school_id: string | null;
  reviewed_at: string | null;
  reviewed_by_id: string | null;
  created_at: string;
}

export const createTransferRequest = (
  studentId: string,
  data: { reason?: string },
): Promise<TransferRequest> =>
  api.post(`/students/${studentId}/transfers`, data).then(r => r.data);

export const listPendingTransfers = (): Promise<TransferRequest[]> =>
  api.get('/students/transfers/pending').then(r => r.data);

export const reviewTransfer = (
  transferId: string,
  status: 'APPROVED' | 'REJECTED' | 'WITHDRAWN',
): Promise<TransferRequest> =>
  api.patch(`/students/transfers/${transferId}/review`, { status }).then(r => r.data);
