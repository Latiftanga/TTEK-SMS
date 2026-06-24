<script lang="ts">
  import { createMutation, useQueryClient } from '@tanstack/svelte-query';
  import { assignStudentToClass, createTransferRequest } from '$lib/api/students';
  import { type SchoolClass } from '$lib/api/academic';
  import { toast } from '$lib/stores/toast';

  interface Props {
    studentId: string;
    activeClass: SchoolClass | null;
    classes: SchoolClass[];
    years: import('$lib/api/academic').AcademicYear[];
    onDone: (newAssignmentId: string) => void;
  }
  const { studentId, activeClass, classes, years, onDone }: Props = $props();

  const qc = useQueryClient();

  type ActionMode = 'promote' | 'repeat' | 'demote' | 'first' | null;
  let actionMode     = $state<ActionMode>(null);
  let showTransfer   = $state(false);
  let caYearId       = $state('');
  let caClassId      = $state('');
  let caError        = $state('');
  let transferReason = $state('');
  let transferErr    = $state('');

  function openAction(mode: ActionMode) {
    actionMode = mode; caYearId = ''; caError = '';
    if (!activeClass) { caClassId = ''; return; }
    if (mode === 'promote') {
      caClassId = classes.find(
        c => c.level === activeClass.level
          && c.year_group === activeClass.year_group + 1
          && c.programme_id === activeClass.programme_id
          && (c.stream ?? null) === (activeClass.stream ?? null)
      )?.id ?? '';
    } else if (mode === 'repeat') {
      caClassId = activeClass.id;
    } else if (mode === 'demote') {
      caClassId = classes.find(
        c => c.level === activeClass.level
          && c.year_group === activeClass.year_group - 1
          && c.programme_id === activeClass.programme_id
          && (c.stream ?? null) === (activeClass.stream ?? null)
      )?.id ?? '';
    } else {
      caClassId = '';
    }
  }

  const assignMut = createMutation({
    mutationFn: () => assignStudentToClass({ student_id: studentId, class_id: caClassId, academic_year_id: caYearId }),
    onSuccess: (a) => {
      qc.invalidateQueries({ queryKey: ['student-class-assignments', studentId] });
      const labels: Record<string, string> = { promote: 'Promoted', repeat: 'Re-enrolled', demote: 'Demoted', first: 'Assigned' };
      toast.success(`${labels[actionMode ?? 'first'] ?? 'Done'}.`);
      onDone(a.id); actionMode = null; caYearId = ''; caClassId = ''; caError = '';
    },
    onError: (e: unknown) => { caError = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? 'Could not assign.'; },
  });

  const transferMut = createMutation({
    mutationFn: () => createTransferRequest(studentId, { reason: transferReason.trim() || undefined }),
    onSuccess: () => { showTransfer = false; transferReason = ''; transferErr = ''; toast.success('Transfer request submitted for review.'); },
    onError: (e: unknown) => { transferErr = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? 'Could not create transfer.'; },
  });

  function handleAssign() {
    caError = '';
    if (!caYearId)  { caError = 'Select an academic year.'; return; }
    if (!caClassId) { caError = 'Select a class.'; return; }
    $assignMut.mutate();
  }

  const CARD = {
    promote: { label: 'Promote',     sub: 'Move up a year',        border: 'border-green-200 dark:border-green-800', bg: 'bg-green-50 dark:bg-green-950/30', text: 'text-green-700 dark:text-green-400', sub2: 'text-green-600 dark:text-green-500' },
    repeat:  { label: 'Repeat year', sub: 'Same class, new year',  border: 'border-amber-200 dark:border-amber-800', bg: 'bg-amber-50 dark:bg-amber-950/30', text: 'text-amber-700 dark:text-amber-400', sub2: 'text-amber-600 dark:text-amber-500' },
    demote:  { label: 'Demote',      sub: 'Move down a year',      border: 'border-red-200 dark:border-red-800',     bg: 'bg-red-50 dark:bg-red-950/30',     text: 'text-red-700 dark:text-red-400',    sub2: 'text-red-600 dark:text-red-500'   },
  };
</script>

