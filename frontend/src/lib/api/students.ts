import client from './client';

export type Gender = 'MALE' | 'FEMALE';

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
}

export async function listStudents(params: {
  class_id?: string;
  term_id?: string;
  search?: string;
  active_only?: boolean;
  skip?: number;
  limit?: number;
}): Promise<StudentSummary[]> {
  const { data } = await client.get<StudentSummary[]>('/students', { params });
  return data;
}

export async function enrollStudent(req: {
  student_id: string;
  class_id: string;
  academic_term_id: string;
}): Promise<{ id: string; class_display_name: string }> {
  const { data } = await client.post('/students/term-enrollments', req);
  return data;
}

export async function bulkEnrollStudents(
  items: { student_id: string; class_id: string; academic_term_id: string }[]
): Promise<{ enrolled: number; skipped: number }> {
  const { data } = await client.post('/students/bulk-term-enrollments', { items });
  return data;
}
