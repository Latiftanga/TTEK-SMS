import client from './client';

export interface SchoolBranding {
  school_name: string;
  short_name: string | null;
  school_type: 'BASIC' | 'SHS' | 'TECHNICAL' | 'VOCATIONAL' | 'PRIVATE';
  motto: string | null;
  logo_url: string | null;
  brand_color: string;
}

/** Public endpoint — no auth required. */
export async function getSchoolBranding(subdomain: string): Promise<SchoolBranding> {
  const { data } = await client.get<SchoolBranding>(`/schools/public/${subdomain}`);
  return data;
}

/** Apply the school's brand color as a CSS custom property on <html>. */
export function applyBranding(branding: SchoolBranding) {
  const root = document.documentElement;
  root.style.setProperty('--brand', branding.brand_color);

  // Compute a light tint (mix with white at 90%) for backgrounds
  root.style.setProperty('--brand-light', hexTint(branding.brand_color, 0.9));
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
