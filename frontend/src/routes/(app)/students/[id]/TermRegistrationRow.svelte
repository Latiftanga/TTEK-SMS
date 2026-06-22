<script lang="ts">
  import { createQuery, createMutation, useQueryClient } from '@tanstack/svelte-query';
  import {
    listSubjectRegistrations, registerSubjects, removeSubjectRegistration,
    type TermEnrollmentRead,
  } from '$lib/api/students';
  import { listClassSubjects, listSubjects, type Subject } from '$lib/api/academic';
  import { toast } from '$lib/stores/toast';

  interface Props {
    enrollment: TermEnrollmentRead;
    termLabel: string;
    inline?: boolean;
  }
  const { enrollment, termLabel, inline = false }: Props = $props();

  const qc = useQueryClient();
  let expanded    = $state(false);
  let showAddForm = $state(false);
  let subjectId   = $state('');
  let regType     = $state<'CORE' | 'ELECTIVE'>('CORE');
  let addError    = $state('');

  const subjectRegsQ = createQuery({
    queryKey: ['term-subject-regs', enrollment.id],
    queryFn:  () => listSubjectRegistrations(enrollment.id),
    enabled:  () => expanded,
    staleTime: 60_000,
  });

  const allSubjectsQ = createQuery({
    queryKey: ['subjects'],
    queryFn:  listSubjects,
    enabled:  () => expanded,
    staleTime: 5 * 60_000,
  });

  const classSubjectsQ = createQuery({
    queryKey: ['class-subjects', enrollment.class_id],
    queryFn:  () => enrollment.class_id ? listClassSubjects(enrollment.class_id) : Promise.resolve([]),
    enabled:  () => expanded && !!enrollment.class_id,
    staleTime: 5 * 60_000,
  });

  const registeredIds = $derived(new Set(($subjectRegsQ.data ?? []).map(r => r.subject_id)));

  const availableSubjects = $derived.by<Subject[]>(() => {
    const all = $allSubjectsQ.data ?? [];
    const cls = $classSubjectsQ.data;
    if (cls && cls.length > 0) {
      return cls
        .filter(cs => !registeredIds.has(cs.subject_id))
        .map(cs => all.find(s => s.id === cs.subject_id))
        .filter((s): s is Subject => !!s);
    }
    return all.filter(s => !registeredIds.has(s.id));
  });

  const subjectName = (id: string) =>
    ($allSubjectsQ.data ?? []).find(s => s.id === id)?.name ?? '—';

  const addMut = createMutation({
    mutationFn: () => registerSubjects(enrollment.id, [{ subject_id: subjectId, registration_type: regType }]),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['term-subject-regs', enrollment.id] });
      subjectId = ''; regType = 'CORE'; addError = ''; showAddForm = false;
      toast.success('Subject added.');
    },
    onError: (e: unknown) => {
      addError = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
        ?? 'Could not add subject.';
    },
  });

  function handleAdd() {
    addError = '';
    if (!subjectId) { addError = 'Select a subject.'; return; }
    $addMut.mutate();
  }

  const removeMut = createMutation({
    mutationFn: (regId: string) => removeSubjectRegistration(enrollment.id, regId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['term-subject-regs', enrollment.id] });
      toast.success('Subject removed.');
    },
    onError: (e: unknown) => {
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
        ?? 'Could not remove subject.';
      toast.error(msg);
    },
  });

  function toggle() {
    expanded = !expanded;
    if (!expanded) { showAddForm = false; subjectId = ''; addError = ''; }
  }

  function closeForm() { showAddForm = false; subjectId = ''; addError = ''; }
</script>

