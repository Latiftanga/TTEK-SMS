<script lang="ts">
  import type { Assessment } from '$lib/api/assessments';
  import AssessmentActionsBar from './AssessmentActionsBar.svelte';

  interface Props {
    a: Assessment;
    label: string;
    subjectDisplay: string;
    termLocked: boolean;
    canEnterScores: boolean;
    canManage: boolean;

    editing: boolean;
    editForm: { description: string; maxScore: string; dueDate: string };
    editErr: string;
    editPending: boolean;
    onSaveEdit: () => void;
    onCancelEdit: () => void;
    onStartEdit: () => void;

    unapprovedCount: number;
    hasScores: boolean;
    approvePending: boolean;
    onApprove: () => void;

    confirmPublish: boolean;
    publishPending: boolean;
    onPublish: () => void;

    confirmDelete: boolean;
    deletePending: boolean;
    onDelete: () => void;

    onRequestUnpublish: () => void;
  }
  let {
    a, label, subjectDisplay, termLocked, canEnterScores, canManage,
    editing, editForm = $bindable(), editErr, editPending, onSaveEdit, onCancelEdit, onStartEdit,
    unapprovedCount, hasScores, approvePending, onApprove,
    confirmPublish = $bindable(), publishPending, onPublish,
    confirmDelete = $bindable(), deletePending, onDelete,
    onRequestUnpublish,
  }: Props = $props();
</script>

<div class="mb-5 rounded-2xl border border-[var(--border)] bg-[var(--card)] p-5">
  {#if editing}
    <!-- Edit form -->
    <div class="space-y-3">
      <div class="grid gap-3 sm:grid-cols-3">
        <div class="sm:col-span-1"><label class="lx">Description</label><input bind:value={editForm.description} class="inp mt-1" /></div>
        <div><label class="lx">Max score</label><input type="number" min="1" step="0.5" inputmode="decimal" bind:value={editForm.maxScore} class="inp mt-1" /></div>
        <div><label class="lx">Date given to students</label><input type="date" bind:value={editForm.dueDate} class="inp mt-1" /></div>
      </div>
      {#if editErr}<p class="text-xs text-red-500">{editErr}</p>{/if}
      <div class="flex gap-2">
        <button onclick={onSaveEdit} disabled={editPending}
          class="min-h-[44px] rounded-xl px-4 py-2 text-sm font-semibold text-white disabled:opacity-50 hover:opacity-90 transition" style="background:var(--brand)">
          {editPending ? 'Saving…' : 'Save changes'}
        </button>
        <button onclick={onCancelEdit}
          class="min-h-[44px] rounded-xl border border-[var(--border)] px-4 py-2 text-sm text-[var(--fg-muted)] hover:bg-[var(--hover)] transition">
          Cancel
        </button>
      </div>
    </div>

  {:else}
    <!-- View mode -->
    <div class="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
      <!-- Info -->
      <div class="min-w-0">
        <div class="flex flex-wrap items-center gap-2">
          <h1 class="text-lg font-bold text-[var(--fg)]">{label}</h1>
          {#if a.is_published}
            <span class="rounded-full bg-green-50 px-2.5 py-0.5 text-[10px] font-bold text-green-700 ring-1 ring-inset ring-green-600/20 dark:bg-green-950/30 dark:text-green-400">Published</span>
          {:else}
            <span class="rounded-full bg-[var(--hover)] px-2.5 py-0.5 text-[10px] font-semibold text-[var(--fg-muted)]">Draft</span>
          {/if}
          {#if termLocked}
            <span class="rounded-full bg-red-50 px-2.5 py-0.5 text-[10px] font-bold text-red-700 ring-1 ring-inset ring-red-600/20 dark:bg-red-950/30 dark:text-red-400">
              Term locked
            </span>
          {/if}
        </div>
        <p class="mt-1 text-sm text-[var(--fg-muted)]">
          {subjectDisplay} · Max {a.max_score}
          {#if a.due_date}<span class="text-[var(--fg-subtle)]"> · Given {a.due_date}</span>{/if}
          {#if a.description}<span class="text-[var(--fg-subtle)]"> · {a.description}</span>{/if}
        </p>
      </div>

      <!-- Actions (unpublished only). Edit/Delete are the owning subject
           teacher's own job (get_assessment is already scope-checked
           server-side, so canEnterScores here is safe — a 'teacher' role
           only ever sees data for a class+subject they teach). Approve/
           Publish stay canManage-only inside the bar. -->
      {#if !a.is_published && canEnterScores}
        <AssessmentActionsBar
          {unapprovedCount}
          {hasScores}
          {approvePending}
          {onApprove}
          bind:confirmPublish
          {publishPending}
          {onPublish}
          onEdit={onStartEdit}
          bind:confirmDelete
          {deletePending}
          {onDelete}
          canApprovePublish={canManage}
        />
      {:else if a.is_published && canManage}
        <!-- Same senior-staff tier as publish itself — reverses a mistake,
             always asks for a reason. -->
        <button onclick={onRequestUnpublish}
          class="min-h-[44px] rounded-xl border border-red-200 px-3 py-1.5 text-xs font-semibold text-red-600 transition hover:bg-red-50 dark:border-red-800 dark:text-red-400 dark:hover:bg-red-950/30">
          Unpublish
        </button>
      {/if}
    </div>
  {/if}
</div>

<style>
  @reference "tailwindcss";
  .lx  { @apply block text-xs font-medium text-[var(--fg-muted)]; }
  .inp { @apply w-full min-h-[44px] rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--fg)] placeholder:text-[var(--fg-subtle)] focus:border-[var(--brand)] focus:outline-none transition; }
</style>
