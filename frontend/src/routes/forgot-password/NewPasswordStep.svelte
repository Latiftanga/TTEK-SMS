<script lang="ts">
  import { resetPassword } from '$lib/api/auth';

  interface Props {
    resetToken: string;
    onSuccess: () => void;
  }

  const { resetToken, onSuccess }: Props = $props();

  let newPassword = $state('');
  let confirmPw   = $state('');
  let showPw      = $state(false);
  let pending     = $state(false);
  let error       = $state('');

  function strength(pw: string) {
    if (!pw) return { score: 0, label: '', color: '' };
    let s = 0;
    if (pw.length >= 8)          s++;
    if (pw.length >= 12)         s++;
    if (/[A-Z]/.test(pw))        s++;
    if (/[0-9]/.test(pw))        s++;
    if (/[^A-Za-z0-9]/.test(pw)) s++;
    if (s <= 1) return { score: s, label: 'Weak',   color: '#ef4444' };
    if (s === 2) return { score: s, label: 'Fair',   color: '#f97316' };
    if (s === 3) return { score: s, label: 'Good',   color: '#eab308' };
    return          { score: s, label: 'Strong', color: '#22c55e' };
  }

  let pwStrength = $derived(strength(newPassword));
  let canSubmit  = $derived(!pending && newPassword.length >= 8 && newPassword === confirmPw);

  async function handleReset() {
    if (!canSubmit) return;
    error = ''; pending = true;
    try {
      await resetPassword({ token: resetToken, new_password: newPassword });
      onSuccess();
    } catch (e: unknown) {
      error = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
        ?? 'Reset failed. Please start over.';
    } finally {
      pending = false;
    }
  }
</script>

<div class="space-y-4">
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

  {#if error}
    <p class="rounded-xl bg-red-50 dark:bg-red-950/30 px-4 py-3 text-sm text-red-600 dark:text-red-400">{error}</p>
  {/if}

  <button onclick={handleReset} disabled={!canSubmit}
    class="w-full rounded-xl py-3 text-sm font-semibold text-white transition active:scale-[0.98] disabled:opacity-60"
    style="background: linear-gradient(135deg, var(--brand) 0%, color-mix(in oklab, var(--brand) 70%, #7c3aed) 100%);
           box-shadow: 0 2px 12px rgba(var(--brand-rgb), 0.35);">
    {#if pending}
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
