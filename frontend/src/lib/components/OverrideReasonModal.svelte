<script lang="ts">
  import { portal } from '$lib/actions/portal';

  interface Props {
    open: boolean;
    title?: string;
    message?: string;
    submitLabel?: string;
    errorMessage?: string;
    isPending?: boolean;
    onSubmit: (reason: string) => void;
    onCancel: () => void;
  }

  const {
    open,
    title = 'This term is locked',
    message = 'Scores and behaviour records for this term have been frozen. Supply a reason to override — it is written to the audit log.',
    submitLabel = 'Override & continue',
    errorMessage = '',
    isPending = false,
    onSubmit,
    onCancel,
  }: Props = $props();

  let reason = $state('');

  function submit() {
    const trimmed = reason.trim();
    if (!trimmed) return;
    onSubmit(trimmed);
  }

  function onKeydown(e: KeyboardEvent) { if (e.key === 'Escape') onCancel(); }
</script>

{#if open}
  <!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
  <div use:portal role="dialog" aria-modal="true"
    class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
    onkeydown={onKeydown}>
    <div class="w-full max-w-sm rounded-2xl border border-[var(--border)] bg-[var(--card)] p-6 shadow-2xl">
      <div class="mb-1 flex items-start gap-3">
        <div class="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-red-100 dark:bg-red-950/40">
          <svg class="h-5 w-5 text-red-600 dark:text-red-400" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" d="M13.5 10.5V6.75a4.5 4.5 0 119 0v3.75M3.75 21.75h10.5a2.25 2.25 0 002.25-2.25v-6.75a2.25 2.25 0 00-2.25-2.25H3.75a2.25 2.25 0 00-2.25 2.25v6.75a2.25 2.25 0 002.25 2.25z"/>
          </svg>
        </div>
        <div>
          <h2 class="text-base font-semibold text-[var(--fg)]">{title}</h2>
          <p class="mt-1 text-sm text-[var(--fg-muted)]">{message}</p>
        </div>
      </div>
      <textarea bind:value={reason} rows="3" placeholder="Reason for override…"
        class="mt-3 w-full rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--fg)] placeholder:text-[var(--fg-subtle)] focus:border-[var(--brand)] focus:outline-none"
      ></textarea>
      {#if errorMessage}<p class="mt-2 text-xs text-red-500">{errorMessage}</p>{/if}
      <div class="mt-5 flex justify-end gap-3">
        <button onclick={onCancel} disabled={isPending}
          class="rounded-lg px-4 py-2 text-sm text-[var(--fg-muted)] transition hover:bg-[var(--hover)] disabled:opacity-50">
          Cancel
        </button>
        <button onclick={submit} disabled={isPending || !reason.trim()}
          class="rounded-lg bg-red-600 px-4 py-2 text-sm font-semibold text-white transition hover:bg-red-700 disabled:opacity-50">
          {isPending ? 'Submitting…' : submitLabel}
        </button>
      </div>
    </div>
  </div>
{/if}
