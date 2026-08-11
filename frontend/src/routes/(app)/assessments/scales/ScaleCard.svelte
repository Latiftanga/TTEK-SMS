<script lang="ts">
  import { createMutation, useQueryClient } from '@tanstack/svelte-query';
  import { deleteGradingScale, updateGradingScale, type GradingScale } from '$lib/api/assessments';
  import { toast } from '$lib/stores/toast';
  import ConfirmModal from '$lib/components/ConfirmModal.svelte';
  import GradeBandsPanel from './GradeBandsPanel.svelte';

  interface Props { scale: GradingScale; }
  const { scale }: Props = $props();

  const qc = useQueryClient();
  let expanded = $state(false);
  let editing  = $state(false);

  let editForm = $state({ name: scale.name, description: scale.description ?? '' });
  let editError = $state('');

  // A shared system-default scale (school_id=NULL, seeded — see
  // services/grading.py::resolve_grade) is read-only here: every edit/delete
  // endpoint already requires an exact school_id match, so it can't be
  // reached through this UI regardless — a school overrides it by creating
  // and defaulting their own scale instead.
  const isShared = $derived(scale.school_id === null);

  // ── Mutations ─────────────────────────────────────────────────────────────────

  const updateMut = createMutation({
    mutationFn: (data: { name?: string; description?: string; is_default?: boolean }) =>
      updateGradingScale(scale.id, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['grading-scales'] });
      editing = false; editError = '';
      toast.success('Grading scale updated.');
    },
    onError: (e: unknown) => {
      editError = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? 'Could not update.';
    },
  });

  // ── Deactivate / reactivate / delete ─────────────────────────────────────────
  let confirmDeactivate = $state(false);
  let confirmDeleteScale = $state(false);

  const toggleActiveMut = createMutation({
    mutationFn: (is_active: boolean) => updateGradingScale(scale.id, { is_active }),
    onSuccess: (_d, is_active) => {
      qc.invalidateQueries({ queryKey: ['grading-scales'] });
      confirmDeactivate = false;
      toast.success(is_active ? 'Grading scale reactivated.' : 'Grading scale deactivated.');
    },
    onError: () => { confirmDeactivate = false; toast.error('Could not update status.'); },
  });

  const deleteScaleMut = createMutation({
    mutationFn: () => deleteGradingScale(scale.id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['grading-scales'] });
      confirmDeleteScale = false;
      toast.success('Grading scale deleted.');
    },
    onError: (e: unknown) => {
      confirmDeleteScale = false;
      const detail = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      toast.error(detail ?? 'Could not delete.');
    },
  });

  function startEdit() {
    editForm = { name: scale.name, description: scale.description ?? '' };
    editError = '';
    editing = true;
  }

  function handleSaveEdit() {
    editError = '';
    if (!editForm.name.trim()) { editError = 'Name is required.'; return; }
    $updateMut.mutate({ name: editForm.name.trim(), description: editForm.description.trim() || undefined });
  }

  function handleSetDefault() {
    $updateMut.mutate({ is_default: true });
  }
</script>

