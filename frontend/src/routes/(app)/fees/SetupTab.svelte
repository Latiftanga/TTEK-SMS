<script lang="ts">
  import { createQuery, createMutation, useQueryClient } from '@tanstack/svelte-query';
  import { writable } from 'svelte/store';
  import { listClasses } from '$lib/api/academic';
  import { listFeeTypes, listFeeStructures, bulkAssignFees, ghs, type FeeType, type FeeStructure } from '$lib/api/fees';
  import { toast } from '$lib/stores/toast';
  import FeeTypeModal      from './FeeTypeModal.svelte';
  import FeeStructureModal from './FeeStructureModal.svelte';

  interface Props { termId: string; termName: string; }
  const { termId, termName }: Props = $props();

  const qc = useQueryClient();

  const classesQ = createQuery({ queryKey: ['classes'],   queryFn: listClasses,  staleTime: 10 * 60_000 });
  const typesQ   = createQuery({ queryKey: ['fee-types'], queryFn: listFeeTypes, staleTime:  5 * 60_000 });
  const classes  = $derived($classesQ.data ?? []);
  const feeTypes = $derived<FeeType[]>($typesQ.data ?? []);

  const structOpts = writable({ queryKey: ['fee-structures', termId] as const, queryFn: () => listFeeStructures(termId), enabled: !!termId, staleTime: 60_000 });
  $effect(() => {
    const tid = termId;
    structOpts.set({ queryKey: ['fee-structures', tid] as const, queryFn: () => listFeeStructures(tid), enabled: !!tid, staleTime: 60_000 });
  });
  const structQ    = createQuery(structOpts);
  const structures = $derived<FeeStructure[]>($structQ.data ?? []);

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

  let typeModal   = $state<{ editing: FeeType | null } | null>(null);
  let structModal = $state<{ editing: FeeStructure | null } | null>(null);

  function scopeLabel(s: FeeStructure): string {
    if (s.applies_to_class_id) return classes.find(c => c.id === s.applies_to_class_id)?.display_name ?? 'Specific class';
    if (s.applies_to_year_group || s.applies_to_programme_id) {
      const parts: string[] = [];
      if (s.applies_to_year_group) { const c = classes.find(x => x.year_group === s.applies_to_year_group); parts.push(c ? (c.level.toUpperCase() === 'CRECHE' ? c.level : `${c.level} ${s.applies_to_year_group}`) : `Year ${s.applies_to_year_group}`); }
      if (s.applies_to_programme_id) parts.push(classes.find(c => c.programme_id === s.applies_to_programme_id)?.programme_name ?? '');
      return parts.join(' · ');
    }
    return 'All students' + (s.boarding_only ? ' (boarding)' : '');
  }
</script>

<!-- Fee Structures -->
<div class="flex items-center justify-between">
  <h2 class="text-sm font-semibold text-[var(--fg)]">Fee Structures — {termName}</h2>
  <button onclick={() => structModal = { editing: null }} class="btn-primary">+ Structure</button>
</div>

