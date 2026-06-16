<script lang="ts">
  import { goto } from '$app/navigation';
  import { onMount } from 'svelte';
  import { auth, isAuthenticated } from '$lib/stores/auth';
  import { login, getMe, detectLoginType } from '$lib/api/auth';
  import { getSchoolBranding, getSchoolByDomain, applyBranding, type SchoolBranding } from '$lib/api/schools';
  import { school } from '$lib/stores/school';
  import { subdomain, customDomain } from '$lib/stores/subdomain';
  import { get } from 'svelte/store';
  import LoginForm from './LoginForm.svelte';

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

    const stored = get(school);
    if (stored) {
      schoolCode = stored.schoolCode || stored.subdomain;
      branding = {
        school_name: stored.name,
        short_name: stored.shortName,
        school_type: stored.schoolType ?? 'BASIC',
        motto: stored.motto ?? null,
        logo_url: stored.logoUrl ?? null,
        brand_color: stored.brandColor,
        school_code: stored.schoolCode || stored.subdomain,
      };
      brandingState = 'found';
    }

    const sub = get(subdomain);
    if (sub) {
      if (brandingState !== 'found') { schoolCode = sub; fetchBranding(); }
      return;
    }

    const cd = get(customDomain);
    if (cd) {
      brandingState = 'loading';
      try {
        const result = await getSchoolByDomain(cd);
        schoolCode = result.school_code;
        branding = result;
        brandingState = 'found';
        applyBranding(result);
        school.set({
          name: result.school_name, shortName: result.short_name ?? result.school_name,
          subdomain: result.subdomain ?? '', schoolCode: result.school_code,
          schoolType: result.school_type, brandColor: result.brand_color,
          logoUrl: result.logo_url, motto: result.motto,
        });
      } catch { brandingState = 'not-found'; }
    }
  });

  async function fetchBranding() {
    const slug = schoolCode.trim().toLowerCase();
    if (!slug) { brandingState = 'idle'; return; }
    brandingState = 'loading';
    try {
      const data = await getSchoolBranding(slug);
      schoolCode = data.school_code;
      branding = data;
      brandingState = 'found';
      applyBranding(data);
      school.set({
        name: data.school_name, shortName: data.short_name ?? data.school_name,
        subdomain: slug, schoolCode: data.school_code,
        schoolType: data.school_type, brandColor: data.brand_color,
        logoUrl: data.logo_url, motto: data.motto,
      });
    } catch {
      branding = null;
      brandingState = 'not-found';
    }
  }

  async function handleLogin() {
    formError = '';
    const loginType = detectLoginType(identifier.trim());
    if (loginType === 'ADMISSION_ID' && !schoolCode.trim()) {
      formError = 'Enter your school code — required for student ID login.';
      return;
    }
    if (!identifier.trim() || !password) {
      formError = 'Enter your email / phone / student ID and password.';
      return;
    }
    if (schoolCode.trim() && brandingState === 'idle') await fetchBranding();
    loadingLogin = true;
    try {
      const tokens = await login({
        login_type: loginType,
        identifier: identifier.trim(),
        password,
        school_code: schoolCode.trim() || undefined,
      });
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

<div class="relative min-h-screen flex flex-col items-center justify-center p-4 overflow-hidden bg-[var(--bg)]">

  <!-- Decorative blobs -->
  <div class="pointer-events-none absolute -top-48 -right-48 h-96 w-96 rounded-full opacity-[0.07] blur-3xl"
       style="background: var(--brand)"></div>
  <div class="pointer-events-none absolute -bottom-48 -left-48 h-96 w-96 rounded-full opacity-[0.05] blur-3xl"
       style="background: var(--brand)"></div>

  <div class="relative w-full max-w-[360px]">
    <LoginForm
      {isSubdomain}
      bind:schoolCode
      bind:identifier
      bind:password
      bind:showPassword
      {branding}
      {brandingState}
      {formError}
      {loadingLogin}
      onSchoolCodeBlur={fetchBranding}
      onKeydown={handleKey}
      onSubmit={handleLogin}
    />

    {#if !isSubdomain}
      <p class="mt-6 text-center text-xs text-[var(--fg-subtle)]">
        Platform admin?
        <a href="/" class="font-semibold text-[var(--fg-muted)] underline-offset-2 hover:underline transition">
          Sign in here →
        </a>
      </p>
    {/if}

    <p class="mt-4 text-center text-[10px] text-[var(--fg-subtle)]">
      Powered by <span class="font-semibold">TTEK-SMS</span>
    </p>
  </div>
</div>
