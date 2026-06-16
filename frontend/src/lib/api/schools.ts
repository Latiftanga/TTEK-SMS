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
  phone: string | null;
  email: string | null;
  address: string | null;
  motto: string | null;
  logo_path: string | null;
  established_year: number | null;
  is_active: boolean;
  has_boarding: boolean;
  subdomain: string | null;
  custom_domain: string | null;
  brand_color: string;
}

export interface SchoolUpdatePayload {
  name?: string;
  short_name?: string;
  phone?: string;
  email?: string;
  address?: string;
  motto?: string;
  established_year?: number;
  has_boarding?: boolean;
  brand_color?: string;
}

/** Extends SchoolBranding with routing identifiers returned for custom domain resolution. */
export interface SchoolByDomainResult extends SchoolBranding {
  school_code: string;
  subdomain: string | null;
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

/** Apply the school's brand color as CSS custom properties on <html>. */
export function applyBranding(branding: SchoolBranding) {
  const root = document.documentElement;
  const hex = branding.brand_color;
  root.style.setProperty('--brand', hex);
  root.style.setProperty('--brand-light', hexTint(hex, 0.9));
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
