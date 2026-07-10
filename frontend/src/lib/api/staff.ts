import client from './client';

export type Gender = 'MALE' | 'FEMALE';
export type EmploymentType = 'PERMANENT' | 'CONTRACT' | 'NATIONAL_SERVICE' | 'INTERN';
export type MaritalStatus = 'SINGLE' | 'MARRIED' | 'DIVORCED' | 'WIDOWED' | 'SEPARATED';
export type StaffType = 'TEACHING' | 'NON_TEACHING';

export interface StaffCategory {
  id: string;
  name: string;
  code: string;
  staff_type: StaffType | null;
  is_template: boolean;
  is_active: boolean;
  school_id: string | null;
}

export interface StaffRank {
  id: string;
  title: string;
  category_id: string;
  is_template: boolean;
  is_active: boolean;
  school_id: string | null;
}

export interface StaffSummary {
  id: string;
  school_id: string;
  staff_number: string;
  first_name: string;
  middle_name: string | null;
  last_name: string;
  display_name: string;
  category_id: string | null;
  category_name: string | null;
  staff_type: StaffType | null;
  gender: Gender | null;
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
  has_account: boolean;
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
  from_rank_id: string | null;
  to_rank_id: string | null;
  from_rank_title: string | null;
  to_rank_title: string | null;
  effective_date: string;
  reason: string | null;
  created_at: string;
}

export type LeaveStatus = 'PENDING' | 'APPROVED' | 'REJECTED' | 'CANCELLED';

