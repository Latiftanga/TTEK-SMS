import { api } from './client';

export interface House {
  id: string;
  school_id: string;
  name: string;
  code: string;
  capacity: number | null;
}

export const listHouses = (): Promise<House[]> =>
  api.get('/houses').then(r => r.data);
