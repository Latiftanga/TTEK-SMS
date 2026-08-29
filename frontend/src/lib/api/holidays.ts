import client from './client';

export interface HolidayRead {
  id: string;
  name: string;
  date: string;
  is_recurring: boolean;
  description: string | null;
}

export interface HolidayPayload {
  name?: string;
  date?: string;
  is_recurring?: boolean;
  description?: string | null;
}

/** Superadmin-only — system-wide Ghana public holiday reference data every
 * school's calendar generation reads from. */
export async function listHolidays(): Promise<HolidayRead[]> {
  const { data } = await client.get<HolidayRead[]>('/superadmin/holidays');
  return data;
}

export async function createHoliday(payload: HolidayPayload): Promise<HolidayRead> {
  const { data } = await client.post<HolidayRead>('/superadmin/holidays', payload);
  return data;
}

export async function updateHoliday(id: string, payload: HolidayPayload): Promise<HolidayRead> {
  const { data } = await client.patch<HolidayRead>(`/superadmin/holidays/${id}`, payload);
  return data;
}

export async function deleteHoliday(id: string): Promise<void> {
  await client.delete(`/superadmin/holidays/${id}`);
}
