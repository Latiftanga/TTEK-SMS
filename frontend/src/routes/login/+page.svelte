<script lang="ts">
  import { goto } from '$app/navigation';
  import { onMount } from 'svelte';
  import { auth, isAuthenticated } from '$lib/stores/auth';
  import { login, getMe, detectLoginType, isPortalUser } from '$lib/api/auth';
  import { getSchoolBranding, getSchoolByDomain, applyBranding, type SchoolBranding } from '$lib/api/schools';
  import { school } from '$lib/stores/school';
  import { subdomain, customDomain } from '$lib/stores/subdomain';
  import { get } from 'svelte/store';
  import LoginForm from './LoginForm.svelte';

  // Every school is reached only via its own subdomain or custom domain —
  // there is no "log in and we'll find your school" path. isSubdomain
  // (despite the name, true for either case) is resolved from the actual
  // URL, never from a cached/stored session — a remembered school must
  // never make a login form appear on the WRONG domain, since the whole
  // point is that identity is tied to the URL, not to browser storage.
  const isSubdomain = get(subdomain) !== null || get(customDomain) !== null;

  let schoolCode   = $state('');
  let identifier   = $state('');
  let password     = $state('');
  let showPassword = $state(false);
  let rememberMe   = $state(false);

  let branding   = $state<SchoolBranding | null>(null);
  let resolving  = $state(true);   // resolving the URL's school context
  let formError  = $state('');
  let loadingLogin = $state(false);

  async function fetchBranding(slug: string) {
    try {
      const data = await getSchoolBranding(slug);
      schoolCode = data.school_code;
      branding = data;
      applyBranding(data);
      school.set({
        name: data.school_name, shortName: data.short_name ?? data.school_name,
        subdomain: slug, schoolCode: data.school_code,
        schoolType: data.school_type, brandColor: data.brand_color,
        logoUrl: data.logo_url, motto: data.motto,
      });
    } catch {
      schoolCode = '';
      branding = null;
    }
  }

  onMount(async () => {
    if (get(isAuthenticated)) {
      try {
        const user = await getMe();
        goto(isPortalUser(user) ? '/portal' : '/dashboard');
      } catch {
        goto('/dashboard');
      }
      return;
    }

    if (!isSubdomain) {
      // Bare/plain domain — never a functional login form, regardless of
      // what's cached in localStorage from a previous visit. hooks.server.ts
      // already redirects a fresh request here to `/`; this is just the
      // client-side backstop for the rare case this component mounts
      // without a server round-trip (e.g. an in-app client-side navigation).
      goto('/', { replaceState: true });
      return;
    }

    // Paint instantly from a cached session while confirming from the URL
    // below — pure UX (avoids a flash of unbranded content), never the
    // reason the form is shown (isSubdomain already gates that).
    const stored = get(school);
    if (stored?.schoolCode) {
      schoolCode = stored.schoolCode;
      branding = {
        school_name: stored.name, short_name: stored.shortName,
        school_type: stored.schoolType ?? 'BASIC', motto: stored.motto ?? null,
        logo_url: stored.logoUrl ?? null, brand_color: stored.brandColor,
        school_code: stored.schoolCode,
      };
      applyBranding(branding);
    }

    const sub = get(subdomain);
    if (sub) {
      await fetchBranding(sub);
    } else {
      const cd = get(customDomain);
      if (cd) {
        try {
          const result = await getSchoolByDomain(cd);
          schoolCode = result.school_code;
          branding = result;
          applyBranding(result);
          school.set({
            name: result.school_name, shortName: result.short_name ?? result.school_name,
            subdomain: result.subdomain ?? '', schoolCode: result.school_code,
            schoolType: result.school_type, brandColor: result.brand_color,
            logoUrl: result.logo_url, motto: result.motto,
          });
        } catch {
          schoolCode = '';
          branding = null;
        }
      }
    }
    resolving = false;
  });

  async function handleLogin() {
    formError = '';
    if (!identifier.trim() || !password) {
      formError = 'Enter your email / phone / student ID and password.';
      return;
    }
    loadingLogin = true;
    try {
      const tokens = await login({
        login_type: detectLoginType(identifier.trim()),
        identifier: identifier.trim(),
        password,
        school_code: schoolCode,
        remember_me: rememberMe,
      });
      auth.setToken(tokens.access_token);
      const user = await getMe();
      auth.setAuth(user, tokens.access_token, tokens.refresh_token);
      goto(isPortalUser(user) ? '/portal' : '/dashboard');
    } catch (e: any) {
      formError = e?.response?.data?.detail ?? 'Login failed. Check your credentials.';
    } finally {
      loadingLogin = false;
    }
  }

  function handleKey(e: KeyboardEvent) {
    if (e.key === 'Enter') handleLogin();
  }
</script>

<svelte:head><title>{branding?.school_name ? `Sign in — ${branding.school_name}` : 'Sign in'}</title></svelte:head>

<div class="relative min-h-screen flex flex-col items-center justify-center p-4 overflow-hidden bg-[var(--bg)]">

  <!-- Decorative blobs -->
  <div class="pointer-events-none absolute -top-48 -right-48 h-96 w-96 rounded-full opacity-[0.07] blur-3xl"
       style="background: var(--brand)"></div>
  <div class="pointer-events-none absolute -bottom-48 -left-48 h-96 w-96 rounded-full opacity-[0.05] blur-3xl"
       style="background: var(--brand)"></div>

  <div class="relative w-full max-w-[360px]">
    {#if resolving}
      <div class="rounded-2xl border border-[var(--border)] bg-[var(--card)] p-8 flex items-center justify-center gap-2 text-sm text-[var(--fg-muted)]"
           style="box-shadow: var(--shadow-lg), 0 0 0 1px var(--border);">
        <svg class="h-4 w-4 animate-spin" fill="none" viewBox="0 0 24 24">
          <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/>
          <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z"/>
        </svg>
        Loading…
      </div>
    {:else if schoolCode}
      <LoginForm
        bind:identifier
        bind:password
        bind:showPassword
        bind:rememberMe
        {branding}
        {formError}
        {loadingLogin}
        onKeydown={handleKey}
        onSubmit={handleLogin}
      />
    {:else}
      <div class="rounded-2xl border border-[var(--border)] bg-[var(--card)] p-6 text-center"
           style="box-shadow: var(--shadow-lg), 0 0 0 1px var(--border);">
        <div class="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-2xl"
             style="background: linear-gradient(135deg, var(--brand) 0%, color-mix(in oklab, var(--brand) 65%, #7c3aed) 100%)">
          <svg class="h-6 w-6 text-white" fill="none" stroke="currentColor" stroke-width="1.75" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" d="M13.5 10.5V6.75a4.5 4.5 0 10-9 0v3.75m-.75 11.25h10.5a2.25 2.25 0 002.25-2.25v-6.75a2.25 2.25 0 00-2.25-2.25H3.75a2.25 2.25 0 00-2.25 2.25v6.75a2.25 2.25 0 002.25 2.25z"/>
          </svg>
        </div>
        <h1 class="text-base font-bold text-[var(--fg)]">Page not found</h1>
        <p class="mt-2 text-sm text-[var(--fg-muted)]">
          The page you're looking for doesn't exist.
        </p>
      </div>
    {/if}

  </div>
</div>
