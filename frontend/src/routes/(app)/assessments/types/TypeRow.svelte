<script lang="ts">
  import type { AssessmentType } from '$lib/api/assessments';
  import AssessmentTypeForm, { type AssessmentTypeFormState } from './AssessmentTypeForm.svelte';

  interface Props {
    t: AssessmentType;
    isEditing: boolean;
    editForm: AssessmentTypeFormState;
    editError: string;
    updatePending: boolean;
    toggleActivePending: boolean;
    deletePending: boolean;
    onToggleEdit: (t: AssessmentType) => void;
    onEditFormChange: (patch: Partial<AssessmentTypeFormState>) => void;
    onSaveEdit: () => void;
    onCancelEdit: () => void;
    onToggleActive: (t: AssessmentType) => void;
    onRequestDelete: (t: AssessmentType) => void;
  }
  const {
    t, isEditing, editForm, editError, updatePending, toggleActivePending, deletePending,
    onToggleEdit, onEditFormChange, onSaveEdit, onCancelEdit, onToggleActive, onRequestDelete,
  }: Props = $props();
</script>

<!-- A card, not a table row — a 6-column row (Name/Code/Category/Weight/
     Status/Actions) forced horizontal scroll on a phone; flex-wrap here lets
     the same information wrap onto a second line instead. -->
<div class="overflow-hidden rounded-2xl border border-[var(--border)] bg-[var(--card)]">
  <div class="flex flex-wrap items-center gap-x-4 gap-y-2 px-4 py-3.5">
    <div class="min-w-0 flex-1 basis-40">
      <p class="truncate font-medium text-[var(--fg)]">{t.name}</p>
      <p class="font-mono text-[10px] text-[var(--fg-subtle)]">{t.code}</p>
    </div>
    <span class="rounded-full bg-[var(--hover)] px-2.5 py-0.5 text-[10px] font-semibold text-[var(--fg-muted)] ring-1 ring-inset ring-[var(--border)]">
      {t.category.charAt(0) + t.category.slice(1).toLowerCase()}
    </span>
    <span class="font-mono text-xs text-[var(--fg-muted)]">{Number(t.weight).toFixed(2)}%</span>
    {#if t.is_active}
      <span class="text-xs font-semibold text-green-600 dark:text-green-500">Active</span>
    {:else}
      <span class="text-xs text-[var(--fg-subtle)]">Inactive</span>
    {/if}

    <!-- title tooltips never show on a touch screen — aria-label (for screen
         readers) plus a real 44px touch target stand in for the missing
         visible label on this dense admin row. -->
    <div class="ml-auto flex items-center gap-1">
      <button onclick={() => onToggleEdit(t)}
        class="flex min-h-[44px] min-w-[44px] items-center justify-center rounded-lg text-[var(--fg-subtle)] transition hover:bg-[var(--hover)] hover:text-[var(--fg)]"
        aria-label="Edit" title="Edit">
        <svg class="h-3.5 w-3.5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" d="M15.232 5.232l3.536 3.536M9 13l6.586-6.586a2 2 0 012.828 2.828L11.828 15.828a2 2 0 01-1.414.586H9v-2a2 2 0 01.586-1.414z"/>
        </svg>
      </button>
      <button
        onclick={() => onToggleActive(t)}
        disabled={toggleActivePending}
        class="flex min-h-[44px] min-w-[44px] items-center justify-center rounded-lg transition disabled:opacity-40 {t.is_active ? 'text-[var(--fg-subtle)] hover:bg-amber-50 hover:text-amber-600 dark:hover:bg-amber-950/30' : 'text-green-500 hover:bg-green-50 hover:text-green-600 dark:hover:bg-green-950/30'}"
        aria-label={t.is_active ? 'Deactivate' : 'Activate'} title={t.is_active ? 'Deactivate' : 'Activate'}>
        {#if t.is_active}
          <svg class="h-3.5 w-3.5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" d="M18.364 18.364A9 9 0 005.636 5.636m12.728 12.728A9 9 0 015.636 5.636m12.728 12.728L5.636 5.636"/>
          </svg>
        {:else}
          <svg class="h-3.5 w-3.5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/>
          </svg>
        {/if}
      </button>
      <button onclick={() => onRequestDelete(t)}
        disabled={deletePending}
        class="flex min-h-[44px] min-w-[44px] items-center justify-center rounded-lg text-[var(--fg-subtle)] transition hover:bg-red-50 hover:text-red-500 disabled:opacity-40 dark:hover:bg-red-950/30"
        aria-label="Delete" title="Delete">
        <svg class="h-3.5 w-3.5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/>
        </svg>
      </button>
    </div>
  </div>

  {#if isEditing}
    <div class="border-t border-[var(--border)] bg-[var(--bg)] px-4 pb-4 pt-3">
      <AssessmentTypeForm
        form={editForm}
        onChange={onEditFormChange}
        error={editError}
        pending={updatePending}
        onSubmit={onSaveEdit}
        onCancel={onCancelEdit}
        submitLabel="Save"
        compact
      />
    </div>
  {/if}
</div>
