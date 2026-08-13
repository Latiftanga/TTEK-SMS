<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import { get } from 'svelte/store';
  import { school } from '$lib/stores/school';
  import { subdomain, customDomain } from '$lib/stores/subdomain';
  import { detectLoginType, forgotPassword } from '$lib/api/auth';
  import { getSchoolBranding, getSchoolByDomain, applyBranding } from '$lib/api/schools';
  import OtpStep from './OtpStep.svelte';
  import NewPasswordStep from './NewPasswordStep.svelte';

  type Step = 'identifier' | 'otp' | 'password' | 'done';
  let step = $state<Step>('identifier');

  // Same rule as the login page: this page only works from a school's own
  // subdomain/custom domain, resolved from the actual URL — never from a
  // cached session on the bare domain, since identity is tied to the URL,
  // not to browser storage.
  const isSubdomain = get(subdomain) !== null || get(customDomain) !== null;

  let schoolCode  = $state('');
  let schoolName  = $state('');
  let schoolReady = $state(false);

  // Step 1 state
  let identifier  = $state('');
  let sendPending = $state(false);
  let sendError   = $state('');

  // State passed between steps
  let loginTypeState  = $state('');
  let identifierState = $state('');
  let devOtp          = $state('');
  let resetToken      = $state('');

  onMount(async () => {
    if (!isSubdomain) {
      schoolReady = true;
      return;
    }

    // Paint instantly from a cached session while confirming from the URL
    // below — pure UX, never the reason the form is shown.
    const stored = get(school);
    if (stored?.schoolCode) {
      schoolCode = stored.schoolCode;
      schoolName = stored.name;
    }

    const sub = get(subdomain);
    if (sub) {
      try {
        const data = await getSchoolBranding(sub);
        schoolCode = data.school_code;
        schoolName = data.school_name;
        applyBranding(data);
        school.set({
          name: data.school_name, shortName: data.short_name ?? data.school_name,
          subdomain: sub, schoolCode: data.school_code,
          schoolType: data.school_type, brandColor: data.brand_color,
          logoUrl: data.logo_url, motto: data.motto,
        });
      } catch {
        schoolCode = '';
        schoolName = '';
      }
    } else {
      const cd = get(customDomain);
      if (cd) {
        try {
          const result = await getSchoolByDomain(cd);
          schoolCode = result.school_code;
          schoolName = result.school_name;
          applyBranding(result);
          school.set({
            name: result.school_name,
            shortName: result.short_name ?? result.school_name,
            subdomain: result.subdomain ?? '',
            schoolCode: result.school_code,
            schoolType: result.school_type,
            brandColor: result.brand_color,
            logoUrl: result.logo_url,
            motto: result.motto,
          });
        } catch {
          schoolCode = '';
          schoolName = '';
        }
      }
    }
    schoolReady = true;
  });

  async function handleSend() {
    sendError = '';
    const trimmed = identifier.trim();
    if (!trimmed) { sendError = 'Enter your email, phone number, or student ID.'; return; }
    const loginType = detectLoginType(trimmed);
    sendPending = true;
    try {
      const res = await forgotPassword({
        login_type: loginType,
        identifier: trimmed,
        school_code: schoolCode,
      });
      loginTypeState  = loginType;
      identifierState = trimmed;
      devOtp          = res.dev_otp ?? '';
      step = 'otp';
    } catch (e: unknown) {
      sendError = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
        ?? 'Could not send code. Try again.';
    } finally {
      sendPending = false;
    }
  }

  async function handleResend(): Promise<{ newDevOtp: string }> {
    const res = await forgotPassword({
      login_type: loginTypeState as any,
      identifier: identifierState,
      school_code: schoolCode,
    });
    return { newDevOtp: res.dev_otp ?? '' };
  }

  const STEP_INDEX: Record<Step, number> = { identifier: 0, otp: 1, password: 2, done: -1 };
  const ICONS: Record<Step, string> = {
    identifier: 'M16.5 10.5V6.75a4.5 4.5 0 10-9 0v3.75m-.75 11.25h10.5a2.25 2.25 0 002.25-2.25v-6.75a2.25 2.25 0 00-2.25-2.25H6.75a2.25 2.25 0 00-2.25 2.25v6.75a2.25 2.25 0 002.25 2.25z',
    otp:        'M10.5 1.5H8.25A2.25 2.25 0 006 3.75v16.5a2.25 2.25 0 002.25 2.25h7.5A2.25 2.25 0 0018 20.25V3.75a2.25 2.25 0 00-2.25-2.25H13.5m-3 0V3h3V1.5m-3 0h3m-3 8.25h3m-3 3.75h3m-3 3.75h3',
    password:   'M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z',
    done:       '',
  };
  const TITLES: Record<Step, string> = {
    identifier: 'Forgot your password?',
    otp:        'Enter your code',
    password:   'Set new password',
    done:       '',
  };
  const SUBTITLES: Record<Step, string> = {
    identifier: "We'll send a 6-digit code to your registered phone number.",
    otp:        `A 6-digit code was sent to your phone.`,
    password:   'Choose something strong and memorable.',
    done:       '',
  };