<div class="overflow-hidden rounded-2xl border border-[var(--border)] bg-[var(--card)]">
  <!-- Header row -->
  <div class="flex items-center gap-2 px-4 py-3.5">
    <button onclick={() => expanded = !expanded}
      class="flex flex-1 items-center gap-2.5 min-w-0 text-left">
      <svg class="h-3.5 w-3.5 shrink-0 text-[var(--fg-muted)] transition-transform duration-200 {expanded ? 'rotate-90' : ''}"
        fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" d="M9 5l7 7-7 7"/>
      </svg>
      <span class="truncate font-semibold text-[var(--fg)]">{scale.name}</span>
      {#if scale.description}
        <span class="hidden truncate text-xs text-[var(--fg-subtle)] sm:inline">{scale.description}</span>
      {/if}
    </button>

    <!-- Badges + actions -->
    <div class="flex shrink-0 items-center gap-2">
      {#if isShared}
        <span class="rounded-full bg-[var(--hover)] px-2.5 py-0.5 text-[10px] font-bold text-[var(--fg-muted)] ring-1 ring-inset ring-[var(--border)]" title="Applies to every school until they create their own">System default</span>
      {:else if scale.is_default}
        <span class="rounded-full bg-blue-50 px-2.5 py-0.5 text-[10px] font-bold text-blue-700 ring-1 ring-inset ring-blue-600/20 dark:bg-blue-950/30 dark:text-blue-400">Default</span>
      {:else}
        <button
          onclick={handleSetDefault}
          disabled={$updateMut.isPending}
          class="rounded-full border border-[var(--border)] px-2.5 py-0.5 text-[10px] font-semibold text-[var(--fg-muted)] transition hover:border-blue-400 hover:text-blue-600 disabled:opacity-40 dark:hover:border-blue-500 dark:hover:text-blue-400"
          title="Set as default grading scale">
          {$updateMut.isPending ? '…' : 'Set default'}
        </button>
      {/if}
      {#if !isShared && !scale.is_active}
        <span class="rounded-full bg-[var(--hover)] px-2.5 py-0.5 text-[10px] font-semibold text-[var(--fg-muted)]">Inactive</span>
      {/if}
      <span class="text-xs text-[var(--fg-subtle)]">{scale.grades.length} bands</span>
      <!-- Edit button -->
      {#if !isShared}
        <button onclick={startEdit}
          class="rounded-lg p-1 text-[var(--fg-subtle)] transition hover:bg-[var(--hover)] hover:text-[var(--fg)]"
          title="Edit scale">
          <svg class="h-3.5 w-3.5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" d="M15.232 5.232l3.536 3.536M9 13l6.586-6.586a2 2 0 012.828 2.828L11.828 15.828a2 2 0 01-1.414.586H9v-2a2 2 0 01.586-1.414z"/>
          </svg>
        </button>
        <button
          onclick={() => scale.is_active ? (confirmDeactivate = true) : $toggleActiveMut.mutate(true)}
          disabled={$toggleActiveMut.isPending}
          class="rounded-lg p-1 transition disabled:opacity-40 {scale.is_active ? 'text-[var(--fg-subtle)] hover:bg-amber-50 hover:text-amber-600 dark:hover:bg-amber-950/30' : 'text-green-500 hover:bg-green-50 hover:text-green-600 dark:hover:bg-green-950/30'}"
          title={scale.is_active ? 'Deactivate' : 'Activate'}>
          {#if scale.is_active}
            <svg class="h-3.5 w-3.5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" d="M18.364 18.364A9 9 0 005.636 5.636m12.728 12.728A9 9 0 015.636 5.636m12.728 12.728L5.636 5.636"/>
            </svg>
          {:else}
            <svg class="h-3.5 w-3.5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/>
            </svg>
          {/if}
        </button>
        <button onclick={() => confirmDeleteScale = true}
          disabled={$deleteScaleMut.isPending}
          class="rounded-lg p-1 text-[var(--fg-subtle)] transition hover:bg-red-50 hover:text-red-500 disabled:opacity-40 dark:hover:bg-red-950/30"
          title="Delete">
          <svg class="h-3.5 w-3.5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/>
          </svg>
        </button>
      {/if}
    </div>
  </div>

  <!-- Edit form -->
  {#if editing}
    <div class="border-t border-[var(--border)] bg-[var(--bg)] px-4 pb-4 pt-3 space-y-2.5">
      <div class="grid gap-2 sm:grid-cols-2">
        <div>
          <label class="label-xs">Scale name <span class="text-red-500">*</span></label>
          <input bind:value={editForm.name} placeholder="e.g. Standard Grading Scale" class="inp" />
        </div>
        <div>
          <label class="label-xs">Description</label>
          <input bind:value={editForm.description} placeholder="Optional" class="inp" />
        </div>
      </div>
      {#if editError}<p class="text-xs text-red-500">{editError}</p>{/if}
      <div class="flex gap-2">
        <button onclick={handleSaveEdit} disabled={$updateMut.isPending}
          class="rounded-lg px-3 py-1.5 text-xs font-semibold text-white disabled:opacity-50 transition hover:opacity-90"
          style="background: var(--brand)">
          {$updateMut.isPending ? 'Saving…' : 'Save'}
        </button>
        <button onclick={() => { editing = false; editError = ''; }}
          class="text-xs text-[var(--fg-muted)] hover:text-[var(--fg)] transition">Cancel</button>
      </div>
    </div>
  {/if}

  <!-- Grade bands (expanded) -->
  {#if expanded}
    <div class="border-t border-[var(--border)] px-4 pb-4 pt-3 space-y-3">
      <GradeBandsPanel scaleId={scale.id} grades={scale.grades} {isShared} />
    </div>
  {/if}
</div>

<ConfirmModal
  open={confirmDeactivate}
  title="Deactivate {scale.name}?"
  message={scale.is_default
    ? "This scale is the active default — deactivating it falls back to the shared default scale, and clears cached grades on every previously-approved score so they're recalculated against it. You can reactivate this scale at any time."
    : "This scale will be hidden from new use. You can reactivate it at any time."}
  confirmLabel="Deactivate"
  variant="warning"
  isPending={$toggleActiveMut.isPending}
  onConfirm={() => $toggleActiveMut.mutate(false)}
  onCancel={() => confirmDeactivate = false}
/>

<ConfirmModal
  open={confirmDeleteScale}
  title="Delete {scale.name}?"
  message="This permanently removes the scale and its grade bands. Only possible when it isn't the active default — if it is, deactivate or replace it as default first."
  confirmLabel="Delete"
  variant="danger"
  isPending={$deleteScaleMut.isPending}
  onConfirm={() => $deleteScaleMut.mutate()}
  onCancel={() => confirmDeleteScale = false}
/>

<style>
  @reference "tailwindcss";
  .label-xs { @apply block text-[10px] font-medium text-[var(--fg-muted)] mb-0.5; }
  .inp { @apply w-full rounded-lg border border-[var(--border)] bg-[var(--bg)] px-2 py-1.5 text-xs text-[var(--fg)] placeholder:text-[var(--fg-subtle)] focus:border-[var(--brand)] focus:outline-none transition; }
</style>
