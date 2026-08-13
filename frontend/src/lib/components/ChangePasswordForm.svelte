<script lang="ts">
  import { changePassword } from '$lib/api/auth';
  import { toast } from '$lib/stores/toast';

  interface Props {
    showForgotLink?: boolean;
    onSuccess?: () => void;
  }
  const { showForgotLink = true, onSuccess }: Props = $props();

  let current    = $state('');
  let next       = $state('');
  let confirm    = $state('');
  let showPwd    = $state(false);
  let submitting = $state(false);

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
  let pwStrength = $derived(strength(next));

  async function submit() {
    if (!current) { toast.error('Enter your current password.'); return; }
    if (next.length < 8) { toast.error('New password must be at least 8 characters.'); return; }
    if (next !== confirm) { toast.error('Passwords do not match.'); return; }
    submitting = true;
    try {
      await changePassword(current, next);
      toast.success('Password updated successfully.');
      current = ''; next = ''; confirm = '';
      onSuccess?.();
    } catch (e: unknown) {
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
        ?? 'Failed to update password.';
      toast.error(msg);
    } finally {
      submitting = false;
    }
  }
</script>

<div class="rounded-2xl border border-[var(--border)] bg-[var(--card)] p-6 shadow-sm">
  <div class="space-y-4">
    <label class="block">
      <span class="mb-1.5 block text-xs font-medium text-[var(--fg-muted)]">Current password</span>
      <input bind:value={current} type={showPwd ? 'text' : 'password'} placeholder="Your current password"
        class="w-full rounded-xl border border-[var(--border)] bg-[var(--bg)] px-4 py-2.5 text-sm
               text-[var(--fg)] placeholder-[var(--fg-subtle)] focus:outline-none focus:ring-2 focus:ring-[var(--brand)] transition" />
    </label>

    <div class="border-t border-[var(--border)] pt-4 space-y-4">
      <label class="block">
        <div class="mb-1.5 flex items-center justify-between">
          <span class="text-xs font-medium text-[var(--fg-muted)]">New password</span>
          <button type="button" onclick={() => showPwd = !showPwd}
            class="text-xs text-[var(--fg-subtle)] hover:text-[var(--fg-muted)]">
            {showPwd ? 'Hide' : 'Show'}
          </button>
        </div>
        <input bind:value={next} type={showPwd ? 'text' : 'password'} placeholder="Min. 8 characters"
          class="w-full rounded-xl border border-[var(--border)] bg-[var(--bg)] px-4 py-2.5 text-sm
                 text-[var(--fg)] placeholder-[var(--fg-subtle)] focus:outline-none focus:ring-2 focus:ring-[var(--brand)] transition" />
        {#if next}
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
      </label>

      <label class="block">
        <span class="mb-1.5 block text-xs font-medium text-[var(--fg-muted)]">Confirm new password</span>
        <input bind:value={confirm} type={showPwd ? 'text' : 'password'} placeholder="Repeat new password"
          onkeydown={(e) => e.key === 'Enter' && submit()}
          class="w-full rounded-xl border border-[var(--border)] bg-[var(--bg)] px-4 py-2.5 text-sm
                 text-[var(--fg)] placeholder-[var(--fg-subtle)] focus:outline-none focus:ring-2 focus:ring-[var(--brand)] transition" />
      </label>
    </div>

    <button onclick={submit} disabled={submitting}
      class="w-full rounded-xl py-2.5 text-sm font-semibold text-white transition hover:opacity-90 disabled:opacity-50"
      style="background-color: var(--brand)">
      {submitting ? 'Updating…' : 'Update password'}
    </button>
  </div>
</div>

{#if showForgotLink}
  <p class="mt-4 text-center text-xs text-[var(--fg-subtle)]">
    Forgot your current password?
    <a href="/forgot-password" class="text-[var(--brand)] hover:underline">Reset it here →</a>
  </p>
{/if}
