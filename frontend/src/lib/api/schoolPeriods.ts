import client from './client';
import type { DayOfWeek } from './attendance';

export interface SchoolPeriod {
  id: string;
  school_id: string;
  name: string;
  day_of_week: DayOfWeek;
  period_number: number;
  start_time: string;
  end_time: string;
}

export const listPeriods = (): Promise<SchoolPeriod[]> =>
  client.get('/attendance/periods').then(r => r.data);

export const createPeriod = (data: {
  name: string;
  day_of_week: DayOfWeek;
  period_number: number;
  start_time: string;
  end_time: string;
}): Promise<SchoolPeriod> =>
  client.post('/attendance/periods', data).then(r => r.data);

export const updatePeriod = (periodId: string, data: {
  name?: string;
  start_time?: string;
  end_time?: string;
}): Promise<SchoolPeriod> =>
  client.patch(`/attendance/periods/${periodId}`, data).then(r => r.data);

export const deletePeriod = (periodId: string): Promise<void> =>
  client.delete(`/attendance/periods/${periodId}`);

export const copyPeriods = (data: {
  source_day: DayOfWeek;
  target_days: DayOfWeek[];
}): Promise<SchoolPeriod[]> =>
  client.post('/attendance/periods/copy', data).then(r => r.data);