{#if $structQ.isPending}
  <div class="space-y-2">{#each [0,1,2] as _}<div class="h-14 animate-pulse rounded-xl bg-[var(--card)]"></div>{/each}</div>
{:else if structures.length === 0}
  <div class="flex flex-col items-center justify-center rounded-2xl border border-dashed border-[var(--border)] py-12 text-center">
    <p class="mb-3 text-sm text-[var(--fg-muted)]">No fee structures for this term.</p>
    <button onclick={() => structModal = { editing: null }} class="btn-primary">Add first structure</button>
  </div>
{:else}
  <div class="rounded-2xl border border-[var(--border)] bg-[var(--card)]">
    <div class="hidden grid-cols-[1fr_auto_auto_auto_auto] gap-4 border-b border-[var(--border)] px-5 py-2.5 text-[10px] font-semibold uppercase tracking-widest text-[var(--fg-subtle)] sm:grid">
      <span>Fee Type</span><span class="text-right">Amount</span><span>Scope</span><span>Mandatory</span><span></span>
    </div>
    {#each structures as s}
      {@const ft = feeTypes.find(t => t.id === s.fee_type_id)}
      <div class="grid grid-cols-[1fr_auto] items-center gap-2 border-b border-[var(--border)] px-5 py-3 last:border-0 sm:grid-cols-[1fr_auto_auto_auto_auto] sm:gap-4">
        <div>
          <span class="text-sm font-medium text-[var(--fg)]">{s.fee_type_name}</span>
          {#if ft && !ft.is_recurring}
            <span class="ml-2 rounded-full bg-amber-50 px-2 py-0.5 text-[10px] font-semibold text-amber-700 dark:bg-amber-950/30 dark:text-amber-400">One-time</span>
          {/if}
        </div>
        <span class="tabular-nums text-sm text-[var(--fg)]">{ghs(s.amount)}</span>
        <span class="hidden text-xs text-[var(--fg-muted)] sm:block">{scopeLabel(s)}</span>
        <span class="hidden text-xs sm:block {s.is_mandatory ? 'text-green-600 dark:text-green-400' : 'text-[var(--fg-subtle)]'}">{s.is_mandatory ? '✓' : '—'}</span>
        <div class="flex items-center gap-2">
          <button onclick={() => structModal = { editing: s }} class="text-xs text-[var(--fg-muted)] transition hover:text-[var(--fg)]">Edit</button>
          <button onclick={() => { bulkingId = s.id; $bulkMut.mutate(s.id); }}
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

<!-- Fee Types -->
<div class="mt-6 flex items-center justify-between">
  <h2 class="text-sm font-semibold text-[var(--fg)]">Fee Types</h2>
  <button onclick={() => typeModal = { editing: null }} class="text-xs font-medium transition hover:underline" style="color: var(--brand)">+ Add type</button>
</div>

{#if $typesQ.isPending}
  <div class="space-y-2 mt-3">{#each [0,1,2] as _}<div class="h-10 animate-pulse rounded-xl bg-[var(--card)]"></div>{/each}</div>
{:else if feeTypes.length === 0}
  <div class="mt-3 rounded-2xl border border-dashed border-[var(--border)] py-8 text-center">
    <p class="text-sm text-[var(--fg-muted)]">No fee types yet. Create one to start building fee structures.</p>
  </div>
{:else}
  <div class="mt-3 rounded-2xl border border-[var(--border)] bg-[var(--card)]">
    {#each feeTypes as t}
      <div class="flex items-center gap-4 border-b border-[var(--border)] px-5 py-3 last:border-0">
        <div class="flex-1 min-w-0">
          <p class="text-sm font-medium text-[var(--fg)]">{t.name}</p>
          <p class="text-xs text-[var(--fg-muted)]">{t.code}{t.school_id === null ? ' · Platform template' : ''}</p>
        </div>
        <span class="text-xs {t.is_recurring ? 'text-[var(--fg-muted)]' : 'rounded-full bg-amber-50 px-2 py-0.5 font-semibold text-amber-700 dark:bg-amber-950/30 dark:text-amber-400'}">{t.is_recurring ? 'Recurring' : 'One-time'}</span>
        <span class="text-xs {t.is_active ? 'text-green-600 dark:text-green-400' : 'text-[var(--fg-subtle)]'}">{t.is_active ? 'Active' : 'Inactive'}</span>
        {#if t.school_id !== null}
          <button onclick={() => typeModal = { editing: t }} class="text-xs text-[var(--fg-muted)] transition hover:text-[var(--fg)]">Edit</button>
        {/if}
      </div>
    {/each}
  </div>
{/if}

{#if typeModal}
  <FeeTypeModal editing={typeModal.editing} onClose={() => { typeModal = null; }} />
{/if}
{#if structModal && termId}
  <FeeStructureModal editing={structModal.editing} {termId} {termName} {feeTypes} {classes} onClose={() => { structModal = null; }} />
{/if}
