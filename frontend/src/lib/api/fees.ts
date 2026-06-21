import { api } from './client';

export type PaymentMethod = 'CASH' | 'MOBILE_MONEY' | 'BANK_TRANSFER' | 'CHEQUE' | 'OTHER';
export type DiscountType = 'SCHOLARSHIP' | 'BURSARY' | 'SIBLING' | 'STAFF_WARD' | 'OTHER';

export interface FeeType {
  id: string;
  school_id: string | null;
  name: string;
  code: string;
  description: string | null;
  is_recurring: boolean;
  is_active: boolean;
}

export interface FeeStructure {
  id: string;
  school_id: string;
  academic_term_id: string;
  fee_type_id: string;
  fee_type_name: string;
  amount: string;
  is_mandatory: boolean;
  applies_to_year_group: number | null;
  applies_to_programme_id: string | null;
}

export interface BulkAssignResult {
  structure_id: string;
  assigned: number;
  skipped: number;
}

export interface FeeRecord {
  id: string;
  student_id: string;
  academic_term_id: string;
  fee_structure_id: string;
  fee_type_name: string;
  amount_due: string;
  due_date: string | null;
  is_waived: boolean;
}

export interface FeeSummary {
  student_id: string;
  academic_term_id: string;
  total_due: string;
  total_paid: string;
  total_discounted: string;
  balance: string;
  last_payment_date: string | null;
  updated_at: string;
}

export interface FeePayment {
  id: string;
  student_id: string;
  academic_term_id: string;
  fee_record_id: string;
  amount_paid: string;
  payment_method: PaymentMethod;
  reference_number: string | null;
  received_by_id: string;
  payment_date: string;
  notes: string | null;
}

export interface FeeDiscount {
  id: string;
  student_id: string;
  academic_term_id: string;
  fee_record_id: string;
  discount_type: DiscountType;
  amount: string | null;
  percentage: string | null;
  reason: string | null;
  approved_by_id: string | null;
  created_at: string;
}

export const PAYMENT_METHOD_LABELS: Record<PaymentMethod, string> = {
  CASH: 'Cash',
  MOBILE_MONEY: 'Mobile Money',
  BANK_TRANSFER: 'Bank Transfer',
  CHEQUE: 'Cheque',
  OTHER: 'Other',
};

export const DISCOUNT_TYPE_LABELS: Record<DiscountType, string> = {
  SCHOLARSHIP: 'Scholarship',
  BURSARY: 'Bursary',
  SIBLING: 'Sibling',
  STAFF_WARD: 'Staff Ward',
  OTHER: 'Other',
};

export function ghs(v: string | number): string {
  const n = Number(v);
  return 'GHS ' + n.toFixed(2).replace(/\B(?=(\d{3})+(?!\d))/g, ',');
}

// Fee types
export const listFeeTypes = () =>
  api.get<FeeType[]>('/fees/types').then(r => r.data);

export const createFeeType = (data: { name: string; code: string; description?: string; is_recurring?: boolean }) =>
  api.post<FeeType>('/fees/types', data).then(r => r.data);

export const updateFeeType = (id: string, data: { name?: string; description?: string; is_recurring?: boolean; is_active?: boolean }) =>
  api.patch<FeeType>(`/fees/types/${id}`, data).then(r => r.data);

// Fee structures
export const listFeeStructures = (termId: string) =>
  api.get<FeeStructure[]>('/fees/structures', { params: { term_id: termId } }).then(r => r.data);

export const createFeeStructure = (data: { academic_term_id: string; fee_type_id: string; amount: number; is_mandatory?: boolean; applies_to_year_group?: number }) =>
  api.post<FeeStructure>('/fees/structures', data).then(r => r.data);

export const updateFeeStructure = (id: string, data: { amount?: number; is_mandatory?: boolean }) =>
  api.patch<FeeStructure>(`/fees/structures/${id}`, data).then(r => r.data);

export const bulkAssignFees = (structureId: string) =>
  api.post<BulkAssignResult>(`/fees/structures/${structureId}/bulk-assign`).then(r => r.data);

// Student records
export const listStudentFeeRecords = (studentId: string, termId: string) =>
  api.get<FeeRecord[]>(`/fees/students/${studentId}/records`, { params: { term_id: termId } }).then(r => r.data);

export const getFeeSummary = (studentId: string, termId: string) =>
  api.get<FeeSummary>(`/fees/students/${studentId}/summary`, { params: { term_id: termId } }).then(r => r.data);

// Payments
export const recordPayment = (data: {
  student_id: string;
  fee_record_id: string;
  amount_paid: number;
  payment_method: PaymentMethod;
  reference_number?: string;
  payment_date: string;
  notes?: string;
}) => api.post<FeePayment>('/fees/payments', data).then(r => r.data);

export const listPayments = (studentId: string, termId: string) =>
  api.get<FeePayment[]>('/fees/payments', { params: { student_id: studentId, term_id: termId } }).then(r => r.data);

// Discounts
export const applyDiscount = (data: {
  student_id: string;
  fee_record_id: string;
  discount_type: DiscountType;
  amount?: number;
  percentage?: number;
  reason?: string;
}) => api.post<FeeDiscount>('/fees/discounts', data).then(r => r.data);

export const listDiscounts = (studentId: string, termId: string) =>
  api.get<FeeDiscount[]>('/fees/discounts', { params: { student_id: studentId, term_id: termId } }).then(r => r.data);
