/**
 * The platform's own root domain (school subdomains live under it, e.g.
 * <school_code>.<platform domain>), read from PUBLIC_PLATFORM_DOMAIN.
 *
 * Deliberately no hardcoded fallback — the domain hasn't been purchased yet,
 * so pretending one exists would build broken/misleading sign-in links.
 * Once the real domain is bought and PUBLIC_PLATFORM_DOMAIN is set, every
 * caller of this module picks it up automatically — no code change needed.
 */
import { env } from '$env/dynamic/public';

export function getPlatformDomain(): string | null {
  return env.PUBLIC_PLATFORM_DOMAIN || null;
}

/** A school's own sign-in URL, or null until both a subdomain and the
 *  platform domain are known. */
export function schoolLoginUrl(subdomain: string | null | undefined): string | null {
  const domain = getPlatformDomain();
  if (!domain || !subdomain) return null;
  return `https://${subdomain}.${domain}`;
}
