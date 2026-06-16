/**
 * Dexie OfflineCache — structured data store.
 *
 * Stores class roster, student list, current term, subjects, and calendar
 * so teachers can work with zero network connection.
 *
 * Synced on every app foreground when network is available.
 * Read-only from the perspective of the app — only the sync process writes here.
 */
import Dexie, { type Table } from 'dexie';

export interface CachedClass {
  id: string;
  school_id: string;
  level: string;
  year_group: number | null;
  stream: string | null;
  computed_name: string;       // pre-computed on server: "SHS 1 Science A"
  cached_at: number;           // Unix timestamp
}

export interface CachedStudent {
  id: string;
  school_id: string;
  class_id: string;
  admission_number: string;
  full_name: string;           // pre-joined: first + middle + last
  student_type: 'DAY' | 'BOARDING';
  photo_url: string | null;
  fee_status: string;
  cached_at: number;
}

export interface CachedTerm {
  id: string;
  school_id: string;
  name: string;
  start_date: string;
  end_date: string;
  block_owing_students: boolean;
  cached_at: number;
}

export interface CachedSubject {
  id: string;
  school_id: string;
  class_id: string;
  subject_id: string;
  subject_name: string;
  cached_at: number;
}

export interface CachedCalendarDay {
  id: string;
  school_id: string;
  term_id: string;
  date: string;                // ISO date string
  day_type: 'SCHOOL_DAY' | 'HOLIDAY' | 'CLOSURE' | 'WEEKEND';
  label: string | null;
  cached_at: number;
}

export interface SyncMeta {
  key: string;                 // e.g. "classes:school_id"
  last_synced_at: number;      // Unix timestamp
  school_id: string;
}

class OfflineCacheDB extends Dexie {
  classes!: Table<CachedClass>;
  students!: Table<CachedStudent>;
  terms!: Table<CachedTerm>;
  subjects!: Table<CachedSubject>;
  calendar!: Table<CachedCalendarDay>;
  sync_meta!: Table<SyncMeta>;

  constructor() {
    super('ttek_offline_cache');
    this.version(1).stores({
      classes:   'id, school_id, cached_at',
      students:  'id, school_id, class_id, cached_at',
      terms:     'id, school_id, cached_at',
      subjects:  'id, school_id, class_id, cached_at',
      calendar:  'id, school_id, term_id, date, day_type',
      sync_meta: 'key, school_id',
    });
  }
}

export const offlineCache = new OfflineCacheDB();

/** Returns true if data is stale (older than maxAgeHours). */
export async function isCacheStale(key: string, maxAgeHours = 24): Promise<boolean> {
  const meta = await offlineCache.sync_meta.get(key);
  if (!meta) return true;
  const ageMs = Date.now() - meta.last_synced_at;
  return ageMs > maxAgeHours * 60 * 60 * 1000;
}

/** Update sync timestamp after a successful sync. */
export async function markSynced(key: string, school_id: string): Promise<void> {
  await offlineCache.sync_meta.put({
    key,
    last_synced_at: Date.now(),
    school_id,
  });
}
