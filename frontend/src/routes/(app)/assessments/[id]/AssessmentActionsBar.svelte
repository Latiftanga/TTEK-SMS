<script lang="ts">
  interface Props {
    unapprovedCount: number;
    hasScores: boolean;
    approvePending: boolean;
    onApprove: () => void;
    confirmPublish: boolean;
    publishPending: boolean;
    onPublish: () => void;
    onEdit: () => void;
    confirmDelete: boolean;
    deletePending: boolean;
    onDelete: () => void;
    // Approve/Publish are the senior sign-off step (guardian notifications,
    // report-card visibility) — kept separate from Edit/Delete, which any
    // subject teacher who owns this assessment already has via the parent's
    // broader canEnterScores gate.
    canApprovePublish: boolean;
  }
  let {
    unapprovedCount, hasScores, approvePending, onApprove,
    confirmPublish = $bindable(), publishPending, onPublish,
    onEdit,
    confirmDelete = $bindable(), deletePending, onDelete,
    canApprovePublish,
  }: Props = $props();
</script>

<div class="flex flex-wrap items-center gap-2 sm:shrink-0">
  {#if canApprovePublish}
    <!-- Approve pending -->
    {#if unapprovedCount > 0}
      <button onclick={onApprove} disabled={approvePending}
        class="flex items-center gap-1.5 rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-1.5 text-xs font-semibold text-[var(--fg)] transition hover:border-[var(--brand)] hover:text-[var(--brand)] disabled:opacity-50">
        <svg class="h-3.5 w-3.5" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24"><polyline points="20 6 9 17 4 12"/></svg>
        {approvePending ? 'Approving…' : `Approve ${unapprovedCount}`}
      </button>
    {:else if hasScores}
      <span class="flex items-center gap-1 rounded-xl bg-green-50 px-3 py-1.5 text-xs font-semibold text-green-700 dark:bg-green-950/30 dark:text-green-400">
        <svg class="h-3.5 w-3.5" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24"><polyline points="20 6 9 17 4 12"/></svg>
        All approved
      </span>
    {/if}

    <!-- Publish -->
    {#if !confirmPublish}
      <button onclick={() => confirmPublish = true}
        class="rounded-xl px-3 py-1.5 text-xs font-semibold text-white transition hover:opacity-90"
        style="background: var(--brand)">
        Publish
      </button>
    {:else}
      <div class="flex items-center gap-2 rounded-xl border border-[var(--border)] bg-[var(--card)] px-3 py-1.5">
        <span class="text-xs text-[var(--fg-muted)]">SMS guardians?</span>
        <button onclick={onPublish} disabled={publishPending}
          class="rounded-lg bg-green-600 px-2.5 py-1 text-xs font-semibold text-white hover:bg-green-700 disabled:opacity-50 transition">
          {publishPending ? '…' : 'Yes, publish'}
        </button>
        <button onclick={() => confirmPublish = false} class="text-xs text-[var(--fg-muted)] hover:text-[var(--fg)] transition">Cancel</button>
      </div>
    {/if}
  {/if}

  <!-- Edit / Delete (secondary) -->
  <button onclick={onEdit} title="Edit"
    class="rounded-xl border border-[var(--border)] p-1.5 text-[var(--fg-subtle)] transition hover:bg-[var(--hover)] hover:text-[var(--fg)]">
    <svg class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
      <path stroke-linecap="round" stroke-linejoin="round" d="M15.232 5.232l3.536 3.536M9 13l6.586-6.586a2 2 0 012.828 2.828L11.828 15.828a2 2 0 01-1.414.586H9v-2a2 2 0 01.586-1.414z"/>
    </svg>
  </button>

  {#if !confirmDelete}
    <button onclick={() => confirmDelete = true}
      class="rounded-xl border border-[var(--border)] p-1.5 text-[var(--fg-subtle)] transition hover:border-red-200 hover:bg-red-50 hover:text-red-600 dark:hover:border-red-800 dark:hover:bg-red-950/30">
      <svg class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/>
      </svg>
    </button>
  {:else}
    <div class="flex items-center gap-2 rounded-xl border border-red-200 bg-red-50 px-3 py-1.5 dark:border-red-800 dark:bg-red-950/30">
      <span class="text-xs font-semibold text-red-600 dark:text-red-400">Delete?</span>
      <button onclick={onDelete} disabled={deletePending}
        class="rounded-lg bg-red-600 px-2.5 py-1 text-xs font-semibold text-white hover:bg-red-700 disabled:opacity-50 transition">
        {deletePending ? '…' : 'Yes'}
      </button>
      <button onclick={() => confirmDelete = false} class="text-xs text-red-600 hover:text-red-800 transition">Cancel</button>
    </div>
  {/if}
</div>
