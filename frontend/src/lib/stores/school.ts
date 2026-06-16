import { writable } from 'svelte/store';
import { browser } from '$app/environment';

export type SchoolType = 'BASIC' | 'SHS' | 'TECHNICAL' | 'VOCATIONAL' | 'PRIVATE';

export interface SchoolInfo {
  name: string;
  shortName: string;
  subdomain: string;
  schoolCode: string;
  schoolType: SchoolType;
  brandColor: string;
  logoUrl: string | null;
  motto: string | null;
}

const KEY = 'ttek_school';

function createSchoolStore() {
  let initial: SchoolInfo | null = null;
  if (browser) {
    try { initial = JSON.parse(localStorage.getItem(KEY) ?? 'null'); } catch { /* ignore */ }
  }
  const { subscribe, set: _set } = writable<SchoolInfo | null>(initial);
  return {
    subscribe,
    set(info: SchoolInfo) {
      if (browser) localStorage.setItem(KEY, JSON.stringify(info));
      _set(info);
    },
    clear() {
      if (browser) localStorage.removeItem(KEY);
      _set(null);
    },
  };
}

export const school = createSchoolStore();
