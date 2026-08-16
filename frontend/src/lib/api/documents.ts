import { api } from './client';

export type DocumentEntityType = 'student' | 'staff';

export interface DocumentRecord {
  id: string;
  school_id: string;
  entity_type: DocumentEntityType;
  entity_id: string;
  document_type: string;
  file_name: string;
  file_size: number | null;
  mime_type: string | null;
  uploaded_by_id: string;
  created_at: string;
}

export const listDocuments = (
  entityType: DocumentEntityType, entityId: string,
): Promise<DocumentRecord[]> =>
  api.get(`/documents/${entityType}/${entityId}`).then(r => r.data);

export const uploadDocument = (
  entityType: DocumentEntityType, entityId: string, documentType: string, file: File,
): Promise<DocumentRecord> => {
  const form = new FormData();
  form.append('file', file);
  return api.post(`/documents/${entityType}/${entityId}`, form, {
    params: { document_type: documentType },
    headers: { 'Content-Type': 'multipart/form-data' },
  }).then(r => r.data);
};

export const downloadDocumentBlob = (docId: string): Promise<Blob> =>
  api.get(`/documents/${docId}/download`, { responseType: 'blob' }).then(r => r.data);

export const deleteDocument = (docId: string): Promise<void> =>
  api.delete(`/documents/${docId}`).then(() => undefined);
