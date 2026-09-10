#!/usr/bin/env node
/**
 * Screenshot capture tool for TTEK-SMS's dev docker-compose stack.
 * Runs inside the `playwright` compose service (its own Dockerfile bundles a
 * matching browser build + OS deps) — never on the host, which may lack the
 * shared libraries Chromium needs and root access to install them.
 *
 * Usage (from the project root):
 *   docker compose run --rm playwright --path=/dashboard --out=dashboard.png \
 *     --email=admin@shs.school --password=Demo1234! --school_code=SHS-DEMO
 *
 * Output lands in scripts/screenshot/screenshots/<out> on the host (bind-mounted).
 *
 * Flags:
 *   --path=/route          route to visit after the frontend origin loads (default /login)
 *   --out=name.png         output filename under screenshots/ (default screenshot.png)
 *   --host=frontend:5173   internal docker hostname:port to visit (default frontend:5173)
 *   --api=http://api:8000  internal API base for the login call (default http://api:8000)
 *   --email= --password= --school_code=   log in as a real school account first
 *   --superadmin --email= --password=      log in via /auth/superadmin-login instead
 *   --full-page             capture the whole scrollable page, not just the viewport
 *   --dark                  emulate prefers-color-scheme: dark
 *   --wait-for=<selector>   wait for a CSS selector before capturing (else a settle delay)
 *   --timeout=15000         navigation/wait timeout in ms
 */
import { chromium, request as pwRequest } from 'playwright';
import { mkdirSync } from 'node:fs';

function arg(name, def) {
  const pfx = `--${name}=`;
  const found = process.argv.find((a) => a.startsWith(pfx));
  return found ? found.slice(pfx.length) : def;
}
function flag(name) {
  return process.argv.includes(`--${name}`);
}

const routePath = arg('path', '/login');
const out = arg('out', 'screenshot.png');
const host = arg('host', 'frontend:5173');
const apiBase = arg('api', 'http://api:8000');
const email = arg('email');
const password = arg('password');
const schoolCode = arg('school_code');
const superadmin = flag('superadmin');
const fullPage = flag('full-page');
const dark = flag('dark');
const waitForSelector = arg('wait-for');
const timeout = parseInt(arg('timeout', '15000'), 10);

const baseUrl = `http://${host}`;

async function login() {
  const api = await pwRequest.newContext();
  const endpoint = superadmin ? '/auth/superadmin-login' : '/auth/login';
  const data = superadmin
    ? { identifier: email, password }
    : { login_type: 'EMAIL', identifier: email, password, school_code: schoolCode };

  const resp = await api.post(`${apiBase}${endpoint}`, { data });
  if (!resp.ok()) {
    console.error(`Login failed (${resp.status()}):`, await resp.text());
    process.exit(1);
  }
  const body = await resp.json();
  await api.dispose();
  return body;
}

async function main() {
  const browser = await chromium.launch();
  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    colorScheme: dark ? 'dark' : 'light',
  });
  const page = await context.newPage();

  // Must land on the origin once before localStorage is writable.
  await page.goto(`${baseUrl}/login`, { waitUntil: 'domcontentloaded', timeout });

  if (email && password) {
    const { access_token, refresh_token } = await login();
    await page.evaluate(
      ([at, rt, isSuper]) => {
        localStorage.setItem('access_token', at);
        if (rt) localStorage.setItem('refresh_token', rt);
        localStorage.setItem('offline_session_started_at', new Date().toISOString());
        localStorage.setItem('is_superadmin', isSuper ? '1' : '0');
      },
      [access_token, refresh_token, superadmin],
    );
  }

  await page.goto(`${baseUrl}${routePath}`, { waitUntil: 'networkidle', timeout });

  if (waitForSelector) {
    await page.waitForSelector(waitForSelector, { timeout }).catch((e) => {
      console.error(`wait-for selector "${waitForSelector}" never appeared:`, e.message);
    });
  } else {
    await page.waitForTimeout(700); // let page-enter animations / HMR overlay settle
  }

  mkdirSync('screenshots', { recursive: true });
  const outPath = `screenshots/${out}`;
  await page.screenshot({ path: outPath, fullPage });
  console.log('Saved', outPath);

  await browser.close();
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
