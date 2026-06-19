<script lang="ts">
  import { tick } from 'svelte';
  import { verifyOtp } from '$lib/api/auth';
  import type { LoginType } from '$lib/api/auth';

  interface Props {
    loginType: LoginType;
    identifier: string;
    schoolCode: string;
    devOtp: string;
    onSuccess: (resetToken: string) => void;
    onBack: () => void;
    onResend: () => Promise<{ newDevOtp: string }>;
  }

  const { loginType, identifier, schoolCode, devOtp: initialDevOtp, onSuccess, onBack, onResend }: Props = $props();

  let otpDigits  = $state<string[]>(
    initialDevOtp ? initialDevOtp.split('') : ['', '', '', '', '', '']
  );
  let otpInputs  = $state<HTMLInputElement[]>([]);
  let pending    = $state(false);
  let error      = $state('');
  let devOtp     = $state(initialDevOtp);
  let countdown  = $state(600);
  let canResend  = $state(false);
  let resendIn   = $state(30);
  let timerHandle: ReturnType<typeof setInterval> | null = null;

  $effect(() => {
    startCountdown();
    if (initialDevOtp) tick().then(() => otpInputs[5]?.focus());
    else tick().then(() => otpInputs[0]?.focus());
    return () => { if (timerHandle) clearInterval(timerHandle); };
  });

  function startCountdown() {
    countdown = 600; canResend = false; resendIn = 30;
    if (timerHandle) clearInterval(timerHandle);
    timerHandle = setInterval(() => {
      countdown = Math.max(0, countdown - 1);
      resendIn  = Math.max(0, resendIn - 1);
      if (resendIn === 0) canResend = true;
      if (countdown === 0 && timerHandle) { clearInterval(timerHandle); timerHandle = null; }
    }, 1000);
  }

  function fmt(s: number) {
    return `${Math.floor(s / 60).toString().padStart(2, '0')}:${(s % 60).toString().padStart(2, '0')}`;
  }

  function otpValue() { return otpDigits.join(''); }

  function handleInput(e: Event & { currentTarget: HTMLInputElement }, i: number) {
    const val = e.currentTarget.value.replace(/\D/g, '').slice(-1);
    otpDigits[i] = val;
    if (val && i < 5) otpInputs[i + 1]?.focus();
    if (otpValue().length === 6) submit();
  }

  function handleKeydown(e: KeyboardEvent & { currentTarget: HTMLInputElement }, i: number) {
    if (e.key === 'Backspace' && !otpDigits[i] && i > 0) otpInputs[i - 1]?.focus();
    if (e.key === 'ArrowLeft'  && i > 0) otpInputs[i - 1]?.focus();
    if (e.key === 'ArrowRight' && i < 5) otpInputs[i + 1]?.focus();
  }

  function handlePaste(e: ClipboardEvent) {
    e.preventDefault();
    const pasted = (e.clipboardData?.getData('text') ?? '').replace(/\D/g, '').slice(0, 6);
    for (let i = 0; i < 6; i++) otpDigits[i] = pasted[i] ?? '';
    otpInputs[Math.min(pasted.length, 5)]?.focus();
    if (pasted.length === 6) submit();
  }

  async function submit() {
    const code = otpValue();
    if (code.length !== 6 || pending) return;
    pending = true; error = '';
    try {
      const result = await verifyOtp({ login_type: loginType, identifier, school_code: schoolCode || undefined, otp: code });
      onSuccess(result.reset_token);
    } catch (e: unknown) {
      error     = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? 'Invalid code.';
      otpDigits = ['', '', '', '', '', ''];
      await tick();
      otpInputs[0]?.focus();
    } finally {
      pending = false;
    }
  }

  async function handleResend() {
    if (!canResend) return;
    canResend = false; resendIn = 30; error = '';
    otpDigits = ['', '', '', '', '', ''];
    const result = await onResend();
    devOtp = result.newDevOtp;
    if (devOtp) {
      otpDigits = devOtp.split('');
      await tick(); otpInputs[5]?.focus();
    } else {
      await tick(); otpInputs[0]?.focus();
    }
    startCountdown();
  }
</script>

<div class="space-y-6">
  {#if devOtp}
    <div class="rounded-xl border border-amber-200 bg-amber-50 dark:border-amber-800 dark:bg-amber-950/30 px-4 py-3">
      <p class="text-[11px] font-semibold uppercase tracking-wide text-amber-700 dark:text-amber-400 mb-1">Dev mode — no SMS sent</p>
      <p class="text-sm text-amber-900 dark:text-amber-300">
        Your OTP is <span class="font-bold tracking-widest">{devOtp}</span>
        <span class="ml-1 text-xs text-amber-600 dark:text-amber-500">(pre-filled above)</span>
      </p>
    </div>
  {/if}

  <!-- 6 OTP boxes -->
  <div class="flex justify-center gap-2.5">
    {#each otpDigits as _, i}
      <input
        bind:this={otpInputs[i]}
        type="text" inputmode="numeric" maxlength="1"
        value={otpDigits[i]}
        oninput={(e) => handleInput(e, i)}
        onkeydown={(e) => handleKeydown(e, i)}
        onpaste={(e) => handlePaste(e)}
        class="h-14 w-11 rounded-xl border-2 bg-[var(--bg)] text-center text-2xl font-bold
               text-[var(--fg)] transition-all focus:outline-none"
        style="border-color: {error ? '#ef4444' : otpDigits[i] ? 'var(--brand)' : 'var(--border-strong)'};
               box-shadow: {otpDigits[i] ? '0 0 0 3px color-mix(in oklab, var(--brand) 15%, transparent)' : 'none'}" />
    {/each}
  </div>

  {#if pending}
    <div class="flex items-center justify-center gap-2 text-sm text-[var(--fg-muted)]">
      <svg class="h-4 w-4 animate-spin" fill="none" viewBox="0 0 24 24">
        <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/>
        <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z"/>
      </svg>
      Verifying…
    </div>
  {/if}

  {#if error}
    <p class="text-center rounded-xl bg-red-50 dark:bg-red-950/30 px-4 py-3 text-sm text-red-600 dark:text-red-400">{error}</p>
  {/if}

  <div class="text-center space-y-2">
    {#if countdown > 0}
      <p class="text-xs text-[var(--fg-muted)]">
        Code expires in <span class="font-bold tabular-nums text-[var(--fg)]">{fmt(countdown)}</span>
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
    <button onclick={onBack} class="text-[var(--fg-muted)] hover:text-[var(--fg)] hover:underline transition">
      ← Change identifier
    </button>
  </p>
</div>
