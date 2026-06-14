import { redirect } from '@sveltejs/kit';
import type { Handle } from '@sveltejs/kit';
import { env } from '$env/dynamic/private';

// Reserved subdomains that belong to the platform, not schools
const RESERVED = new Set(['www', 'api', 'admin', 'mail', 'staging', 'dev']);

/**
 * Returns { subdomain, customDomain } from the Host header.
 *
 * Cases:
 *  localhost / 127.0.0.1          → both null (platform root, local dev)
 *  basic.localhost:5173           → subdomain='basic', customDomain=null
 *  presec.ttek-sms.com            → subdomain='presec', customDomain=null
 *  portal.presec.com              → subdomain=null, customDomain='portal.presec.com'
 *  ttek-sms.com / www.ttek-sms.com → both null (platform root)
 */
function parseHost(host: string): { subdomain: string | null; customDomain: string | null } {
  const hostname = host.split(':')[0]; // strip port

  if (hostname === 'localhost' || hostname === '127.0.0.1') {
    return { subdomain: null, customDomain: null };
  }

  // *.localhost — local dev only (Chrome/Firefox support this natively)
  if (hostname.endsWith('.localhost')) {
    const sub = hostname.split('.')[0];
    if (RESERVED.has(sub)) return { subdomain: null, customDomain: null };
    return { subdomain: sub, customDomain: null };
  }

  const platformDomain = env.PLATFORM_DOMAIN ?? 'ttek-sms.com';

  // Platform subdomain: presec.ttek-sms.com
  if (hostname === platformDomain || hostname.endsWith(`.${platformDomain}`)) {
    if (hostname === platformDomain) return { subdomain: null, customDomain: null };
    const sub = hostname.slice(0, hostname.length - platformDomain.length - 1);
    if (RESERVED.has(sub)) return { subdomain: null, customDomain: null };
    return { subdomain: sub, customDomain: null };
  }

  // Everything else is a potential custom domain (portal.presec.com)
  return { subdomain: null, customDomain: hostname };
}

export const handle: Handle = async ({ event, resolve }) => {
  const host = event.request.headers.get('host') ?? '';
  const { subdomain, customDomain } = parseHost(host);

  event.locals.subdomain = subdomain;
  event.locals.customDomain = customDomain;

  // Platform admin login is only reachable from the root domain
  if ((subdomain || customDomain) && event.url.pathname === '/') {
    throw redirect(302, '/login');
  }

  return resolve(event);
};
