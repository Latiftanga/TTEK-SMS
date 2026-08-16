import { api } from './client';

export type HouseGender = 'MALE' | 'FEMALE' | 'MIXED';
export type ExeatStatus = 'PENDING' | 'APPROVED' | 'REJECTED' | 'RETURNED';
export type ExeatType = 'INTERNAL' | 'EXTERNAL';

export interface RollCall {
  id: string;
  house_id: string;
  school_calendar_id: string;
  recorded_by_id: string;
  recorded_at: string;
  total_expected: number;
  total_present: number;
  notes: string | null;
}

export interface Room {
  id: string;
  house_id: string;
  room_number: string;
  capacity: number | null;
  room_type: string;
}

export interface House {
  id: string;
  school_id: string;
  name: string;
  code: string;
  gender: HouseGender;
  capacity: number | null;
  color: string | null;
  is_active: boolean;
  rooms: Room[];
}

export interface AssignmentRead {
  id: string;
  student_id: string;
  house_id: string;
  room_id: string | null;
  academic_year_id: string;
  assigned_at: string;
  vacated_at: string | null;
}

export interface ExeatRead {
  id: string;
  student_id: string;
  student_name: string | null;
  admission_number: string | null;
  exeat_type: ExeatType;
  reason: string;
  destination: string;
  departure_date: string;
  return_date: string;
  status: ExeatStatus;
  approved_by_id: string | null;
  actual_return_date: string | null;
  created_at: string;
}

export interface HouseMasterRead {
  id: string; house_id: string; staff_member_id: string; academic_year_id: string; is_active: boolean;
}

export const listHouses = (): Promise<House[]> =>
  api.get('/housing/houses').then(r => r.data);

export const assignHouseMaster = (
  houseId: string,
  req: { staff_member_id: string; academic_year_id: string }
): Promise<HouseMasterRead> =>
  api.post(`/housing/houses/${houseId}/master`, req).then(r => r.data);

export const getHouse = (id: string): Promise<House> =>
  api.get(`/housing/houses/${id}`).then(r => r.data);

export const createHouse = (req: {
  name: string; code: string; gender: HouseGender;
  capacity?: number | null; color?: string | null;
}): Promise<House> => api.post('/housing/houses', req).then(r => r.data);

export const updateHouse = (houseId: string, req: {
  name?: string; capacity?: number | null; color?: string | null; is_active?: boolean;
}): Promise<House> => api.patch(`/housing/houses/${houseId}`, req).then(r => r.data);

export const addRoom = (houseId: string, req: {
  room_number: string; capacity?: number | null; room_type?: string;
}): Promise<Room> => api.post(`/housing/houses/${houseId}/rooms`, req).then(r => r.data);

export const updateRoom = (houseId: string, roomId: string, req: {
  room_number?: string; capacity?: number | null; room_type?: string;
}): Promise<Room> => api.patch(`/housing/houses/${houseId}/rooms/${roomId}`, req).then(r => r.data);

export const getStudentAssignment = (studentId: string, yearId: string): Promise<AssignmentRead | null> =>
  api.get(`/housing/students/${studentId}/assignment`, { params: { year_id: yearId } }).then(r => r.data);

export const createAssignment = (req: {
  student_id: string; house_id: string; room_id?: string | null;
  academic_year_id: string; assigned_at: string;
}): Promise<AssignmentRead> => api.post('/housing/assignments', req).then(r => r.data);

export const vacateAssignment = (assignmentId: string, vacated_at: string): Promise<AssignmentRead> =>
  api.patch(`/housing/assignments/${assignmentId}/vacate`, { vacated_at }).then(r => r.data);

export const recordRollCall = (req: {
  house_id: string; school_calendar_id: string;
  total_expected: number; total_present: number; notes?: string;
}): Promise<RollCall> => api.post('/housing/roll-calls', req).then(r => r.data);

export const listRollCalls = (houseId: string): Promise<RollCall[]> =>
  api.get('/housing/roll-calls', { params: { house_id: houseId } }).then(r => r.data);

export interface StudentInHouseRead {
  assignment_id: string;
  student_id: string;
  student_name: string;
  admission_number: string;
  gender: string | null;
  room_number: string | null;
  assigned_at: string;
}

export const listMyHouses = (): Promise<House[]> =>
  api.get('/housing/houses/mine').then(r => r.data);

export const listHouseStudents = (houseId: string): Promise<StudentInHouseRead[]> =>
  api.get(`/housing/houses/${houseId}/students`).then(r => r.data);

export const listPendingExeats = (): Promise<ExeatRead[]> =>
  api.get('/housing/exeats/pending').then(r => r.data);

export const listHouseExeats = (houseId: string): Promise<ExeatRead[]> =>
  api.get('/housing/exeats/pending', { params: { house_id: houseId } }).then(r => r.data);

export const listStudentExeats = (studentId: string): Promise<ExeatRead[]> =>
  api.get(`/housing/students/${studentId}/exeats`).then(r => r.data);

export const createExeat = (req: {
  student_id: string; exeat_type: ExeatType; reason: string; destination: string;
  departure_date: string; return_date: string;
}): Promise<ExeatRead> => api.post('/housing/exeats', req).then(r => r.data);

export const approveExeat = (exeatId: string, status: 'APPROVED' | 'REJECTED'): Promise<ExeatRead> =>
  api.patch(`/housing/exeats/${exeatId}/approve`, { status }).then(r => r.data);

export const recordReturn = (exeatId: string, actual_return_date: string): Promise<ExeatRead> =>
  api.patch(`/housing/exeats/${exeatId}/return`, { actual_return_date }).then(r => r.data);