{#if !actionMode && !showTransfer}
  <!-- Year-end action cards -->
  <div class="rounded-2xl border border-[var(--border)] bg-[var(--card)] p-4">
    <p class="mb-3 text-[10px] font-bold uppercase tracking-widest text-[var(--fg-subtle)]">Year-end actions</p>
    <div class="grid grid-cols-2 gap-2 sm:grid-cols-4">
      {#each Object.entries(CARD) as [key, meta]}
        <button onclick={() => openAction(key as ActionMode)}
          class="rounded-xl border px-3 py-2.5 text-left transition hover:opacity-80 {meta.border} {meta.bg}">
          <p class="text-xs font-semibold {meta.text}">{meta.label}</p>
          <p class="mt-0.5 text-[10px] {meta.sub2}">{meta.sub}</p>
        </button>
      {/each}
      <button onclick={() => showTransfer = true}
        class="rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2.5 text-left transition hover:border-[var(--fg-subtle)]">
        <p class="text-xs font-semibold text-[var(--fg)]">Transfer out</p>
        <p class="mt-0.5 text-[10px] text-[var(--fg-muted)]">Leave this school</p>
      </button>
    </div>
  </div>

{:else if actionMode}
  {@const isPromote = actionMode === 'promote'}
  {@const isDemote  = actionMode === 'demote'}
  {@const meta = CARD[actionMode as keyof typeof CARD] ?? CARD.repeat}
  <div class="rounded-2xl border p-5 {meta.border} {meta.bg}">
    <p class="text-sm font-semibold {meta.text}">{meta.label}</p>
    {#if isDemote}
      <p class="mt-1.5 rounded-lg bg-red-100/60 px-3 py-1.5 text-xs font-medium text-red-700 dark:bg-red-950/30 dark:text-red-400">
        Demotion is uncommon. Confirm the target class carefully.
      </p>
    {/if}
    <div class="mt-4 grid gap-3 sm:grid-cols-2">
      <div>
        <label class="text-xs font-medium {meta.text}">Academic year</label>
        <select bind:value={caYearId} class="sel mt-1">
          <option value="">Select year…</option>
          {#each years as y}<option value={y.id}>{y.name}{y.is_current ? ' (current)' : ''}</option>{/each}
        </select>
      </div>
      <div>
        <label class="text-xs font-medium {meta.text}">Class
          {#if isPromote && caClassId}
            <span class="ml-1 rounded-full bg-green-100 px-1.5 py-0.5 text-[10px] font-semibold text-green-700 dark:bg-green-950/40 dark:text-green-300">suggested</span>
          {/if}
        </label>
        <select bind:value={caClassId} class="sel mt-1">
          <option value="">Select class…</option>
          {#each classes as c}<option value={c.id}>{c.display_name}</option>{/each}
        </select>
      </div>
    </div>
    {#if caError}<p class="mt-2 text-xs text-red-600">{caError}</p>{/if}
    <div class="mt-4 flex gap-2">
      <button onclick={handleAssign} disabled={$assignMut.isPending}
        class="rounded-xl px-4 py-2 text-sm font-semibold text-white transition hover:opacity-90 disabled:opacity-50"
        style="background: {isDemote ? '#dc2626' : 'var(--brand)'}">
        {$assignMut.isPending ? 'Saving…' : `Confirm ${meta.label}`}
      </button>
      <button onclick={() => { actionMode = null; caError = ''; }}
        class="rounded-xl border border-[var(--border)] bg-white/60 px-4 py-2 text-sm text-[var(--fg-muted)] hover:bg-white/80 transition dark:bg-white/5">
        Cancel
      </button>
    </div>
  </div>

{:else if showTransfer}
  <div class="rounded-2xl border border-[var(--border)] bg-[var(--card)] p-5">
    <p class="text-sm font-semibold text-[var(--fg)]">Transfer out</p>
    <p class="mt-0.5 text-xs text-[var(--fg-muted)]">Creates a request for admin review. Approval marks this student inactive.</p>
    <div class="mt-4">
      <label class="block text-xs font-medium text-[var(--fg-muted)]">Reason (optional)</label>
      <textarea bind:value={transferReason} rows="2" placeholder="e.g. Relocating to Accra"
        class="mt-1 w-full resize-none rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--fg)] placeholder:text-[var(--fg-subtle)] focus:border-[var(--brand)] focus:outline-none transition"></textarea>
    </div>
    {#if transferErr}<p class="mt-2 text-xs text-red-500">{transferErr}</p>{/if}
    <div class="mt-3 flex gap-2">
      <button onclick={() => $transferMut.mutate()} disabled={$transferMut.isPending}
        class="rounded-xl px-4 py-2 text-sm font-semibold text-white transition hover:opacity-90 disabled:opacity-50"
        style="background: var(--brand)">
        {$transferMut.isPending ? 'Submitting…' : 'Submit transfer request'}
      </button>
      <button onclick={() => { showTransfer = false; transferReason = ''; transferErr = ''; }}
        class="rounded-xl border border-[var(--border)] px-4 py-2 text-sm text-[var(--fg-muted)] hover:bg-[var(--hover)] transition">
        Cancel
      </button>
    </div>
  </div>
{/if}

<style>
  @reference "tailwindcss";
  .sel { @apply w-full rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--fg)] focus:border-[var(--brand)] focus:outline-none transition; }
</style>
