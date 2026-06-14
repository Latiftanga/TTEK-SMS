import { readable } from 'svelte/store';
import { browser } from '$app/environment';
import { env } from '$env/dynamic/public';

const RESERVED = new Set(['www', 'api', 'admin', 'mail', 'staging', 'dev']);

function detect(): { subdomain: string | null; customDomain: string | null } {
  if (!browser) return { subdomain: null, customDomain: null };

  const hostname = window.location.hostname;

  if (hostname === 'localhost' || hostname === '127.0.0.1') {
    return { subdomain: null, customDomain: null };
  }

  if (hostname.endsWith('.localhost')) {
    const sub = hostname.split('.')[0];
    if (RESERVED.has(sub)) return { subdomain: null, customDomain: null };
    return { subdomain: sub, customDomain: null };
  }

  const platformDomain = env.PUBLIC_PLATFORM_DOMAIN ?? 'ttek-sms.com';

  if (hostname === platformDomain || hostname.endsWith(`.${platformDomain}`)) {
    if (hostname === platformDomain) return { subdomain: null, customDomain: null };
    const sub = hostname.slice(0, hostname.length - platformDomain.length - 1);
    if (RESERVED.has(sub)) return { subdomain: null, customDomain: null };
    return { subdomain: sub, customDomain: null };
  }

  return { subdomain: null, customDomain: hostname };
}

const _detected = detect();

/** The school subdomain of the current URL, or null on the root domain. Computed once on boot. */
export const subdomain = readable<string | null>(_detected.subdomain);

/**
 * A school-owned custom domain (e.g. portal.presec.com), or null.
 * When set, the login page must resolve the school via GET /schools/by-domain.
 */
export const customDomain = readable<string | null>(_detected.customDomain);
