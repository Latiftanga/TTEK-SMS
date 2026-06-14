import client from './client';

export type Gender = 'MALE' | 'FEMALE';

export interface StaffSummary {
  id: string;
  school_id: string;
  staff_number: string;
  first_name: string;
  middle_name: string | null;
  last_name: string;
  display_name: string;
  gender: Gender | null;
  phone: string | null;
  email: string | null;
  position_id: string | null;
  position_name: string | null;
  department: string | null;
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
  national_id: string | null;
  photo_path: string | null;
  qualifications: Qualification[];
  emergency_contacts: EmergencyContact[];
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
  national_id?: string;
  phone?: string;
  email?: string;
  position_id?: string;
  department?: string;
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
    phone: string;
    email: string;
    position_id: string;
    department: string;
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
