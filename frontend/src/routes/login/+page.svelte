<script lang="ts">
  import { goto } from '$app/navigation';
  import { onMount } from 'svelte';
  import { auth, isAuthenticated } from '$lib/stores/auth';
  import { login, getMe, detectLoginType } from '$lib/api/auth';
  import { getSchoolBranding, getSchoolByDomain, applyBranding, type SchoolBranding } from '$lib/api/schools';
  import { school } from '$lib/stores/school';
  import { subdomain, customDomain } from '$lib/stores/subdomain';
  import { get } from 'svelte/store';

  // True on any school-scoped URL (platform subdomain OR school-owned custom domain)
  const isSubdomain = get(subdomain) !== null || get(customDomain) !== null;

  let schoolCode   = $state('');
  let identifier   = $state('');
  let password     = $state('');
  let showPassword = $state(false);

  let branding      = $state<SchoolBranding | null>(null);
  let brandingState = $state<'idle' | 'loading' | 'found' | 'not-found'>('idle');
  let formError     = $state('');
  let loadingLogin  = $state(false);

  onMount(async () => {
    if (get(isAuthenticated)) goto('/dashboard');

    // Restore branding from persisted school store (return visitors)
    const stored = get(school);
    if (stored) {
      schoolCode = stored.schoolCode || stored.subdomain;
      branding = {
        school_name: stored.name,
        short_name: stored.shortName,
        school_type: 'BASIC',
        motto: stored.motto ?? null,
        logo_url: stored.logoUrl ?? null,
        brand_color: stored.brandColor,
        school_code: stored.schoolCode || stored.subdomain,
      };
      brandingState = 'found';
    }

    // Platform subdomain (presec.ttek-sms.com): fetch branding to get the real GES school_code
    const sub = get(subdomain);
    if (sub) {
      if (brandingState !== 'found') {
        schoolCode = sub;
        fetchBranding();
      }
      // If brandingState is 'found', schoolCode was already restored from the store (GES code)
      return;
    }

    // Custom domain (portal.presec.com): resolve via API to get school_code + branding
    const cd = get(customDomain);
    if (cd) {
      brandingState = 'loading';
      try {
        const result = await getSchoolByDomain(cd);
        // school_code is what the login API expects (not the subdomain slug)
        schoolCode = result.school_code;
        branding = result;
        brandingState = 'found';
        applyBranding(result);
        school.set({
          name: result.school_name,
          shortName: result.short_name ?? result.school_name,
          subdomain: result.subdomain ?? '',
          schoolCode: result.school_code,
          brandColor: result.brand_color,
          logoUrl: result.logo_url,
          motto: result.motto,
        });
      } catch {
        brandingState = 'not-found';
      }
    }
  });

  async function fetchBranding() {
    const slug = schoolCode.trim().toLowerCase();
    if (!slug) { brandingState = 'idle'; return; }

    brandingState = 'loading';
    try {
      const data = await getSchoolBranding(slug);
      // Use the GES school_code from the response, not the URL slug
      schoolCode = data.school_code;
      branding = data;
      brandingState = 'found';
      applyBranding(data);
      school.set({
        name: data.school_name,
        shortName: data.short_name ?? data.school_name,
        subdomain: slug,
        schoolCode: data.school_code,
        brandColor: data.brand_color,
        logoUrl: data.logo_url,
        motto: data.motto,
      });
    } catch {
      branding = null;
      brandingState = 'not-found';
    }
  }

  function onSchoolCodeBlur() {
    if (!isSubdomain) fetchBranding();
  }

  async function handleLogin() {
    formError = '';

    const loginType = detectLoginType(identifier.trim());
    if (loginType === 'ADMISSION_ID' && !schoolCode.trim()) {
      formError = 'Enter your school code — it is required for student ID login.';
      return;
    }
    if (!identifier.trim() || !password) {
      formError = 'Fill in your email / phone / student ID and password.';
      return;
    }

    // If school code given but lookup hasn't run yet, do it now
    if (schoolCode.trim() && brandingState === 'idle') await fetchBranding();

    loadingLogin = true;
    try {
      const tokens = await login({
        login_type: loginType,
        identifier: identifier.trim(),
        password,
        school_code: schoolCode.trim() || undefined,
      });
      // Set token in store BEFORE getMe() so the Axios interceptor attaches it.
      // Without this, getMe() goes out with no Authorization header → 403.
      auth.setToken(tokens.access_token);
      const user = await getMe();
      auth.setAuth(user, tokens.access_token, tokens.refresh_token);
      goto('/dashboard');
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

<svelte:head><title>Sign in — {branding?.school_name ?? 'TTEK-SMS'}</title></svelte:head>

<div class="min-h-screen flex flex-col items-center justify-center bg-[var(--bg)] p-4">
  <div class="w-full max-w-sm">

    <!-- School identity header -->
    <div class="mb-8 text-center">
      {#if branding?.logo_url}
        <img src={branding.logo_url} alt={branding.school_name}
             class="mx-auto h-16 w-auto object-contain mb-3" />
      {:else}
        <div class="mx-auto h-16 w-16 rounded-2xl flex items-center justify-center
                    text-white text-2xl font-bold mb-3 transition-colors duration-500"
             style="background-color: var(--brand)">
          {branding ? (branding.short_name ?? branding.school_name).slice(0, 2).toUpperCase() : 'S'}
        </div>
      {/if}
      <h1 class="text-xl font-bold text-[var(--fg)] transition-all duration-300">
        {branding?.school_name ?? 'Sign in to your school'}
      </h1>
      {#if branding?.motto}
        <p class="text-xs text-[var(--fg-muted)] mt-1 italic">{branding.motto}</p>
      {/if}
    </div>

    <div class="bg-[var(--card)] rounded-2xl shadow-sm border border-[var(--border)] p-6 space-y-4">

      <!-- School code — hidden on subdomains (already known from the URL) -->
      {#if !isSubdomain}
        <div>
          <label class="block text-sm font-medium text-[var(--fg)] mb-1" for="school-code">
            School code
          </label>
          <div class="relative">
            <input
              id="school-code"
              type="text"
              bind:value={schoolCode}
              onblur={onSchoolCodeBlur}
              onkeydown={handleKey}
              placeholder="e.g. presec"
              autocomplete="off"
              spellcheck={false}
              class="w-full rounded-xl border border-[var(--border)] bg-[var(--input-bg)]
                     px-4 py-3 pr-10 text-sm text-[var(--fg)] placeholder:text-[var(--fg-muted)]
                     focus:outline-none focus:ring-2 focus:ring-[var(--brand)]/40
                     focus:border-[var(--brand)] transition lowercase"
            />
            <span class="absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none">
              {#if brandingState === 'loading'}
                <svg class="h-4 w-4 animate-spin text-[var(--fg-muted)]" fill="none" viewBox="0 0 24 24">
                  <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/>
                  <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z"/>
                </svg>
              {:else if brandingState === 'found'}
                <svg class="h-4 w-4 text-emerald-500" fill="none" viewBox="0 0 24 24"
                     stroke="currentColor" stroke-width="2.5">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7"/>
                </svg>
              {:else if brandingState === 'not-found'}
                <svg class="h-4 w-4 text-red-400" fill="none" viewBox="0 0 24 24"
                     stroke="currentColor" stroke-width="2.5">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12"/>
                </svg>
              {/if}
            </span>
          </div>
          {#if brandingState === 'not-found'}
            <p class="mt-1 text-xs text-red-500">School not found — check the code and try again.</p>
          {/if}
        </div>
      {/if}

      <!-- Identifier -->
      <div>
        <label class="block text-sm font-medium text-[var(--fg)] mb-1" for="identifier">
          Email / Phone / Student ID
        </label>
        <input
          id="identifier"
          type="text"
          bind:value={identifier}
          onkeydown={handleKey}
          placeholder="you@example.com or 0244…"
          autocomplete="username"
          class="w-full rounded-xl border border-[var(--border)] bg-[var(--input-bg)]
                 px-4 py-3 text-sm text-[var(--fg)] placeholder:text-[var(--fg-muted)]
                 focus:outline-none focus:ring-2 focus:ring-[var(--brand)]/40
                 focus:border-[var(--brand)] transition"
        />
      </div>

      <!-- Password with show/hide toggle -->
      <div>
        <label class="block text-sm font-medium text-[var(--fg)] mb-1" for="password">Password</label>
        <div class="relative">
          <input
            id="password"
            type={showPassword ? 'text' : 'password'}
            bind:value={password}
            onkeydown={handleKey}
            placeholder="••••••••"
            autocomplete="current-password"
            class="w-full rounded-xl border border-[var(--border)] bg-[var(--input-bg)]
                   px-4 py-3 pr-10 text-sm text-[var(--fg)] placeholder:text-[var(--fg-muted)]
                   focus:outline-none focus:ring-2 focus:ring-[var(--brand)]/40
                   focus:border-[var(--brand)] transition"
          />
          <button
            type="button"
            onclick={() => showPassword = !showPassword}
            class="absolute right-3 top-1/2 -translate-y-1/2 text-[var(--fg-muted)]
                   hover:text-[var(--fg)] transition cursor-pointer"
            aria-label={showPassword ? 'Hide password' : 'Show password'}
          >
            {#if showPassword}
              <svg class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                <path stroke-linecap="round" stroke-linejoin="round"
                  d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7
                     a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878
                     l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l3.59
                     3.59m0 0A9.953 9.953 0 0112 5c4.478 0 8.268 2.943 9.543 7a10.025
                     10.025 0 01-4.132 5.411m0 0L21 21"/>
              </svg>
            {:else}
              <svg class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                <path stroke-linecap="round" stroke-linejoin="round"
                  d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"/>
                <path stroke-linecap="round" stroke-linejoin="round"
                  d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943
                     9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"/>
              </svg>
            {/if}
          </button>
        </div>
      </div>

      {#if formError}
        <p class="text-sm text-red-500">{formError}</p>
      {/if}

      <button
        onclick={handleLogin}
        disabled={loadingLogin}
        class="w-full rounded-xl py-3 text-sm font-semibold text-white transition
               active:scale-95 disabled:opacity-60 cursor-pointer"
        style="background-color: var(--brand)"
      >
        {loadingLogin ? 'Signing in…' : 'Sign in'}
      </button>

    </div>

    <!-- Only shown on the root domain, never on school subdomains -->
    {#if !isSubdomain}
      <p class="mt-6 text-center text-xs text-[var(--fg-muted)]">
        Platform admin?
        <a href="/" class="font-medium underline hover:text-[var(--fg)] transition">Sign in here →</a>
      </p>
    {/if}

  </div>
</div>
