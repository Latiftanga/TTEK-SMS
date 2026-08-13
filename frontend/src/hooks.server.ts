import { redirect, type Handle } from '@sveltejs/kit';
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

  // No hardcoded fallback: the platform domain isn't purchased yet, so an
  // unset PLATFORM_DOMAIN means this branch simply never matches — every
  // non-localhost hostname falls through to the customDomain catch-all
  // below, exactly as it already does for any other unrecognized hostname.
  const platformDomain = env.PLATFORM_DOMAIN;

  // Platform subdomain: presec.ttek-sms.com (once PLATFORM_DOMAIN is set)
  if (platformDomain && (hostname === platformDomain || hostname.endsWith(`.${platformDomain}`))) {
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

  // A recognized school subdomain (matched above via the explicit
  // `.localhost` / `.{PLATFORM_DOMAIN}` suffix rule — a deliberate, known
  // convention, not a guess) landing on the bare root belongs on that
  // school's own login (/login), not the platform-admin login every other
  // hostname shows at `/` — the sign-in link every school is actually given
  // (see admin/staff invite modal, superadmin school list) is exactly
  // `https://<subdomain>.<platform domain>`, the bare root, so without this
  // that link lands on the wrong page.
  //
  // Deliberately NOT applied to `customDomain`: that branch is parseHost()'s
  // catch-all for "any hostname that matched nothing else" — a LAN IP, a
  // WSL-forwarded address, a typo — completely unverified against the DB.
  // Forcing this same redirect off *that* guess is exactly what made `/`
  // (the platform-admin login) unreachable for a real platform admin on a
  // non-canonical hostname, with no way back (12bg). Real custom-domain
  // schools landing on platform-admin at their own root instead of /login
  // is a known, accepted gap until Phase C's domain-verification pipeline
  // exists (see CLAUDE.md 12ba) — customDomain has no DB check to redirect
  // on safely yet.
  if (subdomain && event.url.pathname === '/') {
    throw redirect(302, '/login');
  }

  return resolve(event);
};
