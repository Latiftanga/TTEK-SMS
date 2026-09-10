import { api } from './client';

export type ExtractionStatus = 'PENDING' | 'DONE' | 'FAILED' | 'EMPTY';

export interface CurriculumMaterial {
  id: string;
  school_id: string;
  class_subject_id: string;
  document_type: string;
  file_name: string;
  file_size: number | null;
  mime_type: string | null;
  uploaded_by_id: string;
  created_at: string;
  extraction_status: ExtractionStatus;
  extraction_error: string | null;
  unit_extraction_status: ExtractionStatus;
  unit_extraction_error: string | null;
}

export const listCurriculumMaterials = (classSubjectId: string): Promise<CurriculumMaterial[]> =>
  api.get(`/curriculum-materials/${classSubjectId}`).then(r => r.data);

export const uploadCurriculumMaterial = (
  classSubjectId: string, documentType: string, file: File,
): Promise<CurriculumMaterial> => {
  const form = new FormData();
  form.append('file', file);
  return api.post(`/curriculum-materials/${classSubjectId}`, form, {
    params: { document_type: documentType },
    headers: { 'Content-Type': 'multipart/form-data' },
  }).then(r => r.data);
};

export const deleteCurriculumMaterial = (materialId: string): Promise<void> =>
  api.delete(`/curriculum-materials/${materialId}`).then(r => r.data);

// Admin-triggered, not automatic on upload — a large document can cost
// 10-30 sequential AI calls, a conscious action rather than a surprise
// side effect of every upload.
export const extractCurriculumUnits = (materialId: string): Promise<CurriculumMaterial> =>
  api.post(`/curriculum-materials/${materialId}/extract-units`).then(r => r.data);
