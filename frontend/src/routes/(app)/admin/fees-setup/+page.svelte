<script lang="ts">
  import { createQuery, createMutation, useQueryClient } from '@tanstack/svelte-query';
  import { writable } from 'svelte/store';
  import { listAllTerms, listClasses, type AcademicTerm } from '$lib/api/academic';
  import {
    listFeeTypes, listFeeStructures, bulkAssignFees, ghs,
    type FeeType, type FeeStructure,
  } from '$lib/api/fees';
  import { toast } from '$lib/stores/toast';
  import FeeTypeModal from './FeeTypeModal.svelte';
  import FeeStructureModal from './FeeStructureModal.svelte';

  type Tab = 'types' | 'structures';
  let activeTab = $state<Tab>('structures');

  const qc = useQueryClient();

  // Terms
  const termsQ = createQuery({ queryKey: ['all-terms'], queryFn: listAllTerms, staleTime: 5 * 60_000 });
  const terms  = $derived<AcademicTerm[]>([...($termsQ.data ?? [])].sort((a, b) => b.start_date.localeCompare(a.start_date)));
  let termId = $state('');
  $effect(() => {
    if (!termId && terms.length) termId = terms.find(t => t.is_current)?.id ?? terms[0]?.id ?? '';
  });

  // Class levels (derived from school's actual classes)
  const classesQ  = createQuery({ queryKey: ['classes'], queryFn: listClasses, staleTime: 10 * 60_000 });
  const classLevels = $derived([...new Set(($classesQ.data ?? []).map(c => c.level))].sort());

  // Fee types
  const typesQ  = createQuery({ queryKey: ['fee-types'], queryFn: listFeeTypes, staleTime: 5 * 60_000 });
  const feeTypes = $derived<FeeType[]>($typesQ.data ?? []);

  // Fee structures (reactive on termId)
  const structOpts = writable({ queryKey: ['fee-structures', termId] as const, queryFn: () => listFeeStructures(termId), enabled: !!termId, staleTime: 60_000 });
  $effect(() => {
    const tid = termId;
    structOpts.set({ queryKey: ['fee-structures', tid] as const, queryFn: () => listFeeStructures(tid), enabled: !!tid, staleTime: 60_000 });
  });
  const structQ = createQuery(structOpts);
  const structures = $derived<FeeStructure[]>($structQ.data ?? []);

  // Bulk assign
  let bulkingId = $state<string | null>(null);
  const bulkMut = createMutation({
    mutationFn: (sid: string) => bulkAssignFees(sid),
    onSuccess: (res) => {
      toast.success(`Assigned: ${res.assigned} students, skipped: ${res.skipped} (already assigned).`);
      bulkingId = null;
    },
    onError: (e: unknown) => {
      toast.error((e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? 'Bulk assign failed.');
      bulkingId = null;
    },
  });

  // Modals
  let typeModal      = $state<{ editing: FeeType | null } | null>(null);
  let structModal    = $state<{ editing: FeeStructure | null } | null>(null);

  function currentTermName() { return terms.find(t => t.id === termId)?.name ?? ''; }
</script>

<svelte:head><title>Fee Structure — Setup</title></svelte:head>

<div class="space-y-6">
  <div class="flex flex-wrap items-center justify-between gap-3">
    <h1 class="text-xl font-bold text-[var(--fg)]">Fee Structure</h1>
    <div class="flex items-center gap-2">
      {#if activeTab === 'structures' && terms.length}
        <select bind:value={termId} class="sel">
          {#each terms as t}<option value={t.id}>{t.name}{t.is_current ? ' (current)' : ''}</option>{/each}
        </select>
      {/if}
      {#if activeTab === 'types'}
        <button onclick={() => typeModal = { editing: null }} class="btn-primary">+ Fee Type</button>
      {:else}
        <button onclick={() => structModal = { editing: null }} class="btn-primary">+ Structure</button>
      {/if}
    </div>
  </div>

  <!-- Tabs -->
  <div class="border-b border-[var(--border)]">
    <nav class="-mb-px flex gap-1">
      {#each ([['structures', 'Structures'], ['types', 'Fee Types']] as const) as [key, label]}
        <button onclick={() => activeTab = key}
          class="relative px-4 pb-3 pt-1 text-sm font-medium transition-colors
                 {activeTab === key ? 'text-[var(--brand)]' : 'text-[var(--fg-muted)] hover:text-[var(--fg)]'}">
          {label}
          <span class="pointer-events-none absolute bottom-0 left-0 right-0 h-0.5 rounded-t-sm
                       {activeTab === key ? 'bg-[var(--brand)]' : 'bg-transparent'}"></span>
        </button>
      {/each}
    </nav>
  </div>

  <!-- Structures tab -->
  {#if activeTab === 'structures'}
    {#if $structQ.isPending}
      <div class="space-y-2">{#each [0,1,2] as _}<div class="h-14 animate-pulse rounded-xl bg-[var(--card)]"></div>{/each}</div>
    {:else if structures.length === 0}
      <div class="flex flex-col items-center justify-center rounded-2xl border border-dashed border-[var(--border)] py-16 text-center">
        <p class="text-sm text-[var(--fg-muted)]">No fee structures for this term. Add one to get started.</p>
      </div>
    {:else}
      <div class="rounded-2xl border border-[var(--border)] bg-[var(--card)]">
        <div class="hidden grid-cols-[1fr_auto_auto_auto_auto] gap-4 border-b border-[var(--border)] px-5 py-2.5 text-[10px] font-semibold uppercase tracking-widest text-[var(--fg-subtle)] sm:grid">
          <span>Fee Type</span><span class="text-right">Amount</span><span>Scope</span><span>Mandatory</span><span></span>
        </div>
        {#each structures as s}
          {@const feeType = feeTypes.find(t => t.id === s.fee_type_id)}
          <div class="grid grid-cols-[1fr_auto] items-center gap-2 border-b border-[var(--border)] px-5 py-3 last:border-0 sm:grid-cols-[1fr_auto_auto_auto_auto] sm:gap-4">
            <div>
              <span class="text-sm font-medium text-[var(--fg)]">{s.fee_type_name}</span>
              {#if feeType && !feeType.is_recurring}
                <span class="ml-2 rounded-full bg-amber-50 px-2 py-0.5 text-[10px] font-semibold text-amber-700 dark:bg-amber-950/30 dark:text-amber-400">One-time · assign to one term only</span>
              {/if}
            </div>
            <span class="tabular-nums text-sm text-[var(--fg)]">{ghs(s.amount)}</span>
            <span class="hidden text-xs text-[var(--fg-muted)] sm:block">{s.applies_to_level ?? 'All levels'}</span>
            <span class="hidden text-xs sm:block {s.is_mandatory ? 'text-green-600 dark:text-green-400' : 'text-[var(--fg-subtle)]'}">{s.is_mandatory ? '✓' : '—'}</span>
            <div class="flex items-center gap-2">
              <button onclick={() => structModal = { editing: s }}
                class="text-xs text-[var(--fg-muted)] transition hover:text-[var(--fg)]">Edit</button>
              <button
                onclick={() => { bulkingId = s.id; $bulkMut.mutate(s.id); }}
                disabled={$bulkMut.isPending && bulkingId === s.id}
                class="rounded-lg border border-[var(--border)] px-2.5 py-1 text-xs font-medium transition hover:border-[var(--brand)] hover:text-[var(--brand)] disabled:opacity-50">
                {$bulkMut.isPending && bulkingId === s.id ? '…' : 'Bulk Assign'}
              </button>
            </div>
          </div>
        {/each}
      </div>
      <p class="text-xs text-[var(--fg-subtle)]">Bulk Assign creates fee records for all currently enrolled students who don't already have one.</p>
    {/if}
  {/if}

  <!-- Fee Types tab -->
  {#if activeTab === 'types'}
    {#if $typesQ.isPending}
      <div class="space-y-2">{#each [0,1,2] as _}<div class="h-14 animate-pulse rounded-xl bg-[var(--card)]"></div>{/each}</div>
    {:else if feeTypes.length === 0}
      <div class="flex flex-col items-center justify-center rounded-2xl border border-dashed border-[var(--border)] py-16 text-center">
        <p class="text-sm text-[var(--fg-muted)]">No fee types yet. Create one to start building fee structures.</p>
      </div>
    {:else}
      <div class="rounded-2xl border border-[var(--border)] bg-[var(--card)]">
        {#each feeTypes as t}
          <div class="flex items-center gap-4 border-b border-[var(--border)] px-5 py-3 last:border-0">
            <div class="flex-1 min-w-0">
              <p class="text-sm font-medium text-[var(--fg)]">{t.name}</p>
              <p class="text-xs text-[var(--fg-muted)]">{t.code}{t.school_id === null ? ' · Platform template' : ''}</p>
            </div>
            {#if t.is_recurring}
              <span class="text-xs text-[var(--fg-muted)]">Recurring</span>
            {:else}
              <span class="rounded-full bg-amber-50 px-2 py-0.5 text-[10px] font-semibold text-amber-700 dark:bg-amber-950/30 dark:text-amber-400">One-time annual</span>
            {/if}
            <span class="text-xs {t.is_active ? 'text-green-600 dark:text-green-400' : 'text-[var(--fg-subtle)]'}">{t.is_active ? 'Active' : 'Inactive'}</span>
            {#if t.school_id !== null}
              <button onclick={() => typeModal = { editing: t }}
                class="text-xs text-[var(--fg-muted)] transition hover:text-[var(--fg)]">Edit</button>
            {/if}
          </div>
        {/each}
      </div>
    {/if}
  {/if}
</div>

{#if typeModal}
  <FeeTypeModal editing={typeModal.editing} onClose={() => typeModal = null} />
{/if}

{#if structModal && termId}
  <FeeStructureModal
    editing={structModal.editing}
    {termId}
    termName={currentTermName()}
    {feeTypes}
    levels={classLevels}
    onClose={() => structModal = null}
  />
{/if}

<style>
  @reference "tailwindcss";
  .sel { @apply rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--fg)] focus:border-[var(--brand)] focus:outline-none transition; }
</style>
