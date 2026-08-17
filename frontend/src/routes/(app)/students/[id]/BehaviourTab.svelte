<script lang="ts">
  import { createMutation, useQueryClient } from '@tanstack/svelte-query';
  import { reactiveQuery } from '$lib/query.svelte';
  import { useTermSelector } from '$lib/termSelector.svelte';
  import {
    listBehaviourRecords, createBehaviourRecord, deleteBehaviourRecord,
    SEVERITY_LABELS, type BehaviourRecord, type Severity,
  } from '$lib/api/behaviour';
  import { userRole } from '$lib/stores/permissions';
  import { toast } from '$lib/stores/toast';
  import ConfirmModal from '$lib/components/ConfirmModal.svelte';
  import OverrideReasonModal from '$lib/components/OverrideReasonModal.svelte';

  interface Props { studentId: string; canEdit?: boolean; }
  const { studentId, canEdit = true }: Props = $props();

  const qc = useQueryClient();
  // Recording behaviour is now a Class Teacher duty (assessments.record_behaviour,
  // scoped to this student's own class) as well as an admin/approver one — canEdit
  // reflects the student's own can_edit flag (StudentDetail), computed the same way
  // as every other pastoral tab.
  const canManage = $derived($userRole === 'admin' || $userRole === 'approver' || canEdit);
  const today = new Date().toISOString().slice(0, 10);

  const term = useTermSelector();
  const selectedTerm = $derived(term.terms.find(t => t.id === term.termId));

  const recordsQ = reactiveQuery(() => ({
    queryKey: ['behaviour-records', studentId, term.termId] as const,
    queryFn: () => listBehaviourRecords(studentId, term.termId),
    enabled: !!term.termId,
    staleTime: 30_000,
  }));
  function invalidateRecords() {
    qc.invalidateQueries({ queryKey: ['behaviour-records', studentId, term.termId] });
  }

  function detailOf(e: unknown): string | undefined {
    return (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
  }
  function isLocked(e: unknown): boolean {
    return (e as { response?: { status?: number } })?.response?.status === 423;
  }

  function severityColor(s: Severity): string {
    if (s === 'HIGH')   return 'bg-red-50 text-red-700 ring-red-600/20 dark:bg-red-950/30 dark:text-red-400';
    if (s === 'MEDIUM') return 'bg-amber-50 text-amber-700 ring-amber-600/20 dark:bg-amber-950/30 dark:text-amber-400';
    return 'bg-blue-50 text-blue-700 ring-blue-600/20 dark:bg-blue-950/30 dark:text-blue-400';
  }

  // ── Create ────────────────────────────────────────────────────────────────────
  let showCreate = $state(false);
  let cf = $state({ incident_type: '', description: '', severity: 'LOW' as Severity, action_taken: '', incident_date: today });
  let cfError = $state('');
  let cfOverrideNeeded = $state(false);

  function resetCreate() {
    cf = { incident_type: '', description: '', severity: 'LOW', action_taken: '', incident_date: today };
    cfError = ''; cfOverrideNeeded = false;
  }

  const createMut = createMutation({
    mutationFn: (overrideReason: string | undefined) => createBehaviourRecord({
      student_id: studentId, academic_term_id: term.termId,
      incident_type: cf.incident_type.trim(), description: cf.description.trim(),
      severity: cf.severity, action_taken: cf.action_taken.trim() || undefined,
      incident_date: cf.incident_date, override_reason: overrideReason,
    }),
    onSuccess: () => {
      invalidateRecords(); showCreate = false; resetCreate();
      toast.success('Incident recorded.');
    },
    onError: (e: unknown) => {
      if (isLocked(e)) { cfOverrideNeeded = true; cfError = detailOf(e) ?? 'This term is locked.'; return; }
      cfError = detailOf(e) ?? 'Could not save.';
    },
  });

  function submitCreate() {
    cfError = '';
    if (!cf.incident_type.trim())  { cfError = 'Incident type is required.'; return; }
    if (!cf.description.trim())    { cfError = 'Description is required.'; return; }
    if (!cf.incident_date)         { cfError = 'Incident date is required.'; return; }
    $createMut.mutate(undefined);
  }

  // ── Delete ────────────────────────────────────────────────────────────────────
  let deleteTarget = $state<BehaviourRecord | null>(null);
  let deleteOverrideNeeded = $state(false);
  let deleteError = $state('');

  const deleteMut = createMutation({
    mutationFn: (overrideReason: string | undefined) => deleteBehaviourRecord(deleteTarget!.id, overrideReason),
    onSuccess: () => {
      invalidateRecords(); deleteTarget = null; deleteOverrideNeeded = false; deleteError = '';
      toast.success('Incident deleted.');
    },
    onError: (e: unknown) => {
      if (isLocked(e)) { deleteOverrideNeeded = true; deleteError = detailOf(e) ?? 'This term is locked.'; return; }
      toast.error('Could not delete.');
      deleteTarget = null;
    },
  });
</script>

<!-- Term selector -->
<div class="mb-4 flex flex-wrap items-center justify-between gap-2">
  <div class="flex items-center gap-2">
    <select bind:value={term.termId} class="sel">
      {#each term.terms as t}<option value={t.id}>{t.name}{t.is_current ? ' (current)' : ''}</option>{/each}
    </select>
    {#if selectedTerm?.results_locked}
      <span class="rounded-full bg-red-50 px-2.5 py-0.5 text-[10px] font-bold text-red-700 ring-1 ring-inset ring-red-600/20 dark:bg-red-950/30 dark:text-red-400">
        Term locked
      </span>
    {/if}
  </div>
  {#if canManage && term.termId}
    <button onclick={() => { showCreate = !showCreate; resetCreate(); }}
      class="flex items-center gap-1.5 rounded-xl px-4 py-2 text-sm font-semibold text-white transition hover:opacity-90"
      style="background: var(--brand)">
      <svg class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" d="M12 4v16m8-8H4"/>
      </svg>
      Log incident
    </button>
  {/if}
</div>

<!-- Create form -->
{#if showCreate}
  <div class="mb-4 rounded-2xl border border-[var(--border)] bg-[var(--card)] p-5">
    <p class="mb-3 text-sm font-semibold text-[var(--fg)]">Log a new incident</p>
    <div class="grid gap-3 sm:grid-cols-2">
      <label class="block"><span class="lx">Incident type <span class="text-red-500">*</span></span>
        <input bind:value={cf.incident_type} placeholder="e.g. Late to class" class="inp mt-1" /></label>
      <label class="block"><span class="lx">Severity</span>
        <select bind:value={cf.severity} class="sel mt-1 w-full">
          {#each Object.entries(SEVERITY_LABELS) as [k, v]}<option value={k}>{v}</option>{/each}
        </select></label>
      <label class="block sm:col-span-2"><span class="lx">Description <span class="text-red-500">*</span></span>
        <textarea bind:value={cf.description} rows="2" class="inp mt-1"></textarea></label>
      <label class="block"><span class="lx">Incident date <span class="text-red-500">*</span></span>
        <input type="date" bind:value={cf.incident_date}
          min={selectedTerm?.start_date} max={selectedTerm?.end_date} class="inp mt-1" /></label>
      <label class="block"><span class="lx">Action taken <span class="font-normal text-[var(--fg-subtle)]">(optional)</span></span>
        <input bind:value={cf.action_taken} class="inp mt-1" /></label>
    </div>
    {#if cfError}<p class="mt-2 text-xs text-red-500">{cfError}</p>{/if}
    <div class="mt-3 flex gap-2">
      <button onclick={submitCreate} disabled={$createMut.isPending}
        class="rounded-xl px-4 py-2 text-sm font-semibold text-white disabled:opacity-50 transition hover:opacity-90" style="background: var(--brand)">
        {$createMut.isPending ? 'Saving…' : 'Save incident'}
      </button>
      <button onclick={() => { showCreate = false; resetCreate(); }}
        class="rounded-xl border border-[var(--border)] px-4 py-2 text-sm text-[var(--fg-muted)] hover:bg-[var(--hover)] transition">Cancel</button>
    </div>
  </div>
{/if}

<!-- Records list -->
{#if $recordsQ.isPending}
  <div class="space-y-2">{#each [1,2,3] as _}<div class="h-16 animate-pulse rounded-xl bg-[var(--hover)]"></div>{/each}</div>
{:else if ($recordsQ.data ?? []).length === 0}
  <div class="rounded-2xl border border-dashed border-[var(--border)] p-10 text-center">
    <p class="text-sm text-[var(--fg-muted)]">No behaviour records for this term.</p>
  </div>
{:else}
  <div class="space-y-2">
    {#each [...($recordsQ.data ?? [])].sort((a, b) => b.incident_date.localeCompare(a.incident_date)) as r (r.id)}
      <div class="rounded-2xl border border-[var(--border)] bg-[var(--card)] p-4">
        <div class="flex items-start justify-between gap-3">
          <div class="min-w-0">
            <div class="flex flex-wrap items-center gap-2">
              <span class="text-sm font-semibold text-[var(--fg)]">{r.incident_type}</span>
              <span class="rounded-full px-2 py-0.5 text-[10px] font-bold ring-1 ring-inset {severityColor(r.severity)}">
                {SEVERITY_LABELS[r.severity]}
              </span>
            </div>
            <p class="mt-1 text-sm text-[var(--fg-muted)]">{r.description}</p>
            {#if r.action_taken}<p class="mt-1 text-xs text-[var(--fg-subtle)]">Action taken: {r.action_taken}</p>{/if}
            <p class="mt-1 text-xs text-[var(--fg-subtle)]">{r.incident_date}</p>
          </div>
          {#if canManage}
            <button onclick={() => deleteTarget = r} aria-label="Delete behaviour record"
              class="flex min-h-[44px] min-w-[44px] shrink-0 items-center justify-center rounded-lg border border-[var(--border)] text-[var(--fg-subtle)] transition hover:border-red-200 hover:bg-red-50 hover:text-red-600 dark:hover:border-red-800 dark:hover:bg-red-950/30">
              <svg class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/>
              </svg>
            </button>
          {/if}
        </div>
      </div>
    {/each}
  </div>
{/if}

<ConfirmModal
  open={!!deleteTarget && !deleteOverrideNeeded}
  title="Delete this incident?"
  message="This permanently removes the behaviour record. This action is logged."
  confirmLabel="Delete"
  isPending={$deleteMut.isPending}
  onConfirm={() => $deleteMut.mutate(undefined)}
  onCancel={() => deleteTarget = null}
/>

<OverrideReasonModal
  open={cfOverrideNeeded || deleteOverrideNeeded}
  errorMessage={cfOverrideNeeded ? cfError : deleteError}
  isPending={cfOverrideNeeded ? $createMut.isPending : $deleteMut.isPending}
  onSubmit={(reason) => {
    if (cfOverrideNeeded) $createMut.mutate(reason);
    else if (deleteOverrideNeeded) $deleteMut.mutate(reason);
  }}
  onCancel={() => {
    if (cfOverrideNeeded) cfOverrideNeeded = false;
    else { deleteOverrideNeeded = false; deleteTarget = null; }
  }}
/>

<style>
  @reference "tailwindcss";
  .sel { @apply min-h-[44px] rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--fg)] focus:border-[var(--brand)] focus:outline-none transition; }
  .inp { @apply w-full rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--fg)] focus:border-[var(--brand)] focus:outline-none transition; }
  .lx  { @apply block text-xs font-medium text-[var(--fg-muted)]; }
</style>