{#snippet addForm(compact: boolean)}
  <div class="space-y-2.5 {compact ? 'py-2' : 'rounded-xl border border-[var(--border)] bg-[var(--bg)] p-3'}">
    <select bind:value={subjectId} class="sel w-full">
      <option value="">Select subject…</option>
      {#each availableSubjects as s}<option value={s.id}>{s.name}</option>{/each}
      {#if availableSubjects.length === 0 && !$allSubjectsQ.isPending}
        <option disabled>All subjects registered</option>
      {/if}
    </select>

    <!-- Core / Elective toggle -->
    <div class="flex overflow-hidden rounded-lg border border-[var(--border)]">
      <button type="button" onclick={() => regType = 'CORE'}
        class="flex-1 py-1.5 text-xs font-semibold transition
          {regType === 'CORE' ? 'text-white' : 'bg-[var(--bg)] text-[var(--fg-muted)] hover:bg-[var(--hover)]'}"
        style={regType === 'CORE' ? 'background: var(--brand)' : ''}>
        Core
      </button>
      <button type="button" onclick={() => regType = 'ELECTIVE'}
        class="flex-1 border-l border-[var(--border)] py-1.5 text-xs font-semibold transition
          {regType === 'ELECTIVE' ? 'text-white' : 'bg-[var(--bg)] text-[var(--fg-muted)] hover:bg-[var(--hover)]'}"
        style={regType === 'ELECTIVE' ? 'background: var(--brand)' : ''}>
        Elective
      </button>
    </div>

    {#if addError}<p class="text-xs text-red-500">{addError}</p>{/if}

    <div class="flex items-center gap-3">
      <button onclick={handleAdd} disabled={$addMut.isPending || !subjectId}
        class="rounded-lg px-4 py-1.5 text-xs font-semibold text-white disabled:opacity-40 transition hover:opacity-90"
        style="background: var(--brand)">
        {$addMut.isPending ? 'Adding…' : 'Add subject'}
      </button>
      <button onclick={closeForm} class="text-xs text-[var(--fg-muted)] hover:text-[var(--fg)] transition">
        Cancel
      </button>
    </div>
  </div>
{/snippet}

{#snippet subjectList()}
  {#if $subjectRegsQ.isPending}
    {#each [1, 2] as _}
      <div class="h-7 animate-pulse rounded-lg bg-[var(--hover)]"></div>
    {/each}
  {:else if ($subjectRegsQ.data ?? []).length === 0 && !showAddForm}
    <p class="text-xs text-[var(--fg-muted)]">No subjects registered yet.</p>
  {:else}
    {#each $subjectRegsQ.data ?? [] as reg (reg.id)}
      <div class="flex items-center justify-between py-1 group">
        <span class="text-sm text-[var(--fg)]">{subjectName(reg.subject_id)}</span>
        <div class="flex items-center gap-2">
          <span class="rounded-full px-2.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide {
            reg.registration_type === 'CORE'
              ? 'bg-blue-50 text-blue-700 ring-1 ring-inset ring-blue-600/20 dark:bg-blue-950/30 dark:text-blue-400'
              : 'bg-amber-50 text-amber-700 ring-1 ring-inset ring-amber-600/20 dark:bg-amber-950/30 dark:text-amber-400'
          }">{reg.registration_type === 'CORE' ? 'Core' : 'Elective'}</span>
          <button
            onclick={() => $removeMut.mutate(reg.id)}
            disabled={$removeMut.isPending && $removeMut.variables === reg.id}
            class="rounded p-0.5 text-[var(--fg-subtle)] opacity-0 group-hover:opacity-100 transition
                   hover:bg-red-50 hover:text-red-500 dark:hover:bg-red-950/30 disabled:opacity-30"
            title="Remove subject">
            <svg class="h-3.5 w-3.5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12"/>
            </svg>
          </button>
        </div>
      </div>
    {/each}
  {/if}
{/snippet}

<!-- ── INLINE mode: flat tree row ─────────────────────────────────────────────── -->
{#if inline}
  <div>
    <button onclick={toggle}
      class="flex w-full items-center gap-2 rounded-lg py-2 pl-1 pr-2 text-left transition hover:bg-[var(--hover)]">
      <svg class="h-3.5 w-3.5 shrink-0 text-[var(--fg-muted)] transition-transform duration-150 {expanded ? 'rotate-90' : ''}"
        fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" d="M9 5l7 7-7 7"/>
      </svg>
      <span class="flex-1 text-sm font-medium text-[var(--fg)]">{termLabel}</span>
      <span class="pill-green">
        <svg class="h-3.5 w-3.5" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24"><polyline points="20 6 9 17 4 12"/></svg>
        Registered
      </span>
    </button>

    {#if expanded}
      <div class="mb-2 ml-4 mt-1 space-y-2 border-l-2 pl-3"
        style="border-color: color-mix(in srgb, var(--brand) 35%, transparent)">

        <!-- Header -->
        <div class="flex items-center justify-between pt-1">
          <p class="text-xs font-semibold text-[var(--fg-muted)]">
            Subject Registration
            {#if !$subjectRegsQ.isPending}
              <span class="ml-1 font-normal text-[var(--fg-muted)]">
                · {($subjectRegsQ.data ?? []).length} registered
              </span>
            {/if}
          </p>
          {#if !showAddForm && !$allSubjectsQ.isPending}
            <button onclick={() => showAddForm = true}
              class="rounded-lg px-2.5 py-1 text-xs font-semibold text-white transition hover:opacity-90"
              style="background: var(--brand)">
              + Add subject
            </button>
          {/if}
        </div>

        {#if showAddForm}{@render addForm(true)}{/if}
        {@render subjectList()}
      </div>
    {/if}
  </div>

<!-- ── STANDALONE mode: full card ─────────────────────────────────────────────── -->
{:else}
  <div class="overflow-hidden rounded-2xl border border-[var(--border)] bg-[var(--card)]">
    <button onclick={toggle}
      class="flex w-full items-center gap-3 px-4 py-3.5 text-left transition hover:bg-[var(--hover)]">
      <svg class="h-4 w-4 shrink-0 text-[var(--fg-muted)] transition-transform duration-200 {expanded ? 'rotate-90' : ''}"
        fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" d="M9 5l7 7-7 7"/>
      </svg>
      <div class="flex flex-1 min-w-0 items-center gap-2">
        <span class="text-sm font-semibold text-[var(--fg)]">{termLabel}</span>
        <span class="text-[10px] text-[var(--fg-muted)]">Term Registration</span>
      </div>
      <span class="pill-green">
        <svg class="h-3.5 w-3.5" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24"><polyline points="20 6 9 17 4 12"/></svg>
        Registered
      </span>
    </button>

    {#if expanded}
      <div class="border-t border-[var(--border)] px-4 pb-4 pt-3 space-y-3">
        <div class="flex items-center justify-between">
          <p class="text-xs font-semibold uppercase tracking-wide text-[var(--fg-muted)]">
            Subject Registration
            {#if !$subjectRegsQ.isPending}
              <span class="ml-1 font-normal normal-case text-[var(--fg-muted)]">
                · {($subjectRegsQ.data ?? []).length} registered
              </span>
            {/if}
          </p>
          {#if !showAddForm && !$allSubjectsQ.isPending}
            <button onclick={() => showAddForm = true}
              class="rounded-lg px-3 py-1.5 text-xs font-semibold text-white transition hover:opacity-90"
              style="background: var(--brand)">
              + Add subject
            </button>
          {/if}
        </div>

        {#if showAddForm}{@render addForm(false)}{/if}
        {@render subjectList()}
      </div>
    {/if}
  </div>
{/if}

<style>
  @reference "tailwindcss";
  .sel       { @apply rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--fg)] focus:border-[var(--brand)] focus:outline-none transition; }
  .pill-green { @apply shrink-0 flex items-center gap-1 text-xs font-semibold text-green-600 dark:text-green-500; }
</style>
