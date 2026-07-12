import client from './client';

export interface AcademicTerm {
  id: string;
  school_id: string;
  academic_year_id: string;
  term_number: number;
  name: string;
  start_date: string;
  end_date: string;
  is_current: boolean;
  block_owing_students: boolean;
  block_owing_students_set_by: string | null;
  block_owing_students_set_at: string | null;
}

export interface AcademicYear {
  id: string;
  school_id: string;
  name: string;
  start_date: string;
  end_date: string;
  is_current: boolean;
  terms: AcademicTerm[];
}

export interface Programme {
  id: string;
  school_id: string | null;
  code: string;
  name: string;
  is_active: boolean;
}

export interface Subject {
  id: string;
  school_id: string;
  catalogue_id: string | null;
  code: string;
  name: string;
  is_active: boolean;
}

export interface SchoolClass {
  id: string;
  school_id: string;
  level: string;
  year_group: number;
  programme_id: string | null;
  programme_name: string | null;
  stream: string | null;
  capacity: number | null;
  is_active: boolean;
  display_name: string;
}

export interface ClassSubject {
  id: string;
  school_id: string;
  class_id: string;
  subject_id: string;
  is_active: boolean;
}

export interface ClassTeacher {
  id: string;
  school_id: string;
  class_id: string;
  staff_member_id: string;
  academic_year_id: string;
  is_active: boolean;
}

export interface SubjectTeacher {
  id: string;
  school_id: string;
  class_id: string;
  subject_id: string;
  staff_member_id: string;
  academic_term_id: string;
  is_active: boolean;
}

export async function listYears(): Promise<AcademicYear[]> {
  const { data } = await client.get<AcademicYear[]>('/academic/years');
  return data;
}

export async function getCurrentYear(): Promise<AcademicYear | null> {
  const { data } = await client.get<AcademicYear | null>('/academic/years/current');
  return data;
}

export async function createYear(req: {
  name: string;
  start_date: string;
  end_date: string;
}): Promise<AcademicYear> {
  const { data } = await client.post<AcademicYear>('/academic/years', req);
  return data;
}

export async function updateYear(yearId: string, req: {
  name?: string; start_date?: string; end_date?: string;
}): Promise<AcademicYear> {
  const { data } = await client.patch<AcademicYear>(`/academic/years/${yearId}`, req);
  return data;
}

export async function setCurrentYear(yearId: string): Promise<AcademicYear> {
  const { data } = await client.post<AcademicYear>(`/academic/years/${yearId}/set-current`);
  return data;
}

export async function listTerms(yearId: string): Promise<AcademicTerm[]> {
  const { data } = await client.get<AcademicTerm[]>(`/academic/years/${yearId}/terms`);
  return data;
}

export async function createTerm(
  yearId: string,
  req: { term_number: number; name: string; start_date: string; end_date: string }
): Promise<AcademicTerm> {
  const { data } = await client.post<AcademicTerm>(`/academic/years/${yearId}/terms`, req);
  return data;
}

export async function updateTerm(termId: string, req: {
  name?: string; start_date?: string; end_date?: string; block_owing_students?: boolean;
}): Promise<AcademicTerm> {
  const { data } = await client.patch<AcademicTerm>(`/academic/terms/${termId}`, req);
  return data;
}

export async function setCurrentTerm(termId: string): Promise<AcademicTerm> {
  const { data } = await client.post<AcademicTerm>(`/academic/terms/${termId}/set-current`);
  return data;
}

export async function listSubjects(): Promise<Subject[]> {
  const { data } = await client.get<Subject[]>('/academic/subjects');
  return data;
}

export async function createSubject(req: {
  code: string;
  name: string;
  catalogue_id?: string;
}): Promise<Subject> {
  const { data } = await client.post<Subject>('/academic/subjects', req);
  return data;
}

export async function updateSubject(subjectId: string, req: {
  code?: string; name?: string; is_active?: boolean;
}): Promise<Subject> {
  const { data } = await client.patch<Subject>(`/academic/subjects/${subjectId}`, req);
  return data;
}

export async function listAllTerms(): Promise<AcademicTerm[]> {
  const { data } = await client.get<AcademicTerm[]>('/academic/terms');
  return data;
}

export async function listClasses(): Promise<SchoolClass[]> {
  const { data } = await client.get<SchoolClass[]>('/academic/classes');
  return data;
}

export async function getClass(classId: string): Promise<SchoolClass> {
  const { data } = await client.get<SchoolClass>(`/academic/classes/${classId}`);
  return data;
}

export async function createClass(req: {
  level: string;
  year_group: number;
  programme_id?: string;
  stream?: string;
  capacity?: number;
}): Promise<SchoolClass> {
  const { data } = await client.post<SchoolClass>('/academic/classes', req);
  return data;
}

export async function updateClass(classId: string, req: {
  stream?: string | null; capacity?: number | null; is_active?: boolean; programme_id?: string;
}): Promise<SchoolClass> {
  const { data } = await client.patch<SchoolClass>(`/academic/classes/${classId}`, req);
  return data;
}

export async function listClassSubjects(classId: string): Promise<ClassSubject[]> {
  const { data } = await client.get<ClassSubject[]>(`/academic/classes/${classId}/subjects`);
  return data;
}

export async function assignSubjects(
  classId: string,
  subjectIds: string[]
): Promise<ClassSubject[]> {
  const { data } = await client.post<ClassSubject[]>(`/academic/classes/${classId}/subjects`, {
    subject_ids: subjectIds,
  });
  return data;
}

export async function getClassTeacher(classId: string, yearId: string): Promise<ClassTeacher | null> {
  const { data } = await client.get<ClassTeacher | null>(
    `/academic/classes/${classId}/class-teacher`,
    { params: { year_id: yearId } }
  );
  return data;
}

export async function listSubjectTeachers(classId: string, termId: string): Promise<SubjectTeacher[]> {
  const { data } = await client.get<SubjectTeacher[]>(
    `/academic/classes/${classId}/subject-teachers`,
    { params: { term_id: termId } }
  );
  return data;
}

export async function removeClassSubject(classId: string, subjectId: string): Promise<void> {
  await client.delete(`/academic/classes/${classId}/subjects/${subjectId}`);
}

export async function assignClassTeacher(
  classId: string,
  req: { staff_member_id: string; academic_year_id: string }
): Promise<ClassTeacher> {
  const { data } = await client.post<ClassTeacher>(
    `/academic/classes/${classId}/class-teacher`,
    req
  );
  return data;
}

export async function assignSubjectTeacher(
  classId: string,
  req: { subject_id: string; staff_member_id: string; academic_term_id: string }
): Promise<unknown> {
  const { data } = await client.post(`/academic/classes/${classId}/subject-teachers`, req);
  return data;
}

export async function listProgrammes(): Promise<Programme[]> {
  const { data } = await client.get<Programme[]>('/academic/programmes');
  return data;
}

export async function createProgramme(req: { code: string; name: string }): Promise<Programme> {
  const { data } = await client.post<Programme>('/academic/programmes', req);
  return data;
}

export async function updateProgramme(progId: string, req: {
  code?: string; name?: string; is_active?: boolean;
}): Promise<Programme> {
  const { data } = await client.patch<Programme>(`/academic/programmes/${progId}`, req);
  return data;
}
