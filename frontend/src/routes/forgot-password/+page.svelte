<script lang="ts">
  import { tick } from 'svelte';
  import { goto } from '$app/navigation';
  import { get } from 'svelte/store';
  import { school } from '$lib/stores/school';
  import { subdomain } from '$lib/stores/subdomain';
  import { detectLoginType, forgotPassword, verifyOtp, resetPassword } from '$lib/api/auth';

  type Step = 'identifier' | 'otp' | 'password' | 'done';
  let step = $state<Step>('identifier');

  // Step 1
  let identifier  = $state('');
  let schoolCode  = $state(get(school)?.schoolCode ?? get(subdomain) ?? '');
  let sendPending = $state(false);
  let sendError   = $state('');

  // Step 2 — OTP
  let otpDigits   = $state<string[]>(['', '', '', '', '', '']);
  let otpInputs   = $state<HTMLInputElement[]>([]);
  let otpPending  = $state(false);
  let otpError    = $state('');
  let countdown   = $state(600);
  let canResend   = $state(false);
  let resendIn    = $state(30);
  let timerHandle: ReturnType<typeof setInterval> | null = null;
  let resetToken  = $state('');
  let loginTypeState   = $state('');
  let identifierState  = $state('');
  let schoolCodeState  = $state('');

  // Step 3 — new password
  let newPassword  = $state('');
  let confirmPw    = $state('');
  let showPw       = $state(false);
  let resetPending = $state(false);
  let resetError   = $state('');

  function startCountdown() {
    countdown = 600;
    canResend = false;
    resendIn  = 30;
    if (timerHandle) clearInterval(timerHandle);
    timerHandle = setInterval(() => {
      countdown = Math.max(0, countdown - 1);
      resendIn  = Math.max(0, resendIn - 1);
      if (resendIn === 0) canResend = true;
      if (countdown === 0 && timerHandle) { clearInterval(timerHandle); timerHandle = null; }
    }, 1000);
  }

  function fmtCountdown(s: number) {
    const m = Math.floor(s / 60).toString().padStart(2, '0');
    return `${m}:${(s % 60).toString().padStart(2, '0')}`;
  }

  async function handleSend() {
    sendError = '';
    const trimmed = identifier.trim();
    if (!trimmed) { sendError = 'Enter your email or phone number.'; return; }
    const loginType = detectLoginType(trimmed);
    if (loginType === 'ADMISSION_ID' && !schoolCode.trim()) {
      sendError = 'Enter your school code for student ID login.';
      return;
    }
    sendPending = true;
    try {
      await forgotPassword({
        login_type: loginType,
        identifier: trimmed,
        school_code: schoolCode.trim() || undefined,
      });
      loginTypeState  = loginType;
      identifierState = trimmed;
      schoolCodeState = schoolCode.trim();
      otpDigits       = ['', '', '', '', '', ''];
      step = 'otp';
      startCountdown();
      await tick();
      otpInputs[0]?.focus();
    } catch (e: unknown) {
      sendError = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
        ?? 'Could not send code. Try again.';
    } finally {
      sendPending = false;
    }
  }

  async function handleResend() {
    if (!canResend) return;
    canResend = false;
    resendIn  = 30;
    otpDigits = ['', '', '', '', '', ''];
    otpError  = '';
    try {
      await forgotPassword({
        login_type: loginTypeState as any,
        identifier: identifierState,
        school_code: schoolCodeState || undefined,
      });
      startCountdown();
      await tick();
      otpInputs[0]?.focus();
    } catch {
      otpError = 'Could not resend code. Try again.';
    }
  }

  function otpValue() { return otpDigits.join(''); }

  function handleOtpInput(e: Event & { currentTarget: HTMLInputElement }, i: number) {
    const val = e.currentTarget.value.replace(/\D/g, '').slice(-1);
    otpDigits[i] = val;
    if (val && i < 5) otpInputs[i + 1]?.focus();
    if (otpValue().length === 6) submitOtp();
  }

  function handleOtpKeydown(e: KeyboardEvent & { currentTarget: HTMLInputElement }, i: number) {
    if (e.key === 'Backspace' && !otpDigits[i] && i > 0) otpInputs[i - 1]?.focus();
    if (e.key === 'ArrowLeft'  && i > 0) otpInputs[i - 1]?.focus();
    if (e.key === 'ArrowRight' && i < 5) otpInputs[i + 1]?.focus();
  }

  function handleOtpPaste(e: ClipboardEvent) {
    e.preventDefault();
    const pasted = (e.clipboardData?.getData('text') ?? '').replace(/\D/g, '').slice(0, 6);
    for (let i = 0; i < 6; i++) otpDigits[i] = pasted[i] ?? '';
    otpInputs[Math.min(pasted.length, 5)]?.focus();
    if (pasted.length === 6) submitOtp();
  }

  async function submitOtp() {
    const code = otpValue();
    if (code.length !== 6) return;
    otpPending = true;
    otpError   = '';
    try {
      const result = await verifyOtp({
        login_type: loginTypeState as any,
        identifier: identifierState,
        school_code: schoolCodeState || undefined,
        otp: code,
      });
      resetToken = result.reset_token;
      if (timerHandle) { clearInterval(timerHandle); timerHandle = null; }
      step = 'password';
    } catch (e: unknown) {
      otpError  = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
        ?? 'Invalid code.';
      otpDigits = ['', '', '', '', '', ''];
      await tick();
      otpInputs[0]?.focus();
    } finally {
      otpPending = false;
    }
  }

  function strength(pw: string) {
    if (!pw) return { score: 0, label: '', color: '' };
    let s = 0;
    if (pw.length >= 8)         s++;
    if (pw.length >= 12)        s++;
    if (/[A-Z]/.test(pw))       s++;
    if (/[0-9]/.test(pw))       s++;
    if (/[^A-Za-z0-9]/.test(pw)) s++;
    if (s <= 1) return { score: s, label: 'Weak',   color: '#ef4444' };
    if (s === 2) return { score: s, label: 'Fair',   color: '#f97316' };
    if (s === 3) return { score: s, label: 'Good',   color: '#eab308' };
    return          { score: s, label: 'Strong', color: '#22c55e' };
  }

  let pwStrength = $derived(strength(newPassword));

  async function handleReset() {
    resetError = '';
    if (newPassword.length < 8) { resetError = 'Password must be at least 8 characters.'; return; }
    if (newPassword !== confirmPw) { resetError = 'Passwords do not match.'; return; }
    resetPending = true;
    try {
      await resetPassword({ token: resetToken, new_password: newPassword });
      step = 'done';
    } catch (e: unknown) {
      resetError = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
        ?? 'Reset failed. Please start over.';
    } finally {
      resetPending = false;
    }
  }
