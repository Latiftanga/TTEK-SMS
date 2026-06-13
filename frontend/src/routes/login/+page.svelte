<script lang="ts">
  import { goto } from '$app/navigation';
  import { onMount } from 'svelte';
  import { auth, isAuthenticated } from '$lib/stores/auth';
  import { login, getMe, detectLoginType } from '$lib/api/auth';
  import { getSchoolBranding, applyBranding, type SchoolBranding } from '$lib/api/schools';
  import { get } from 'svelte/store';

  // ── Step management ───────────────────────────────────────────────────────
  type Step = 'school' | 'credentials';
  let step = $state<Step>('school');
  let branding = $state<SchoolBranding | null>(null);
  let subdomain = $state('');

  // ── Form fields ───────────────────────────────────────────────────────────
  let identifier = $state('');
  let password = $state('');
  let schoolCode = $state('');
  let error = $state('');
  let loadingBranding = $state(false);
  let loadingLogin = $state(false);

  onMount(() => {
    if (get(isAuthenticated)) goto('/dashboard');
    // Pre-fill subdomain from hostname
    const host = window.location.hostname;
    const parts = host.split('.');
    if (parts.length >= 3) subdomain = parts[0];
  });

  async function lookupSchool() {
    if (!subdomain.trim()) { error = 'Enter your school code'; return; }
    error = '';
    loadingBranding = true;
    try {
      const data = await getSchoolBranding(subdomain.trim().toLowerCase());
      branding = data;
      schoolCode = subdomain.trim().toLowerCase();
      applyBranding(data);
      step = 'credentials';
    } catch {
      error = 'School not found. Check the code and try again.';
    } finally {
      loadingBranding = false;
    }
  }

  async function handleLogin() {
    if (!identifier.trim() || !password) { error = 'Enter your credentials'; return; }
    error = '';
    loadingLogin = true;
    try {
      const loginType = detectLoginType(identifier.trim());
      const tokens = await login({
        login_type: loginType,
        identifier: identifier.trim(),
        password,
        school_code: loginType === 'ADMISSION_ID' ? schoolCode : undefined,
      });
      // Persist access token for hydration across page reloads
      localStorage.setItem('access_token', tokens.access_token);
      const user = await getMe();
      auth.setAuth(user, tokens.access_token, tokens.refresh_token);
      goto('/dashboard');
    } catch (e: any) {
      error = e?.response?.data?.detail ?? 'Login failed. Check your credentials.';
    } finally {
      loadingLogin = false;
    }
  }

  function handleSchoolKey(e: KeyboardEvent) {
    if (e.key === 'Enter') lookupSchool();
  }

  function handleLoginKey(e: KeyboardEvent) {
    if (e.key === 'Enter') handleLogin();
  }
</script>

<div class="min-h-screen flex flex-col items-center justify-center bg-surface p-4">
  <div class="w-full max-w-sm">

    <!-- Logo / branding header -->
    <div class="mb-8 text-center">
      {#if branding?.logo_url}
        <img src={branding.logo_url} alt={branding.school_name} class="mx-auto h-16 w-auto object-contain mb-3" />
      {:else}
        <div class="mx-auto h-16 w-16 rounded-2xl flex items-center justify-center text-white text-2xl font-bold mb-3"
             style="background-color: var(--brand)">
          {branding ? (branding.short_name ?? branding.school_name).slice(0, 2).toUpperCase() : 'S'}
        </div>
      {/if}
      <h1 class="text-xl font-bold text-gray-900">
        {branding?.school_name ?? 'School Management'}
      </h1>
      {#if branding?.motto}
        <p class="text-xs text-gray-500 mt-1 italic">{branding.motto}</p>
      {/if}
    </div>

    <div class="bg-white rounded-2xl shadow-sm border border-gray-100 p-6">

      {#if step === 'school'}
        <!-- Step 1: Enter school code -->
        <h2 class="text-lg font-semibold text-gray-800 mb-1">Find your school</h2>
        <p class="text-sm text-gray-500 mb-5">Enter the code given by your school administrator.</p>

        <label class="block text-sm font-medium text-gray-700 mb-1" for="subdomain">School code</label>
        <input
          id="subdomain"
          type="text"
          bind:value={subdomain}
          onkeydown={handleSchoolKey}
          placeholder="e.g. presec"
          autocomplete="off"
          class="w-full rounded-xl border border-gray-200 px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-brand/40 focus:border-brand transition"
        />

        {#if error}
          <p class="mt-2 text-sm text-red-600">{error}</p>
        {/if}

        <button
          onclick={lookupSchool}
          disabled={loadingBranding}
          class="mt-4 w-full rounded-xl py-3 text-sm font-semibold text-white transition active:scale-95 disabled:opacity-60"
          style="background-color: var(--brand)"
        >
          {loadingBranding ? 'Looking up…' : 'Continue →'}
        </button>

      {:else if step === 'credentials' && branding}
        <!-- Step 2: Login form -->
        <h2 class="text-base font-semibold text-gray-800 mb-4">Sign in to continue</h2>

        <label class="block text-sm font-medium text-gray-700 mb-1" for="identifier">
          Email / Phone / Student ID
        </label>
        <input
          id="identifier"
          type="text"
          bind:value={identifier}
          onkeydown={handleLoginKey}
          placeholder="you@example.com or 0244…"
          autocomplete="username"
          class="w-full rounded-xl border border-gray-200 px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-brand/40 focus:border-brand transition"
        />

        <label class="block text-sm font-medium text-gray-700 mt-3 mb-1" for="password">Password</label>
        <input
          id="password"
          type="password"
          bind:value={password}
          onkeydown={handleLoginKey}
          placeholder="••••••••"
          autocomplete="current-password"
          class="w-full rounded-xl border border-gray-200 px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-brand/40 focus:border-brand transition"
        />

        {#if error}
          <p class="mt-2 text-sm text-red-600">{error}</p>
        {/if}

        <button
          onclick={handleLogin}
          disabled={loadingLogin}
          class="mt-5 w-full rounded-xl py-3 text-sm font-semibold text-white transition active:scale-95 disabled:opacity-60"
          style="background-color: var(--brand)"
        >
          {loadingLogin ? 'Signing in…' : 'Sign in'}
        </button>

        <button
          onclick={() => { step = 'school'; error = ''; }}
          class="mt-3 w-full text-center text-xs text-gray-400 hover:text-gray-600 transition"
        >
          ← Wrong school?
        </button>
      {/if}

    </div>

    <p class="mt-6 text-center text-xs text-gray-400">
      Powered by Tagnatek TTEK-SMS
    </p>
  </div>
</div>