export interface Leave {
  id: string;
  staff_member_id: string;
  staff_name: string | null;
  staff_number: string | null;
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

export interface StaffListParams {
  active_only?: boolean;
  skip?: number;
  limit?: number;
  search?: string;
  gender?: string;
  category_id?: string;
}

export async function listStaff(params?: StaffListParams): Promise<StaffSummary[]> {
  const { data } = await client.get<StaffSummary[]>('/staff', { params });
  return data;
}

export interface StaffListPage {
  items: StaffSummary[];
  total: number;
}

export async function listStaffPage(params: StaffListParams = {}): Promise<StaffListPage> {
  const res = await client.get<StaffSummary[]>('/staff', { params });
  return { items: res.data, total: Number(res.headers['x-total-count'] ?? res.data.length) };
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
  category_id?: string;
  date_of_birth?: string;
  gender?: Gender;
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
    category_id: string;
    date_of_birth: string;
    joined_date: string;
    gender: Gender;
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

export async function updateQualification(
  staffId: string,
  qualId: string,
  req: {
    institution?: string;
    qualification_type?: string;
    field_of_study?: string;
    year_obtained?: number;
  }
): Promise<Qualification> {
  const { data } = await client.patch<Qualification>(`/staff/${staffId}/qualifications/${qualId}`, req);
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

export async function listCategories(): Promise<StaffCategory[]> {
  const { data } = await client.get<StaffCategory[]>('/staff/categories');
  return data;
}

export async function listRanks(categoryId: string): Promise<StaffRank[]> {
  const { data } = await client.get<StaffRank[]>('/staff/ranks', { params: { category_id: categoryId } });
  return data;
}

export async function listPromotions(staffId: string): Promise<Promotion[]> {
  const { data } = await client.get<Promotion[]>(`/staff/${staffId}/promotions`);
  return data;
}

export async function addPromotion(
  staffId: string,
  req: {
    from_rank_id?: string;
    to_rank_id: string;
    effective_date: string;
    reason?: string;
  }
): Promise<Promotion> {
  const { data } = await client.post<Promotion>(`/staff/${staffId}/promotions`, req);
  return data;
}

export async function updatePromotion(
  staffId: string,
  promotionId: string,
  req: {
    from_rank_id?: string;
    to_rank_id?: string;
    effective_date?: string;
    reason?: string;
  }
): Promise<Promotion> {
  const { data } = await client.patch<Promotion>(`/staff/${staffId}/promotions/${promotionId}`, req);
  return data;
}

export async function deletePromotion(staffId: string, promotionId: string): Promise<void> {
  await client.delete(`/staff/${staffId}/promotions/${promotionId}`);
}

export interface StaffExportParams {
  category_id?: string;
  active_only?: boolean;
  search?: string;
  gender?: string;
}

export async function exportStaffExcel(params?: StaffExportParams): Promise<void> {
  const response = await client.get('/staff/export/excel', { params, responseType: 'blob' });
  const url = URL.createObjectURL(new Blob([response.data]));
  const a = Object.assign(document.createElement('a'), { href: url, download: 'staff_register.xlsx' });
  a.click();
  URL.revokeObjectURL(url);
}

export interface StaffCustomExportParams extends StaffExportParams {
  fields: string;
  fmt: 'csv' | 'excel';
}

export async function customExportStaff(params: StaffCustomExportParams): Promise<void> {
  const response = await client.get('/staff/export/custom', { params, responseType: 'blob' });
  const ext = params.fmt === 'excel' ? 'xlsx' : 'csv';
  const url = URL.createObjectURL(new Blob([response.data]));
  const a = Object.assign(document.createElement('a'), { href: url, download: `staff.${ext}` });
  a.click();
  URL.revokeObjectURL(url);
}

export async function exportStaffPdf(params?: StaffExportParams): Promise<void> {
  const response = await client.get('/staff/export/pdf', { params, responseType: 'blob' });
  const url = URL.createObjectURL(new Blob([response.data]));
  const a = Object.assign(document.createElement('a'), { href: url, download: 'staff_register.pdf' });
  a.click();
  URL.revokeObjectURL(url);
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

export interface InviteResult {
  invitation_token: string;
  invite_link: string;
  sms_sent: boolean;
}

export async function inviteStaff(staffId: string): Promise<InviteResult> {
  const { data } = await client.post<InviteResult>(`/staff/${staffId}/invite`);
  return data;
}

export interface ClassTeacherAssignment {
  class_id: string;
  class_name: string;
  academic_year_id: string;
  academic_year_name: string;
  is_active: boolean;
}

export interface SubjectAssignment {
  class_id: string;
  class_name: string;
  subject_id: string;
  subject_name: string;
  academic_term_id: string;
  term_name: string;
  academic_year_name: string;
  is_active: boolean;
}

export interface HouseAssignment {
  house_id: string;
  house_name: string;
  house_code: string;
  academic_year_id: string;
  academic_year_name: string;
  is_active: boolean;
}

export interface StaffResponsibilities {
  class_teacher: ClassTeacherAssignment | null;
  subject_assignments: SubjectAssignment[];
  house_assignments: HouseAssignment[];
}

export async function getStaffResponsibilities(staffId: string): Promise<StaffResponsibilities> {
  const { data } = await client.get<StaffResponsibilities>(`/staff/${staffId}/responsibilities`);
  return data;
}

export type PermissionSource = 'override' | 'position' | 'default_deny';

export interface StaffPermission {
  module: string;
  action: string;
  effective: boolean;
  source: PermissionSource;
  override_is_allowed: boolean | null;
}

export const listStaffPermissions = (staffId: string): Promise<StaffPermission[]> =>
  client.get<StaffPermission[]>(`/staff/${staffId}/permissions`).then(r => r.data);

export const setStaffPermission = (
  staffId: string,
  module: string,
  action: string,
  is_allowed: boolean,
): Promise<StaffPermission[]> =>
  client.post<StaffPermission[]>(`/staff/${staffId}/permissions`, { module, action, is_allowed }).then(r => r.data);

export const clearStaffPermission = (
  staffId: string,
  module: string,
  action: string,
): Promise<StaffPermission[]> =>
  client.delete<StaffPermission[]>(`/staff/${staffId}/permissions/${module}/${action}`).then(r => r.data);
