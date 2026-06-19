<script lang="ts">
  import { portal } from '$lib/actions/portal';

  interface Props {
    open: boolean;
    title: string;
    message: string;
    confirmLabel?: string;
    isPending?: boolean;
    onConfirm: () => void;
    onCancel: () => void;
  }

  const {
    open,
    title,
    message,
    confirmLabel = 'Delete',
    isPending = false,
    onConfirm,
    onCancel,
  }: Props = $props();

  function onKeydown(e: KeyboardEvent) {
    if (e.key === 'Escape') onCancel();
  }
</script>

{#if open}
  <!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
  <div use:portal role="dialog" aria-modal="true"
    class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
    onkeydown={onKeydown}>
    <div class="w-full max-w-sm rounded-2xl border border-[var(--border)] bg-[var(--card)] p-6 shadow-2xl">
      <div class="mb-1 flex items-start gap-3">
        <div class="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-red-100 dark:bg-red-950/40">
          <svg class="h-4.5 w-4.5 text-red-600" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z"/>
          </svg>
        </div>
        <div>
          <h2 class="text-base font-semibold text-[var(--fg)]">{title}</h2>
          <p class="mt-1 text-sm text-[var(--fg-muted)]">{message}</p>
        </div>
      </div>
      <div class="mt-5 flex justify-end gap-3">
        <button onclick={onCancel} disabled={isPending}
          class="rounded-lg px-4 py-2 text-sm text-[var(--fg-muted)] transition hover:bg-[var(--hover)] disabled:opacity-50">
          Cancel
        </button>
        <button onclick={onConfirm} disabled={isPending}
          class="rounded-lg bg-red-600 px-4 py-2 text-sm font-semibold text-white transition hover:bg-red-700 disabled:opacity-50">
          {isPending ? 'Deleting…' : confirmLabel}
        </button>
      </div>
    </div>
  </div>
{/if}
