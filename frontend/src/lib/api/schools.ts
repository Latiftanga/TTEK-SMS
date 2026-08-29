import client from './client';

export interface SchoolBranding {
  school_name: string;
  short_name: string | null;
  school_type: 'BASIC' | 'SHS' | 'TECHNICAL' | 'VOCATIONAL' | 'PRIVATE';
  motto: string | null;
  logo_url: string | null;
  brand_color: string;
  school_code: string;
}

export interface SchoolRead {
  id: string;
  name: string;
  short_name: string | null;
  school_code: string;
  school_type: 'BASIC' | 'SHS' | 'TECHNICAL' | 'VOCATIONAL' | 'PRIVATE';
  ownership: 'PUBLIC' | 'PRIVATE';
  region_id: string;
  district_id: string;
  phone: string | null;
  email: string | null;
  address: string | null;
  motto: string | null;
  logo_path: string | null;
  logo_url: string | null;
  established_year: number | null;
  is_active: boolean;
  has_boarding: boolean;
  has_period_attendance: boolean;
  subdomain: string | null;
  custom_domain: string | null;
  brand_color: string;
}

/** SchoolRead plus usage stats — the superadmin dashboard list only. */
export interface SchoolSummary extends SchoolRead {
  student_count: number;
  staff_count: number;
  last_login_at: string | null;
}

/** PATCH /schools/me — self-service. Deliberately no subdomain/custom_domain
 * field: the backend rejects them here with 403 regardless (services/
 * school.py::update_school's allow_domain_change gate) — only a platform
 * superadmin can change a school's sign-in link, via the separate
 * superadmin school-edit form. */
export interface SchoolUpdatePayload {
  name?: string;
  short_name?: string;
  phone?: string;
  email?: string;
  address?: string;
  motto?: string;
  established_year?: number;
  has_boarding?: boolean;
  has_period_attendance?: boolean;
  brand_color?: string;
}

/** Extends SchoolBranding with routing identifiers returned for custom domain resolution. */
export interface SchoolByDomainResult extends SchoolBranding {
  school_code: string;
  subdomain: string | null;
}

export interface RegionRead {
  id: string;
  name: string;
  code: string;
}

export interface DistrictRead {
  id: string;
  name: string;
  code: string;
  region_id: string;
}

/** POST /schools payload — superadmin only. subdomain left blank auto-generates
 * one from `name` (services/school.py::create_school). */
export interface SchoolCreatePayload {
  name: string;
  short_name?: string;
  school_code: string;
  school_type: 'BASIC' | 'SHS';
  region_id: string;
  district_id: string;
  phone?: string;
  email?: string;
  address?: string;
  motto?: string;
  established_year?: number;
  subdomain?: string;
  has_boarding?: boolean;
}

/** PATCH /schools/{id} payload — superadmin only. school_code/school_type
 * are immutable after creation (not accepted by the backend at all). */
export interface SchoolAdminUpdatePayload {
  name?: string;
  short_name?: string;
  phone?: string;
  email?: string;
  address?: string;
  motto?: string;
  established_year?: number;
  has_boarding?: boolean;
  subdomain?: string;
  custom_domain?: string;
  is_active?: boolean;
}

/** Public endpoint — no auth required. */
export async function getSchoolBranding(subdomain: string): Promise<SchoolBranding> {
  const { data } = await client.get<SchoolBranding>(`/schools/public/${subdomain}`);
  return data;
}

/**
 * Resolve a custom domain to its school branding + routing identifiers.
 * Public endpoint — no auth required. Called before login on custom-domain deployments.
 */
export async function getSchoolByDomain(hostname: string): Promise<SchoolByDomainResult> {
  const { data } = await client.get<SchoolByDomainResult>('/schools/by-domain', {
    params: { h: hostname },
  });
  return data;
}

/** Authenticated endpoint — returns the current user's school branding. */
export async function getMySchoolBranding(): Promise<SchoolBranding> {
  const { data } = await client.get<SchoolBranding>('/schools/my-branding');
  return data;
}

