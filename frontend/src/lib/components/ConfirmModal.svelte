<script lang="ts">
  import { portal } from '$lib/actions/portal';

  interface Props {
    open: boolean;
    title: string;
    message: string;
    confirmLabel?: string;
    variant?: 'danger' | 'warning';
    isPending?: boolean;
    onConfirm: () => void;
    onCancel: () => void;
  }

  const {
    open,
    title,
    message,
    confirmLabel = 'Delete',
    variant = 'danger',
    isPending = false,
    onConfirm,
    onCancel,
  }: Props = $props();

  const iconBg  = $derived(variant === 'warning' ? 'bg-amber-100 dark:bg-amber-950/40' : 'bg-red-100 dark:bg-red-950/40');
  const iconCol = $derived(variant === 'warning' ? 'text-amber-600 dark:text-amber-400' : 'text-red-600 dark:text-red-400');
  const btnCls  = $derived(variant === 'warning'
    ? 'bg-amber-500 hover:bg-amber-600 disabled:opacity-50'
    : 'bg-red-600 hover:bg-red-700 disabled:opacity-50');

  function onKeydown(e: KeyboardEvent) { if (e.key === 'Escape') onCancel(); }
</script>

{#if open}
  <!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
  <div use:portal role="dialog" aria-modal="true"
    class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
    onkeydown={onKeydown}>
    <div class="w-full max-w-sm rounded-2xl border border-[var(--border)] bg-[var(--card)] p-6 shadow-2xl">
      <div class="mb-1 flex items-start gap-3">
        <div class="flex h-9 w-9 shrink-0 items-center justify-center rounded-full {iconBg}">
          {#if variant === 'warning'}
            <svg class="h-5 w-5 {iconCol}" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z"/>
            </svg>
          {:else}
            <svg class="h-5 w-5 {iconCol}" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" d="M14.74 9l-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 01-2.244 2.077H8.084a2.25 2.25 0 01-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 00-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 013.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 00-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 00-7.5 0"/>
            </svg>
          {/if}
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
          class="rounded-lg px-4 py-2 text-sm font-semibold text-white transition {btnCls}">
          {isPending ? `${confirmLabel}…` : confirmLabel}
        </button>
      </div>
    </div>
  </div>
{/if}
