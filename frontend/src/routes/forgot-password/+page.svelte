<script lang="ts">
  import { forgotPassword, detectLoginType } from '$lib/api/auth';

  let identifier = $state('');
  let schoolCode = $state('');
  let state      = $state<'idle' | 'submitting' | 'sent'>('idle');
  let error      = $state('');

  async function submit() {
    const id = identifier.trim();
    if (!id) { error = 'Enter your email or phone number.'; return; }
    error = '';
    state = 'submitting';
    try {
      await forgotPassword({
        login_type: detectLoginType(id),
        identifier: id,
        school_code: schoolCode.trim() || undefined,
      });
      state = 'sent';
    } catch {
      error = 'Something went wrong. Please try again.';
      state = 'idle';
    }
  }
</script>

<svelte:head><title>Reset Password — TTEK-SMS</title></svelte:head>

<div class="relative min-h-screen flex flex-col items-center justify-center p-4 bg-[var(--bg)]">
  <div class="pointer-events-none absolute -top-48 -right-48 h-96 w-96 rounded-full opacity-[0.07] blur-3xl"
       style="background: var(--brand)"></div>

  <div class="w-full max-w-[360px]">
    <a href="/login" class="mb-8 flex items-center gap-1.5 text-xs text-[var(--fg-muted)] transition hover:text-[var(--fg)]">
      <svg class="h-3.5 w-3.5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" d="M15 19l-7-7 7-7"/>
      </svg>
      Back to sign in
    </a>

    <div class="rounded-2xl border border-[var(--border)] bg-[var(--card)] p-8 shadow-lg">
      {#if state === 'sent'}
        <div class="text-center">
          <div class="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-emerald-100 dark:bg-emerald-900/40">
            <svg class="h-6 w-6 text-emerald-600 dark:text-emerald-400" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
            </svg>
          </div>
          <h1 class="text-lg font-bold text-[var(--fg)]">Check your inbox</h1>
          <p class="mt-2 text-sm text-[var(--fg-muted)]">
            If an account exists for <span class="font-medium text-[var(--fg)]">{identifier}</span>,
            you'll receive a reset link shortly.
          </p>
          <p class="mt-3 text-xs text-[var(--fg-subtle)]">
            Didn't get it? Contact your school administrator to reset your password directly.
          </p>
          <a href="/login"
             class="mt-6 block rounded-xl py-2.5 text-sm font-semibold text-white transition hover:opacity-90"
             style="background-color: var(--brand)">
            Back to sign in
          </a>
        </div>
      {:else}
        <div class="mb-6">
          <h1 class="text-xl font-bold text-[var(--fg)]">Forgot password?</h1>
          <p class="mt-1 text-sm text-[var(--fg-muted)]">Enter your email or phone and we'll send a reset link.</p>
        </div>

        <div class="space-y-4">
          <label class="block">
            <span class="mb-1.5 block text-xs font-medium text-[var(--fg-muted)]">Email or phone number</span>
            <input bind:value={identifier} type="text" placeholder="you@school.edu or 024XXXXXXX"
              onkeydown={(e) => e.key === 'Enter' && submit()}
              class="w-full rounded-xl border border-[var(--border)] bg-[var(--bg)] px-4 py-2.5 text-sm
                     text-[var(--fg)] placeholder-[var(--fg-subtle)] focus:outline-none focus:ring-2
                     focus:ring-[var(--brand)] transition" />
          </label>

          <label class="block">
            <span class="mb-1.5 block text-xs font-medium text-[var(--fg-muted)]">School code <span class="font-normal text-[var(--fg-subtle)]">(if required)</span></span>
            <input bind:value={schoolCode} type="text" placeholder="e.g. PRESEC"
              class="w-full rounded-xl border border-[var(--border)] bg-[var(--bg)] px-4 py-2.5 text-sm
                     text-[var(--fg)] placeholder-[var(--fg-subtle)] focus:outline-none focus:ring-2
                     focus:ring-[var(--brand)] transition" />
          </label>

          {#if error}
            <p class="text-xs text-red-500">{error}</p>
          {/if}

          <button onclick={submit} disabled={state === 'submitting'}
            class="w-full rounded-xl py-2.5 text-sm font-semibold text-white transition
                   hover:opacity-90 disabled:opacity-50"
            style="background-color: var(--brand)">
            {state === 'submitting' ? 'Sending…' : 'Send reset link'}
          </button>
        </div>
      {/if}
    </div>
  </div>
</div>
