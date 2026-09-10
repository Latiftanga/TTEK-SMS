import { api } from './client';

export interface CurriculumUnit {
  id: string;
  school_id: string;
  material_id: string;
  sequence_number: number;
  unit_label: string | null;
  strand: string | null;
  sub_strand: string | null;
  content_standard: string | null;
  indicator: string | null;
  learning_objectives: string | null;
  topics: string | null;
  source_page_start: number;
  source_page_end: number;
}

export interface CurriculumUnitUpdatePayload {
  unit_label?: string | null;
  strand?: string | null;
  sub_strand?: string | null;
  content_standard?: string | null;
  indicator?: string | null;
  learning_objectives?: string | null;
  topics?: string | null;
}

export const listCurriculumUnits = (materialId: string): Promise<CurriculumUnit[]> =>
  api.get(`/curriculum-materials/${materialId}/units`).then(r => r.data);

export const updateCurriculumUnit = (unitId: string, data: CurriculumUnitUpdatePayload): Promise<CurriculumUnit> =>
  api.patch(`/curriculum-units/${unitId}`, data).then(r => r.data);