</script>

<svelte:head><title>Reset password</title></svelte:head>

<div class="relative min-h-screen flex flex-col items-center justify-center p-4 overflow-hidden bg-[var(--bg)]">
  <div class="pointer-events-none absolute -top-48 -right-48 h-96 w-96 rounded-full opacity-[0.07] blur-3xl" style="background: var(--brand)"></div>
  <div class="pointer-events-none absolute -bottom-48 -left-48 h-96 w-96 rounded-full opacity-[0.05] blur-3xl" style="background: var(--brand)"></div>

  <div class="relative w-full max-w-[360px]">

    {#if step !== 'done'}
      <!-- Step indicators -->
      <div class="flex items-center justify-center mb-8 gap-2">
        {#each ['identifier', 'otp', 'password'] as s, i}
          {@const active = step === s}
          {@const past   = STEP_INDEX[step] > i}
          <div class="flex items-center gap-2">
            <div class="flex h-7 w-7 items-center justify-center rounded-full text-xs font-bold transition-all duration-300"
                 style="background: {active ? 'var(--brand)' : past ? 'color-mix(in oklab, var(--brand) 25%, transparent)' : 'var(--hover)'};
                        color: {active ? 'white' : past ? 'var(--brand)' : 'var(--fg-muted)'}">
              {#if past}
                <svg class="h-3.5 w-3.5" fill="none" stroke="currentColor" stroke-width="3" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7"/>
                </svg>
              {:else}
                {i + 1}
              {/if}
            </div>
            {#if i < 2}
              <div class="h-px w-6 transition-all duration-300" style="background: {past ? 'var(--brand)' : 'var(--border)'}"></div>
            {/if}
          </div>
        {/each}
      </div>

      <!-- Step header -->
      <div class="mb-6 text-center">
        <div class="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-2xl shadow"
             style="background: linear-gradient(135deg, var(--brand) 0%, color-mix(in oklab, var(--brand) 65%, #7c3aed) 100%)">
          <svg class="h-7 w-7 text-white" fill="none" stroke="currentColor" stroke-width="1.75" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" d={ICONS[step]}/>
          </svg>
        </div>
        <h1 class="text-xl font-bold text-[var(--fg)]">{TITLES[step]}</h1>
        <p class="mt-1.5 text-sm text-[var(--fg-muted)]">{SUBTITLES[step]}</p>
      </div>

      <!-- Step content card -->
      <div class="rounded-2xl border border-[var(--border)] bg-[var(--card)] p-6"
           style="box-shadow: var(--shadow-lg), 0 0 0 1px var(--border)">

        {#if step === 'identifier'}
          {#if !schoolReady}
            <div class="flex items-center justify-center gap-2 py-4 text-sm text-[var(--fg-muted)]">
              <svg class="h-4 w-4 animate-spin" fill="none" viewBox="0 0 24 24">
                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/>
                <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z"/>
              </svg>
              Loading…
            </div>
          {:else if !schoolCode}
            <div class="py-2 text-center">
              <p class="text-sm text-[var(--fg-muted)]">
                This page is specific to your school. Please use your school's own sign-in link, then choose "Forgot password?" from there.
              </p>
              <p class="mt-4 text-xs">
                <a href="/login" class="text-[var(--fg-muted)] hover:text-[var(--fg)] hover:underline transition">← Back to sign in</a>
              </p>
            </div>
          {:else}
            <div class="space-y-4">
              {#if schoolName || schoolCode}
                <div class="flex items-center gap-2 rounded-xl bg-[var(--brand-dim)] px-3 py-2">
                  <div class="h-2 w-2 rounded-full flex-shrink-0" style="background: var(--brand)"></div>
                  <p class="text-xs text-[var(--fg-muted)]">
                    Resetting password for <span class="font-semibold text-[var(--fg)]">{schoolName || schoolCode}</span>
                  </p>
                </div>
              {/if}

              <div>
                <label class="block text-[0.8125rem] font-semibold text-[var(--fg)] mb-1.5" for="reset-identifier">Email / Phone / Student ID</label>
                <input id="reset-identifier" type="text" bind:value={identifier}
                  onkeydown={(e) => e.key === 'Enter' && handleSend()}
                  placeholder="you@school.com, 024…, or student ID" autocomplete="username"
                  class="w-full rounded-xl border border-[var(--border-strong)] bg-[var(--input-bg)]
                         px-4 py-3 text-sm text-[var(--fg)] placeholder:text-[var(--fg-subtle)]
                         focus:outline-none focus:ring-2 focus:ring-[var(--brand)]/20 focus:border-[var(--brand)] transition" />
              </div>

              {#if sendError}
                <p class="rounded-xl bg-red-50 dark:bg-red-950/30 px-4 py-3 text-sm text-red-600 dark:text-red-400">{sendError}</p>
              {/if}

              <button onclick={handleSend} disabled={sendPending}
                class="w-full rounded-xl py-3 text-sm font-semibold text-white transition active:scale-[0.98] disabled:opacity-60"
                style="background: linear-gradient(135deg, var(--brand) 0%, color-mix(in oklab, var(--brand) 70%, #7c3aed) 100%);
                       box-shadow: 0 2px 12px rgba(var(--brand-rgb), 0.35);">
                {#if sendPending}
                  <span class="flex items-center justify-center gap-2">
                    <svg class="h-4 w-4 animate-spin" fill="none" viewBox="0 0 24 24">
                      <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/>
                      <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z"/>
                    </svg>
                    Sending…
                  </span>
                {:else}
                  Send code
                {/if}
              </button>

              <p class="text-center text-xs">
                <a href="/login" class="text-[var(--fg-muted)] hover:text-[var(--fg)] hover:underline transition">← Back to sign in</a>
              </p>
            </div>
          {/if}

        {:else if step === 'otp'}
          <OtpStep
            loginType={loginTypeState as any}
            identifier={identifierState}
            {schoolCode}
            {devOtp}
            onSuccess={(token) => { resetToken = token; step = 'password'; }}
            onBack={() => step = 'identifier'}
            onResend={handleResend}
          />

        {:else if step === 'password'}
          <NewPasswordStep
            {resetToken}
            onSuccess={() => step = 'done'}
          />
        {/if}
      </div>
    {:else}
      <!-- Done -->
      <div class="text-center space-y-6">
        <div class="mx-auto flex h-20 w-20 items-center justify-center rounded-full shadow-lg"
             style="background: linear-gradient(135deg, #22c55e 0%, #16a34a 100%)">
          <svg class="h-10 w-10 text-white" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
          </svg>
        </div>
        <div>
          <h1 class="text-2xl font-bold text-[var(--fg)]">Password changed!</h1>
          <p class="mt-2 text-sm text-[var(--fg-muted)]">Your password has been updated. You can now sign in.</p>
        </div>
        <button onclick={() => goto('/login')}
          class="w-full rounded-xl py-3 text-sm font-semibold text-white transition active:scale-[0.98]"
          style="background: linear-gradient(135deg, var(--brand) 0%, color-mix(in oklab, var(--brand) 70%, #7c3aed) 100%)">
          Sign in now →
        </button>
      </div>
    {/if}

  </div>
</div>