</script>

<svelte:head><title>Reset password — TTEK-SMS</title></svelte:head>

<div class="relative min-h-screen flex flex-col items-center justify-center p-4 overflow-hidden bg-[var(--bg)]">
  <div class="pointer-events-none absolute -top-48 -right-48 h-96 w-96 rounded-full opacity-[0.07] blur-3xl"
       style="background: var(--brand)"></div>
  <div class="pointer-events-none absolute -bottom-48 -left-48 h-96 w-96 rounded-full opacity-[0.05] blur-3xl"
       style="background: var(--brand)"></div>

  <div class="relative w-full max-w-[360px]">

    <!-- Step indicators -->
    {#if step !== 'done'}
      <div class="flex items-center justify-center mb-8 gap-2">
        {#each ['identifier', 'otp', 'password'] as s, i}
          {@const active = step === s}
          {@const past   = ['identifier', 'otp', 'password'].indexOf(step) > i}
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
              <div class="h-px w-6 transition-all duration-300"
                   style="background: {past ? 'var(--brand)' : 'var(--border)'}"></div>
            {/if}
          </div>
        {/each}
      </div>
    {/if}

    <!-- ── Step 1: Identifier ───────────────────────────────── -->
    {#if step === 'identifier'}
      <div class="mb-6 text-center">
        <div class="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-2xl shadow"
             style="background: linear-gradient(135deg, var(--brand) 0%, color-mix(in oklab, var(--brand) 65%, #7c3aed) 100%)">
          <svg class="h-7 w-7 text-white" fill="none" stroke="currentColor" stroke-width="1.75" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" d="M16.5 10.5V6.75a4.5 4.5 0 10-9 0v3.75m-.75 11.25h10.5a2.25 2.25 0 002.25-2.25v-6.75a2.25 2.25 0 00-2.25-2.25H6.75a2.25 2.25 0 00-2.25 2.25v6.75a2.25 2.25 0 002.25 2.25z"/>
          </svg>
        </div>
        <h1 class="text-xl font-bold text-[var(--fg)]">Forgot your password?</h1>
        <p class="mt-1.5 text-sm text-[var(--fg-muted)]">We'll send a 6-digit code to your registered phone.</p>
      </div>

      <div class="rounded-2xl border border-[var(--border)] bg-[var(--card)] p-6 space-y-4"
           style="box-shadow: var(--shadow-lg), 0 0 0 1px var(--border)">
        <div>
          <label class="block text-[0.8125rem] font-semibold text-[var(--fg)] mb-1.5">Email or phone number</label>
          <input type="text" bind:value={identifier}
            onkeydown={(e) => e.key === 'Enter' && handleSend()}
            placeholder="you@school.com or 024…" autocomplete="username"
            class="w-full rounded-xl border border-[var(--border-strong)] bg-[var(--input-bg)]
                   px-4 py-3 text-sm text-[var(--fg)] placeholder:text-[var(--fg-subtle)]
                   focus:outline-none focus:ring-2 focus:ring-[var(--brand)]/20 focus:border-[var(--brand)] transition" />
        </div>

        <div>
          <label class="block text-[0.8125rem] font-semibold text-[var(--fg)] mb-1.5">
            School code <span class="font-normal text-[var(--fg-muted)]">(if required)</span>
          </label>
          <input type="text" bind:value={schoolCode}
            onkeydown={(e) => e.key === 'Enter' && handleSend()}
            placeholder="e.g. presec" autocomplete="off" spellcheck={false}
            class="w-full rounded-xl border border-[var(--border-strong)] bg-[var(--input-bg)]
                   px-4 py-3 text-sm text-[var(--fg)] placeholder:text-[var(--fg-subtle)]
                   focus:outline-none focus:ring-2 focus:ring-[var(--brand)]/20 focus:border-[var(--brand)] transition lowercase" />
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

    <!-- ── Step 2: OTP ──────────────────────────────────────── -->
    {#if step === 'otp'}
      <div class="mb-6 text-center">
        <div class="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-2xl shadow"
             style="background: linear-gradient(135deg, var(--brand) 0%, color-mix(in oklab, var(--brand) 65%, #7c3aed) 100%)">
          <svg class="h-7 w-7 text-white" fill="none" stroke="currentColor" stroke-width="1.75" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" d="M10.5 1.5H8.25A2.25 2.25 0 006 3.75v16.5a2.25 2.25 0 002.25 2.25h7.5A2.25 2.25 0 0018 20.25V3.75a2.25 2.25 0 00-2.25-2.25H13.5m-3 0V3h3V1.5m-3 0h3m-3 8.25h3m-3 3.75h3m-3 3.75h3"/>
          </svg>
        </div>
        <h1 class="text-xl font-bold text-[var(--fg)]">Enter your code</h1>
        <p class="mt-1.5 text-sm text-[var(--fg-muted)]">
          A 6-digit code was sent to<br/>
          <span class="font-semibold text-[var(--fg)]">{identifierState}</span>
        </p>
      </div>

      <div class="rounded-2xl border border-[var(--border)] bg-[var(--card)] p-6 space-y-6"
           style="box-shadow: var(--shadow-lg), 0 0 0 1px var(--border)">

        <!-- OTP digit boxes -->
        <div class="flex justify-center gap-2.5">
          {#each otpDigits as _, i}
            <input
              bind:this={otpInputs[i]}
              type="text" inputmode="numeric" maxlength="1"
              value={otpDigits[i]}
              oninput={(e) => handleOtpInput(e, i)}
              onkeydown={(e) => handleOtpKeydown(e, i)}
              onpaste={(e) => handleOtpPaste(e)}
              class="h-14 w-11 rounded-xl border-2 bg-[var(--bg)] text-center text-2xl font-bold
                     text-[var(--fg)] transition-all focus:outline-none"
              style="border-color: {otpError ? '#ef4444' : otpDigits[i] ? 'var(--brand)' : 'var(--border-strong)'};
                     box-shadow: {otpDigits[i] ? '0 0 0 3px color-mix(in oklab, var(--brand) 15%, transparent)' : 'none'}" />
          {/each}
        </div>

        {#if otpPending}
          <div class="flex items-center justify-center gap-2 text-sm text-[var(--fg-muted)]">
            <svg class="h-4 w-4 animate-spin" fill="none" viewBox="0 0 24 24">
              <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/>
              <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z"/>
            </svg>
            Verifying…
          </div>
        {/if}

        {#if otpError}
          <p class="text-center rounded-xl bg-red-50 dark:bg-red-950/30 px-4 py-3 text-sm text-red-600 dark:text-red-400">
            {otpError}
          </p>
        {/if}

        <div class="text-center space-y-2">
          {#if countdown > 0}
            <p class="text-xs text-[var(--fg-muted)]">
              Code expires in <span class="font-bold tabular-nums text-[var(--fg)]">{fmtCountdown(countdown)}</span>
            </p>
          {:else}
            <p class="text-xs font-medium text-red-500">Code has expired.</p>
          {/if}
          <button onclick={handleResend} disabled={!canResend}
            class="text-sm font-medium transition"
            style="color: {canResend ? 'var(--brand)' : 'var(--fg-muted)'}; opacity: {canResend ? 1 : 0.6}">
            {canResend ? 'Resend code' : `Resend in ${resendIn}s`}
          </button>
        </div>

        <p class="text-center text-xs">
          <button
            onclick={() => { step = 'identifier'; if (timerHandle) { clearInterval(timerHandle); timerHandle = null; } }}
            class="text-[var(--fg-muted)] hover:text-[var(--fg)] hover:underline transition">
            ← Change identifier
          </button>
        </p>
      </div>
    {/if}

    <!-- ── Step 3: New password ─────────────────────────────── -->
    {#if step === 'password'}
      <div class="mb-6 text-center">
        <div class="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-2xl shadow"
             style="background: linear-gradient(135deg, var(--brand) 0%, color-mix(in oklab, var(--brand) 65%, #7c3aed) 100%)">
          <svg class="h-7 w-7 text-white" fill="none" stroke="currentColor" stroke-width="1.75" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
          </svg>
        </div>
        <h1 class="text-xl font-bold text-[var(--fg)]">Set new password</h1>
        <p class="mt-1.5 text-sm text-[var(--fg-muted)]">Choose something strong and memorable.</p>
      </div>

      <div class="rounded-2xl border border-[var(--border)] bg-[var(--card)] p-6 space-y-4"
           style="box-shadow: var(--shadow-lg), 0 0 0 1px var(--border)">
        <div>
          <label class="block text-[0.8125rem] font-semibold text-[var(--fg)] mb-1.5">New password</label>
          <div class="relative">
            <input type={showPw ? 'text' : 'password'} bind:value={newPassword}
              placeholder="At least 8 characters" autocomplete="new-password"
              class="w-full rounded-xl border border-[var(--border-strong)] bg-[var(--input-bg)]
                     px-4 py-3 pr-10 text-sm text-[var(--fg)] placeholder:text-[var(--fg-subtle)]
                     focus:outline-none focus:ring-2 focus:ring-[var(--brand)]/20 focus:border-[var(--brand)] transition" />
            <button type="button" onclick={() => showPw = !showPw}
              class="absolute right-3 top-1/2 -translate-y-1/2 text-[var(--fg-subtle)] hover:text-[var(--fg-muted)] transition"
              aria-label="Toggle visibility">
              {#if showPw}
                <svg class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M3.98 8.223A10.477 10.477 0 001.934 12C3.226 16.338 7.244 19.5 12 19.5c.993 0 1.953-.138 2.863-.395M6.228 6.228A10.45 10.45 0 0112 4.5c4.756 0 8.773 3.162 10.065 7.498a10.523 10.523 0 01-4.293 5.774M6.228 6.228L3 3m3.228 3.228l3.65 3.65m7.894 7.894L21 21m-3.228-3.228l-3.65-3.65m0 0a3 3 0 10-4.243-4.243m4.242 4.242L9.88 9.88"/>
                </svg>
              {:else}
                <svg class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M2.036 12.322a1.012 1.012 0 010-.639C3.423 7.51 7.36 4.5 12 4.5c4.638 0 8.573 3.007 9.963 7.178.07.207.07.431 0 .639C20.577 16.49 16.64 19.5 12 19.5c-4.638 0-8.573-3.007-9.963-7.178z"/>
                  <path stroke-linecap="round" stroke-linejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"/>
                </svg>
              {/if}
            </button>
          </div>
          {#if newPassword}
            <div class="mt-2 space-y-1">
              <div class="flex gap-1">
                {#each [1, 2, 3, 4, 5] as n}
                  <div class="h-1 flex-1 rounded-full transition-all"
                       style="background: {n <= pwStrength.score ? pwStrength.color : 'var(--border)'}"></div>
                {/each}
              </div>
              <p class="text-[11px] font-medium" style="color: {pwStrength.color}">{pwStrength.label}</p>
            </div>
          {/if}
        </div>

        <div>
          <label class="block text-[0.8125rem] font-semibold text-[var(--fg)] mb-1.5">Confirm password</label>
          <input type={showPw ? 'text' : 'password'} bind:value={confirmPw}
            placeholder="Same password again" autocomplete="new-password"
            onkeydown={(e) => e.key === 'Enter' && handleReset()}
            class="w-full rounded-xl border border-[var(--border-strong)] bg-[var(--input-bg)]
                   px-4 py-3 text-sm text-[var(--fg)] placeholder:text-[var(--fg-subtle)]
                   focus:outline-none focus:ring-2 focus:ring-[var(--brand)]/20 focus:border-[var(--brand)] transition" />
          {#if confirmPw && confirmPw !== newPassword}
            <p class="mt-1 text-xs text-red-500">Passwords don't match.</p>
          {/if}
        </div>

        {#if resetError}
          <p class="rounded-xl bg-red-50 dark:bg-red-950/30 px-4 py-3 text-sm text-red-600 dark:text-red-400">{resetError}</p>
        {/if}

        <button onclick={handleReset}
          disabled={resetPending || newPassword.length < 8 || newPassword !== confirmPw}
          class="w-full rounded-xl py-3 text-sm font-semibold text-white transition active:scale-[0.98] disabled:opacity-60"
          style="background: linear-gradient(135deg, var(--brand) 0%, color-mix(in oklab, var(--brand) 70%, #7c3aed) 100%);
                 box-shadow: 0 2px 12px rgba(var(--brand-rgb), 0.35);">
          {#if resetPending}
            <span class="flex items-center justify-center gap-2">
              <svg class="h-4 w-4 animate-spin" fill="none" viewBox="0 0 24 24">
                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/>
                <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z"/>
              </svg>
              Saving…
            </span>
          {:else}
            Set new password
          {/if}
        </button>
      </div>
    {/if}

    <!-- ── Step 4: Done ────────────────────────────────────── -->
    {#if step === 'done'}
      <div class="text-center space-y-6">
        <div class="mx-auto flex h-20 w-20 items-center justify-center rounded-full shadow-lg"
             style="background: linear-gradient(135deg, #22c55e 0%, #16a34a 100%)">
          <svg class="h-10 w-10 text-white" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
          </svg>
        </div>
        <div>
          <h1 class="text-2xl font-bold text-[var(--fg)]">Password changed!</h1>
          <p class="mt-2 text-sm text-[var(--fg-muted)]">
            Your password has been updated successfully.<br/>
            You can now sign in with your new password.
          </p>
        </div>
        <button onclick={() => goto('/login')}
          class="w-full rounded-xl py-3 text-sm font-semibold text-white transition active:scale-[0.98]"
          style="background: linear-gradient(135deg, var(--brand) 0%, color-mix(in oklab, var(--brand) 70%, #7c3aed) 100%)">
          Sign in now →
        </button>
      </div>
    {/if}

    <p class="mt-6 text-center text-[10px] text-[var(--fg-subtle)]">
      Powered by <span class="font-semibold">TTEK-SMS</span>
    </p>
  </div>
</div>