/** Return full school profile for the authenticated user's school. */
export async function getMySchool(): Promise<SchoolRead> {
  const { data } = await client.get<SchoolRead>('/schools/me');
  return data;
}

/** Partially update the authenticated user's school profile. */
export async function updateMySchool(payload: SchoolUpdatePayload): Promise<SchoolRead> {
  const { data } = await client.patch<SchoolRead>('/schools/me', payload);
  return data;
}

/** Upload or replace the school logo. */
export async function uploadMyLogo(file: File): Promise<SchoolRead> {
  const form = new FormData();
  form.append('file', file);
  const { data } = await client.post<SchoolRead>('/schools/me/logo', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return data;
}

// ── Superadmin — school onboarding ──────────────────────────────────────────

/** List every school on the platform. Superadmin only. */
export async function listSchools(
  params?: { active_only?: boolean; search?: string },
): Promise<SchoolSummary[]> {
  const { data } = await client.get<SchoolSummary[]>('/schools', {
    params: { limit: 500, ...params },
  });
  return data;
}

/** Permanently delete a school. Superadmin only — the backend only ever
 * allows this for an already-disabled, genuinely empty school (zero
 * students, zero staff); see services/school.py::delete_school. */
export async function deleteSchool(id: string): Promise<void> {
  await client.delete(`/schools/${id}`);
}

/** Register a new school. Superadmin only — Tagnatek provisions each school. */
export async function createSchool(payload: SchoolCreatePayload): Promise<SchoolRead> {
  const { data } = await client.post<SchoolRead>('/schools', payload);
  return data;
}

/** Update any school's profile — including is_active, which is what
 * actually blocks sign-in (services/auth_lookup.py::resolve_school_id
 * excludes deactivated schools from every login/reset lookup). Superadmin only. */
export async function updateSchool(id: string, payload: SchoolAdminUpdatePayload): Promise<SchoolRead> {
  const { data } = await client.patch<SchoolRead>(`/schools/${id}`, payload);
  return data;
}

/** Public reference data — no auth required (also usable pre-login). */
export async function listRegions(): Promise<RegionRead[]> {
  const { data } = await client.get<RegionRead[]>('/schools/regions');
  return data;
}

export async function listDistricts(regionId?: string): Promise<DistrictRead[]> {
  const { data } = await client.get<DistrictRead[]>('/schools/districts', {
    params: regionId ? { region_id: regionId } : undefined,
  });
  return data;
}

const DEFAULT_FAVICON = '/favicon.svg';

/**
 * Apply the school's brand color as CSS custom properties on <html>, and
 * swap the browser-tab favicon to the school's own logo — the one piece of
 * "this feels like ours" branding that was still a static platform-wide
 * file (app.html's #app-favicon) even though title/logo/motto/color were
 * already dynamic everywhere this function is called (login, portal,
 * forgot-password, the live Setup preview). Falls back to the default
 * favicon when a school has no logo, rather than leaving a stale one from
 * whatever branding was applied previously (matters for ProfileTab's live
 * preview and for navigating between schools on the login screen).
 */
export function applyBranding(branding: SchoolBranding) {
  const root = document.documentElement;
  const hex = branding.brand_color;
  root.style.setProperty('--brand', hex);
  root.style.setProperty('--brand-light', hexTint(hex, 0.9));

  const favicon = document.getElementById('app-favicon') as HTMLLinkElement | null;
  if (favicon) favicon.href = branding.logo_url ?? DEFAULT_FAVICON;

  // RGB triplet for rgba(var(--brand-rgb), 0.1) usage in components
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  root.style.setProperty('--brand-rgb', `${r}, ${g}, ${b}`);
}

function hexTint(hex: string, lightness: number): string {
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  const tr = Math.round(r + (255 - r) * lightness);
  const tg = Math.round(g + (255 - g) * lightness);
  const tb = Math.round(b + (255 - b) * lightness);
  return `rgb(${tr}, ${tg}, ${tb})`;
}
