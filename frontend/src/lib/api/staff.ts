import client from './client';

export type Gender = 'MALE' | 'FEMALE';
export type StaffCategory = 'TEACHING' | 'NON_TEACHING';
export type EmploymentType = 'PERMANENT' | 'CONTRACT' | 'NATIONAL_SERVICE' | 'INTERN';
export type MaritalStatus = 'SINGLE' | 'MARRIED' | 'DIVORCED' | 'WIDOWED' | 'SEPARATED';

export interface StaffSummary {
  id: string;
  school_id: string;
  staff_number: string;
  first_name: string;
  middle_name: string | null;
  last_name: string;
  display_name: string;
  gender: Gender | null;
  staff_category: StaffCategory | null;
  employment_type: EmploymentType | null;
  phone: string | null;
  email: string | null;
  position_ids: string[];
  position_names: string[];
  is_active: boolean;
  joined_date: string | null;
}

export interface Qualification {
  id: string;
  institution: string;
  qualification_type: string;
  field_of_study: string | null;
  year_obtained: number | null;
}

export interface EmergencyContact {
  id: string;
  name: string;
  contact_type: string;
  phone: string;
  email: string | null;
}

export interface StaffDetail extends StaffSummary {
  date_of_birth: string | null;
  marital_status: MaritalStatus | null;
  national_id: string | null;
  ssnit_number: string | null;
  address: string | null;
  photo_path: string | null;
  qualifications: Qualification[];
  emergency_contacts: EmergencyContact[];
}

export interface Position {
  id: string;
  name: string;
}

export interface Promotion {
  id: string;
  staff_member_id: string;
  staff_category: 'TEACHING' | 'NON_TEACHING';
  non_teaching_group: string | null;
  from_grade: string | null;
  to_grade: string;
  effective_date: string;
  reason: string | null;
  created_at: string;
}

export type LeaveStatus = 'PENDING' | 'APPROVED' | 'REJECTED' | 'CANCELLED';

export interface Leave {
  id: string;
  staff_member_id: string;
  leave_type: string;
  start_date: string;
  end_date: string;
  days_count: number;
  reason: string | null;
  status: LeaveStatus;
  approved_by_id: string | null;
  reviewed_at: string | null;
  notes: string | null;
  created_at: string;
}

export async function listStaff(params?: {
  active_only?: boolean;
  skip?: number;
  limit?: number;
}): Promise<StaffSummary[]> {
  const { data } = await client.get<StaffSummary[]>('/staff', { params });
  return data;
}

export async function getStaff(id: string): Promise<StaffDetail> {
  const { data } = await client.get<StaffDetail>(`/staff/${id}`);
  return data;
}

export async function createStaff(req: {
  staff_number: string;
  first_name: string;
  middle_name?: string;
  last_name: string;
  date_of_birth?: string;
  gender?: Gender;
  staff_category?: StaffCategory;
  employment_type?: EmploymentType;
  marital_status?: MaritalStatus;
  national_id?: string;
  ssnit_number?: string;
  address?: string;
  phone?: string;
  email?: string;
  position_ids?: string[];
  joined_date?: string;
}): Promise<StaffDetail> {
  const { data } = await client.post<StaffDetail>('/staff', req);
  return data;
}

export async function updateStaff(
  id: string,
  req: Partial<{
    first_name: string;
    middle_name: string;
    last_name: string;
    gender: Gender;
    staff_category: StaffCategory;
    employment_type: EmploymentType;
    marital_status: MaritalStatus;
    national_id: string;
    ssnit_number: string;
    address: string;
    phone: string;
    email: string;
    position_ids: string[];
    is_active: boolean;
  }>
): Promise<StaffDetail> {
  const { data } = await client.patch<StaffDetail>(`/staff/${id}`, req);
  return data;
}

export async function addQualification(
  staffId: string,
  req: {
    institution: string;
    qualification_type: string;
    field_of_study?: string;
    year_obtained?: number;
  }
): Promise<Qualification> {
  const { data } = await client.post<Qualification>(`/staff/${staffId}/qualifications`, req);
  return data;
}

export async function deleteQualification(staffId: string, qualId: string): Promise<void> {
  await client.delete(`/staff/${staffId}/qualifications/${qualId}`);
}

export async function addEmergencyContact(
  staffId: string,
  req: { name: string; contact_type: string; phone: string; email?: string }
): Promise<EmergencyContact> {
  const { data } = await client.post<EmergencyContact>(
    `/staff/${staffId}/emergency-contacts`,
    req
  );
  return data;
}

export async function deleteEmergencyContact(staffId: string, contactId: string): Promise<void> {
  await client.delete(`/staff/${staffId}/emergency-contacts/${contactId}`);
}

export async function listPositions(): Promise<Position[]> {
  const { data } = await client.get<Position[]>('/schools/me/positions');
  return data;
}

export async function listPromotions(staffId: string): Promise<Promotion[]> {
  const { data } = await client.get<Promotion[]>(`/staff/${staffId}/promotions`);
  return data;
}

export async function addPromotion(
  staffId: string,
  req: {
    staff_category: string;
    non_teaching_group?: string;
    from_grade?: string;
    to_grade: string;
    effective_date: string;
    reason?: string;
  }
): Promise<Promotion> {
  const { data } = await client.post<Promotion>(`/staff/${staffId}/promotions`, req);
  return data;
}

export async function listLeave(staffId: string): Promise<Leave[]> {
  const { data } = await client.get<Leave[]>(`/staff/${staffId}/leave`);
  return data;
}

export async function submitLeave(
  staffId: string,
  req: {
    leave_type: string;
    start_date: string;
    end_date: string;
    days_count: number;
    reason?: string;
  }
): Promise<Leave> {
  const { data } = await client.post<Leave>(`/staff/${staffId}/leave`, req);
  return data;
}

export async function listPendingLeave(): Promise<Leave[]> {
  const { data } = await client.get<Leave[]>('/staff/leave/pending');
  return data;
}

export async function reviewLeave(
  leaveId: string,
  req: { status: 'APPROVED' | 'REJECTED'; notes?: string }
): Promise<Leave> {
  const { data } = await client.patch<Leave>(`/staff/leave/${leaveId}/review`, req);
  return data;
}

export interface ImportRowResult {
  row: number;
  ref: string | null;
  status: string;
  error: string | null;
  warning: string | null;
}

export interface ImportBatchResult {
  batch_id: string;
  total_rows: number;
  created: number;
  failed: number;
  errors: ImportRowResult[];
  warnings: ImportRowResult[];
}

export async function downloadImportTemplate(): Promise<void> {
  const response = await client.get('/staff/import/template', { responseType: 'blob' });
  const cd = response.headers['content-disposition'] as string | undefined;
  const match = cd?.match(/filename="?([^";]+)"?/);
  const filename = match?.[1] ?? 'staff_import_template.xlsx';
  const url = URL.createObjectURL(new Blob([response.data]));
  const a = Object.assign(document.createElement('a'), { href: url, download: filename });
  a.click();
  URL.revokeObjectURL(url);
}

export async function bulkImportStaff(file: File): Promise<ImportBatchResult> {
  const form = new FormData();
  form.append('file', file);
  const { data } = await client.post<ImportBatchResult>('/staff/import', form);
  return data;
}

export interface TempPasswordResult {
  temporary_password: string;
  display_name: string;
}

export async function resetStaffPassword(staffId: string): Promise<TempPasswordResult> {
  const { data } = await client.post<TempPasswordResult>(`/staff/${staffId}/reset-password`);
  return data;
}
