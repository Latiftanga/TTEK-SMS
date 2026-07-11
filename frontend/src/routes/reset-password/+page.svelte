<script lang="ts">
  import { page } from '$app/stores';
  import { goto } from '$app/navigation';
  import { get } from 'svelte/store';
  import { resetPassword } from '$lib/api/auth';

  const token = get(page).url.searchParams.get('token') ?? '';

  let newPassword  = $state('');
  let confirm      = $state('');
  let showPwd      = $state(false);
  let phase        = $state<'idle' | 'submitting' | 'done'>('idle');
  let error        = $state('');

  async function submit() {
    error = '';
    if (!token) { error = 'Reset link is invalid or has expired.'; return; }
    if (newPassword.length < 8) { error = 'Password must be at least 8 characters.'; return; }
    if (newPassword !== confirm) { error = 'Passwords do not match.'; return; }
    phase = 'submitting';
    try {
      await resetPassword({ token, new_password: newPassword });
      phase = 'done';
      setTimeout(() => goto('/login'), 2500);
    } catch (e: unknown) {
      error = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
        ?? 'Link is invalid or has expired. Request a new one.';
      phase = 'idle';
    }
  }
</script>

<svelte:head><title>Set New Password</title></svelte:head>

<div class="relative min-h-screen flex flex-col items-center justify-center p-4 bg-[var(--bg)]">
  <div class="pointer-events-none absolute -top-48 -right-48 h-96 w-96 rounded-full opacity-[0.07] blur-3xl"
       style="background: var(--brand)"></div>

  <div class="w-full max-w-[360px]">
    <div class="rounded-2xl border border-[var(--border)] bg-[var(--card)] p-8 shadow-lg">
      {#if !token}
        <div class="text-center">
          <p class="text-sm text-red-500">This reset link is invalid or has expired.</p>
          <a href="/forgot-password" class="mt-4 block text-sm font-medium text-[var(--brand)] hover:underline">
            Request a new link →
          </a>
        </div>

      {:else if phase === 'done'}
        <div class="text-center">
          <div class="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-emerald-100 dark:bg-emerald-900/40">
            <svg class="h-6 w-6 text-emerald-600 dark:text-emerald-400" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
            </svg>
          </div>
          <h1 class="text-lg font-bold text-[var(--fg)]">Password updated</h1>
          <p class="mt-2 text-sm text-[var(--fg-muted)]">Redirecting you to sign in…</p>
        </div>

      {:else}
        <div class="mb-6">
          <h1 class="text-xl font-bold text-[var(--fg)]">Set new password</h1>
          <p class="mt-1 text-sm text-[var(--fg-muted)]">Choose a strong password you'll remember.</p>
        </div>

        <div class="space-y-4">
          <label class="block">
            <span class="mb-1.5 block text-xs font-medium text-[var(--fg-muted)]">New password</span>
            <div class="relative">
              <input bind:value={newPassword} type={showPwd ? 'text' : 'password'} placeholder="Min. 8 characters"
                class="w-full rounded-xl border border-[var(--border)] bg-[var(--bg)] px-4 py-2.5 pr-10 text-sm
                       text-[var(--fg)] placeholder-[var(--fg-subtle)] focus:outline-none focus:ring-2
                       focus:ring-[var(--brand)] transition" />
              <button type="button" onclick={() => showPwd = !showPwd}
                class="absolute right-3 top-1/2 -translate-y-1/2 text-[var(--fg-subtle)] hover:text-[var(--fg-muted)]">
                <svg class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
                  {#if showPwd}
                    <path stroke-linecap="round" stroke-linejoin="round" d="M3.98 8.223A10.477 10.477 0 001.934 12C3.226 16.338 7.244 19.5 12 19.5c.993 0 1.953-.138 2.863-.395M6.228 6.228A10.45 10.45 0 0112 4.5c4.756 0 8.773 3.162 10.065 7.498a10.523 10.523 0 01-4.293 5.774M6.228 6.228L3 3m3.228 3.228l3.65 3.65m7.894 7.894L21 21m-3.228-3.228l-3.65-3.65m0 0a3 3 0 10-4.243-4.243m4.242 4.242L9.88 9.88"/>
                  {:else}
                    <path stroke-linecap="round" stroke-linejoin="round" d="M2.036 12.322a1.012 1.012 0 010-.639C3.423 7.51 7.36 4.5 12 4.5c4.638 0 8.573 3.007 9.963 7.178.07.207.07.431 0 .639C20.577 16.49 16.64 19.5 12 19.5c-4.638 0-8.573-3.007-9.963-7.178z"/><path stroke-linecap="round" stroke-linejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"/>
                  {/if}
                </svg>
              </button>
            </div>
          </label>

          <label class="block">
            <span class="mb-1.5 block text-xs font-medium text-[var(--fg-muted)]">Confirm password</span>
            <input bind:value={confirm} type={showPwd ? 'text' : 'password'} placeholder="Repeat password"
              onkeydown={(e) => e.key === 'Enter' && submit()}
              class="w-full rounded-xl border border-[var(--border)] bg-[var(--bg)] px-4 py-2.5 text-sm
                     text-[var(--fg)] placeholder-[var(--fg-subtle)] focus:outline-none focus:ring-2
                     focus:ring-[var(--brand)] transition" />
          </label>

          {#if error}<p class="text-xs text-red-500">{error}</p>{/if}

          <button onclick={submit} disabled={phase === 'submitting'}
            class="w-full rounded-xl py-2.5 text-sm font-semibold text-white transition hover:opacity-90 disabled:opacity-50"
            style="background-color: var(--brand)">
            {phase === 'submitting' ? 'Updating…' : 'Update password'}
          </button>
        </div>
      {/if}
    </div>
  </div>
</div>
