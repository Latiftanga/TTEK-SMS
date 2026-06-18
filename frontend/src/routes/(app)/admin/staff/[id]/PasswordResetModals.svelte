<script lang="ts">
  import { portal } from '$lib/actions/portal';
  import type { TempPasswordResult } from '$lib/api/staff';

  interface Props {
    displayName: string;
    confirmOpen: boolean;
    onConfirm: () => void;
    onCancel: () => void;
    isPending: boolean;
    result: TempPasswordResult | null;
    onDismiss: () => void;
  }
  const { displayName, confirmOpen, onConfirm, onCancel, isPending, result, onDismiss }: Props = $props();

  let copied = $state(false);

  function copy() {
    if (!result) return;
    navigator.clipboard.writeText(result.temporary_password).then(() => {
      copied = true; setTimeout(() => copied = false, 2000);
    });
  }
</script>

{#if confirmOpen}
  <div use:portal class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
    <div class="w-full max-w-sm rounded-2xl border border-[var(--border)] bg-[var(--card)] p-6 shadow-2xl">
      <h2 class="text-base font-semibold text-[var(--fg)]">Reset password?</h2>
      <p class="mt-2 text-sm text-[var(--fg-muted)]">
        A new temporary password will be generated for
        <span class="font-medium text-[var(--fg)]">{displayName}</span>.
        They will need to use it to sign in, then change it immediately.
      </p>
      <div class="mt-5 flex justify-end gap-3">
        <button onclick={onCancel}
          class="rounded-lg px-4 py-2 text-sm text-[var(--fg-muted)] hover:bg-[var(--hover)]">Cancel</button>
        <button onclick={onConfirm} disabled={isPending}
          class="rounded-lg bg-amber-500 px-4 py-2 text-sm font-medium text-white hover:bg-amber-600 disabled:opacity-50">
          {isPending ? 'Resetting…' : 'Yes, reset'}
        </button>
      </div>
    </div>
  </div>
{/if}

{#if result}
  <div use:portal class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
    <div class="w-full max-w-sm rounded-2xl border border-[var(--border)] bg-[var(--card)] p-6 shadow-2xl">
      <h2 class="text-base font-semibold text-[var(--fg)]">Temporary password generated</h2>
      <p class="mt-1.5 text-sm text-[var(--fg-muted)]">
        Share this with <span class="font-medium text-[var(--fg)]">{result.display_name}</span> securely.
        They should change it after signing in.
      </p>
      <div class="mt-4 flex items-center gap-3 rounded-xl border border-[var(--border)] bg-[var(--bg)] px-4 py-3">
        <p class="flex-1 font-mono text-lg font-semibold tracking-wider text-[var(--fg)]">{result.temporary_password}</p>
        <button onclick={copy}
          class="shrink-0 rounded-lg border border-[var(--border)] px-3 py-1.5 text-xs font-medium text-[var(--fg-muted)] transition hover:bg-[var(--hover)]">
          {copied ? '✓ Copied' : 'Copy'}
        </button>
      </div>
      <p class="mt-3 text-xs text-[var(--fg-subtle)]">This password is only shown once. Dismiss when done.</p>
      <div class="mt-4 flex justify-end">
        <button onclick={onDismiss}
          class="rounded-lg bg-[var(--brand)] px-4 py-2 text-sm font-medium text-white hover:opacity-90">
          Done
        </button>
      </div>
    </div>
  </div>
{/if}
