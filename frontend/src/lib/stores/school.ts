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

// The single canonical test for "does this school have SHS-style programme
// tracks and electives" — previously checked three different, inconsistent
// ways across the Academic module (=== 'SHS', !== 'BASIC', and this exact
// list on the nav only), which meant a TECHNICAL/VOCATIONAL school could get
// SHS-style elective UI but a BASIC-style class-creation form with no
// programme field. Use this everywhere instead of inlining the check.
export function hasProgrammeTracks(schoolType: SchoolType): boolean {
  return schoolType === 'SHS' || schoolType === 'TECHNICAL' || schoolType === 'VOCATIONAL';
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
