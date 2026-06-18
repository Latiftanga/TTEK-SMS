<script lang="ts">
  import { changePassword } from '$lib/api/auth';
  import { toast } from '$lib/stores/toast';

  let current    = $state('');
  let next       = $state('');
  let confirm    = $state('');
  let showPwd    = $state(false);
  let submitting = $state(false);

  async function submit() {
    if (!current) { toast.error('Enter your current password.'); return; }
    if (next.length < 8) { toast.error('New password must be at least 8 characters.'); return; }
    if (next !== confirm) { toast.error('Passwords do not match.'); return; }
    submitting = true;
    try {
      await changePassword(current, next);
      toast.success('Password updated successfully.');
      current = ''; next = ''; confirm = '';
    } catch (e: unknown) {
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
        ?? 'Failed to update password.';
      toast.error(msg);
    } finally {
      submitting = false;
    }
  }
</script>

<svelte:head><title>Change Password</title></svelte:head>

<div class="mx-auto max-w-md">
  <div class="mb-6">
    <h1 class="text-2xl font-bold text-[var(--fg)]">Change Password</h1>
    <p class="mt-1 text-sm text-[var(--fg-muted)]">Update your account password. You'll stay signed in on this device.</p>
  </div>

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

  <p class="mt-4 text-center text-xs text-[var(--fg-subtle)]">
    Forgot your current password?
    <a href="/forgot-password" class="text-[var(--brand)] hover:underline">Reset it here →</a>
  </p>
</div>
