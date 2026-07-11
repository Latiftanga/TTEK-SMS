/**
 * Dynamic PWA manifest — served per-school so installed PWAs show the school's
 * own name (e.g. "Presec-Legon") on the home screen, not a generic app name.
 *
 * Reads the subdomain from the request host and fetches school branding from
 * the backend. Falls back to sensible defaults when the school is unknown or
 * the backend is unreachable.
 */
import { env } from '$env/dynamic/public';
import type { RequestHandler } from './$types';

const FALLBACK = {
  name: 'School Management',
  short_name: 'SMS',
  brand_color: '#1e40af',
  logo_url: null as string | null,
};

async function fetchBranding(subdomain: string, backendUrl: string) {
  try {
    const res = await fetch(`${backendUrl}/schools/public/${subdomain}`, {
      signal: AbortSignal.timeout(3000),
    });
    if (!res.ok) return FALLBACK;
    const data = await res.json();
    return {
      name: data.school_name as string,
      short_name: (data.short_name ?? data.school_name) as string,
      brand_color: (data.brand_color ?? FALLBACK.brand_color) as string,
      logo_url: data.logo_url as string | null,
    };
  } catch {
    return FALLBACK;
  }
}

export const GET: RequestHandler = async ({ request }) => {
  const host = request.headers.get('host') ?? '';
  // Extract subdomain: "presec.ttek-sms.com" → "presec"
  // Localhost / IP → use "demo" subdomain so dev works
  const parts = host.split('.');
  const subdomain = parts.length >= 3 ? parts[0] : 'demo';

  const backendUrl = env.PUBLIC_API_URL ?? 'http://localhost:8000';
  const branding = await fetchBranding(subdomain, backendUrl);

  const manifest = {
    name: branding.name,
    short_name: branding.short_name,
    description: `School management system for ${branding.name}`,
    start_url: '/',
    display: 'standalone',
    background_color: '#111318',
    theme_color: branding.brand_color,
    orientation: 'portrait-primary',
    lang: 'en-GH',
    icons: [
      {
        src: branding.logo_url ?? '/icons/icon-192.png',
        sizes: '192x192',
        type: 'image/png',
        purpose: 'any maskable',
      },
      {
        src: branding.logo_url ?? '/icons/icon-512.png',
        sizes: '512x512',
        type: 'image/png',
        purpose: 'any maskable',
      },
    ],
    categories: ['education', 'productivity'],
  };

  return new Response(JSON.stringify(manifest), {
    headers: {
      'Content-Type': 'application/manifest+json',
      'Cache-Control': 'public, max-age=3600',
    },
  });
};
