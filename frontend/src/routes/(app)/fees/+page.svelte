<script lang="ts">
  import { createQuery, createMutation, useQueryClient } from '@tanstack/svelte-query';
  import { writable } from 'svelte/store';
  import { isSchoolAdmin } from '$lib/stores/permissions';
  import { currentUser } from '$lib/stores/auth';
  import { listAllTerms, listClasses, type AcademicTerm } from '$lib/api/academic';
  import { listStudents, type StudentSummary } from '$lib/api/students';
  import {
    listStudentFeeRecords, getFeeSummary, listPayments,
    listFeeTypes, listFeeStructures, bulkAssignFees,
    ghs, PAYMENT_METHOD_LABELS,
    type FeeRecord, type FeePayment, type FeeSummary, type FeeType, type FeeStructure,
  } from '$lib/api/fees';
  import { toast } from '$lib/stores/toast';
  import PaymentModal from './PaymentModal.svelte';
  import FeeTypeModal from '../admin/fees-setup/FeeTypeModal.svelte';
  import FeeStructureModal from '../admin/fees-setup/FeeStructureModal.svelte';

  const isAdmin = $derived($isSchoolAdmin || !!$currentUser?.is_superadmin);

  type MainTab = 'payments' | 'setup';
  let activeTab = $state<MainTab>('payments');

  const qc = useQueryClient();

  // ── Terms ─────────────────────────────────────────────────────────────────────
  const termsQ = createQuery({ queryKey: ['all-terms'], queryFn: listAllTerms, staleTime: 5 * 60_000 });
  const terms  = $derived<AcademicTerm[]>([...($termsQ.data ?? [])].sort((a, b) => b.start_date.localeCompare(a.start_date)));
  let termId   = $state('');
  $effect(() => {
    if (!termId && terms.length) termId = terms.find(t => t.is_current)?.id ?? terms[0]?.id ?? '';
  });

  // ── Setup data (only fetched when admin) ──────────────────────────────────────
  const classesQ   = createQuery({ queryKey: ['classes'],   queryFn: listClasses,  staleTime: 10 * 60_000 });
  const typesQ     = createQuery({ queryKey: ['fee-types'], queryFn: listFeeTypes, staleTime: 5 * 60_000  });
  const classes    = $derived($classesQ.data ?? []);
  const feeTypes   = $derived<FeeType[]>($typesQ.data ?? []);

  const structOpts = writable({ queryKey: ['fee-structures', ''] as const, queryFn: () => listFeeStructures(''), enabled: false, staleTime: 60_000 });
  $effect(() => {
    const tid = termId;
    structOpts.set({ queryKey: ['fee-structures', tid] as const, queryFn: () => listFeeStructures(tid), enabled: !!tid, staleTime: 60_000 });
  });
  const structQ    = createQuery(structOpts);
  const structures = $derived<FeeStructure[]>($structQ.data ?? []);

  let bulkingId = $state<string | null>(null);
  const bulkMut = createMutation({
    mutationFn: (sid: string) => bulkAssignFees(sid),
    onSuccess: (res: { assigned: number; skipped: number }) => {
      toast.success(`Assigned: ${res.assigned} students, skipped: ${res.skipped} already assigned.`);
      bulkingId = null;
    },
    onError: (e: unknown) => {
      toast.error((e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? 'Bulk assign failed.');
      bulkingId = null;
    },
  });

  let typeModal   = $state<{ editing: FeeType | null } | null>(null);
  let structModal = $state<{ editing: FeeStructure | null } | null>(null);

  // ── Payments tab ──────────────────────────────────────────────────────────────
  let searchText  = $state('');
  let showResults = $state(false);
  const searchOpts = writable({ queryKey: ['student-search', ''] as const, queryFn: () => listStudents({ search: '', limit: 8, active_only: true }), enabled: false });
  $effect(() => {
    const q = searchText.trim();
    searchOpts.set({ queryKey: ['student-search', q] as const, queryFn: () => listStudents({ search: q, limit: 8, active_only: true }), enabled: q.length >= 2 });
    showResults = q.length >= 2;
  });
  const searchQ       = createQuery(searchOpts);
  const searchResults = $derived<StudentSummary[]>($searchQ.data ?? []);

  let selected = $state<StudentSummary | null>(null);
  let records  = $state<FeeRecord[]>([]);
  let payments = $state<FeePayment[]>([]);
  let summary  = $state<FeeSummary | null>(null);
  let loading  = $state(false);

  async function loadFeeData(sid: string, tid: string) {
    loading = true;
    try {
      const [r, p, s] = await Promise.allSettled([
        listStudentFeeRecords(sid, tid),
        listPayments(sid, tid),
        getFeeSummary(sid, tid),
      ]);
      records  = r.status === 'fulfilled' ? r.value : [];
      payments = p.status === 'fulfilled' ? p.value : [];
      summary  = s.status === 'fulfilled' ? s.value : null;
    } finally { loading = false; }
  }

  $effect(() => { if (selected && termId) loadFeeData(selected.id, termId); });

  function pick(s: StudentSummary) { selected = s; searchText = ''; showResults = false; }

  const paidByRecord = $derived.by(() => {
    const m = new Map<string, number>();
    for (const p of payments) m.set(p.fee_record_id, (m.get(p.fee_record_id) ?? 0) + parseFloat(p.amount_paid));
    return m;
  });

  let payRecord = $state<FeeRecord | null>(null);
  function remainingFor(r: FeeRecord) { return Math.max(0, parseFloat(r.amount_due) - (paidByRecord.get(r.id) ?? 0)); }
  function initials(s: StudentSummary) { return (s.first_name[0] + s.last_name[0]).toUpperCase(); }
  function termName(id: string) { return terms.find(t => t.id === id)?.name ?? ''; }
</script>

<svelte:head><title>Fees</title></svelte:head>

<div class="space-y-6">
  <!-- Header -->
  <div class="flex flex-wrap items-center justify-between gap-3">
    <h1 class="text-xl font-bold text-[var(--fg)]">Fees</h1>
    {#if terms.length}
      <select bind:value={termId} class="sel max-w-xs">
        {#each terms as t}<option value={t.id}>{t.name}{t.is_current ? ' (current)' : ''}</option>{/each}
      </select>
    {/if}
  </div>

  <!-- Tabs — only shown for admins -->
  {#if isAdmin}
    <div class="border-b border-[var(--border)]">
      <nav class="-mb-px flex gap-1">
        <button onclick={() => activeTab = 'payments'}
          class="relative px-4 pb-3 pt-1 text-sm font-medium transition-colors
                 {activeTab === 'payments' ? 'text-[var(--brand)]' : 'text-[var(--fg-muted)] hover:text-[var(--fg)]'}">
          Payments
          <span class="pointer-events-none absolute bottom-0 left-0 right-0 h-0.5 rounded-t-sm
                       {activeTab === 'payments' ? 'bg-[var(--brand)]' : 'bg-transparent'}"></span>
        </button>
        <button onclick={() => activeTab = 'setup'}
          class="relative px-4 pb-3 pt-1 text-sm font-medium transition-colors
                 {activeTab === 'setup' ? 'text-[var(--brand)]' : 'text-[var(--fg-muted)] hover:text-[var(--fg)]'}">
          Fee Setup
          <span class="pointer-events-none absolute bottom-0 left-0 right-0 h-0.5 rounded-t-sm
                       {activeTab === 'setup' ? 'bg-[var(--brand)]' : 'bg-transparent'}"></span>
        </button>
      </nav>
    </div>
  {/if}

  <!-- ── PAYMENTS ──────────────────────────────────────────────────────────────── -->
  {#if activeTab === 'payments'}
    <div class="relative">
      <div class="flex items-center gap-2 rounded-2xl border border-[var(--border)] bg-[var(--card)] px-4 py-3">
        <svg class="h-4 w-4 shrink-0 text-[var(--fg-muted)]" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
          <circle cx="11" cy="11" r="8"/><path stroke-linecap="round" stroke-linejoin="round" d="M21 21l-4.35-4.35"/>
        </svg>
        <input bind:value={searchText} onfocus={() => { if (searchText.length >= 2) showResults = true; }}
          placeholder="Search student by name or admission number…"
          class="min-w-0 flex-1 bg-transparent text-sm text-[var(--fg)] placeholder:text-[var(--fg-subtle)] focus:outline-none" />
        {#if selected}
          <button onclick={() => { selected = null; records = []; payments = []; summary = null; searchText = ''; }}
            class="shrink-0 text-xs text-[var(--fg-muted)] transition hover:text-[var(--fg)]">Clear ✕</button>
        {/if}
      </div>

      {#if showResults && searchResults.length > 0}
        <div class="absolute left-0 right-0 top-full z-20 mt-1 overflow-hidden rounded-xl border border-[var(--border)] bg-[var(--card)] shadow-xl">
          {#each searchResults as s}
            <button onclick={() => pick(s)}
              class="flex w-full items-center gap-3 px-4 py-2.5 text-left transition hover:bg-[var(--hover)]">
              <div class="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-[var(--brand)]/10 text-xs font-bold text-[var(--brand)]">
                {initials(s)}
              </div>
              <div>
                <p class="text-sm font-medium text-[var(--fg)]">{s.display_name}</p>
                <p class="text-xs text-[var(--fg-muted)]">{s.admission_number}{s.current_class_name ? ' · ' + s.current_class_name : ''}</p>
              </div>
            </button>
          {/each}
        </div>
      {/if}
    </div>

    {#if selected}
      <div class="rounded-2xl border border-[var(--border)] bg-[var(--card)] p-5">
        <div class="flex items-center gap-3">
          <div class="flex h-10 w-10 shrink-0 items-center justify-center rounded-full text-sm font-bold text-white" style="background: var(--brand)">{initials(selected)}</div>
          <div>
            <p class="font-semibold text-[var(--fg)]">{selected.display_name}</p>
            <p class="text-xs text-[var(--fg-muted)]">{selected.admission_number}{selected.current_class_name ? ' · ' + selected.current_class_name : ''}</p>
          </div>
        </div>
        {#if loading}
          <div class="mt-4 grid grid-cols-3 gap-3">{#each [0,1,2] as _}<div class="h-14 animate-pulse rounded-xl bg-[var(--hover)]"></div>{/each}</div>
        {:else if summary}
          {@const bal = parseFloat(summary.balance)}
          <div class="mt-4 grid grid-cols-3 gap-3 border-t border-[var(--border)] pt-4">
            <div class="rounded-xl bg-[var(--hover)] px-4 py-3 text-center">
              <p class="text-[10px] font-semibold uppercase tracking-widest text-[var(--fg-subtle)]">Total Due</p>
              <p class="mt-1 text-base font-bold text-[var(--fg)]">{ghs(summary.total_due)}</p>
            </div>
            <div class="rounded-xl bg-[var(--hover)] px-4 py-3 text-center">
              <p class="text-[10px] font-semibold uppercase tracking-widest text-[var(--fg-subtle)]">Paid</p>
              <p class="mt-1 text-base font-bold text-green-600 dark:text-green-400">{ghs(summary.total_paid)}</p>
            </div>
            <div class="rounded-xl px-4 py-3 text-center {bal > 0 ? 'bg-red-50 dark:bg-red-950/30' : 'bg-[var(--hover)]'}">
              <p class="text-[10px] font-semibold uppercase tracking-widest text-[var(--fg-subtle)]">Balance</p>
              <p class="mt-1 text-base font-bold {bal > 0 ? 'text-red-600 dark:text-red-400' : 'text-green-600 dark:text-green-400'}">{ghs(summary.balance)}</p>
            </div>
          </div>
        {:else if records.length === 0}
          <p class="mt-4 text-sm text-[var(--fg-muted)]">No fee records for {termName(termId)}. Fees need to be assigned first.</p>
        {/if}
      </div>

      {#if !loading && records.length > 0}
        <div class="rounded-2xl border border-[var(--border)] bg-[var(--card)]">
          <div class="border-b border-[var(--border)] px-5 py-3">
            <h2 class="text-sm font-semibold text-[var(--fg)]">Fee Records</h2>
          </div>
          <div class="divide-y divide-[var(--border)]">
            {#each records as r}
              {@const paid = paidByRecord.get(r.id) ?? 0}
              {@const remaining = Math.max(0, parseFloat(r.amount_due) - paid)}
              <div class="flex items-center gap-4 px-5 py-3">
                <div class="flex-1 min-w-0">
                  <p class="text-sm font-medium text-[var(--fg)]">{r.fee_type_name}</p>
                  {#if r.due_date}<p class="text-xs text-[var(--fg-muted)]">Due {r.due_date}</p>{/if}
                </div>
                <div class="text-right tabular-nums text-sm text-[var(--fg)]">{ghs(r.amount_due)}</div>
                <div class="text-right tabular-nums text-sm text-green-600 dark:text-green-400">{paid > 0 ? ghs(paid) : '—'}</div>
                <div class="w-24 text-right">
                  {#if r.is_waived}
                    <span class="rounded-full bg-blue-50 px-2 py-0.5 text-xs font-medium text-blue-700 dark:bg-blue-950/30 dark:text-blue-300">Waived</span>
                  {:else if remaining <= 0}
                    <span class="text-xs font-semibold text-green-600 dark:text-green-400">✓ Paid</span>
                  {:else}
                    <button onclick={() => payRecord = r}
                      class="rounded-lg border border-[var(--brand)] px-2.5 py-1 text-xs font-semibold text-[var(--brand)] transition hover:bg-[var(--brand)] hover:text-white">
                      Pay
                    </button>
                  {/if}
                </div>
              </div>
            {/each}
          </div>
        </div>
      {/if}

      {#if !loading && payments.length > 0}
        <div class="rounded-2xl border border-[var(--border)] bg-[var(--card)]">
          <div class="border-b border-[var(--border)] px-5 py-3">
            <h2 class="text-sm font-semibold text-[var(--fg)]">Payment History</h2>
          </div>
          <div class="divide-y divide-[var(--border)]">
            {#each [...payments].sort((a,b) => b.payment_date.localeCompare(a.payment_date)) as p}
              {@const recName = records.find(r => r.id === p.fee_record_id)?.fee_type_name ?? ''}
              <div class="flex items-center gap-4 px-5 py-3">
                <div class="flex-1 min-w-0">
                  <p class="text-sm text-[var(--fg)]">{recName || 'Fee payment'}</p>
                  <p class="text-xs text-[var(--fg-muted)]">{PAYMENT_METHOD_LABELS[p.payment_method]}{p.reference_number ? ' · ' + p.reference_number : ''}</p>
                </div>
                <div class="text-right">
                  <p class="text-sm font-semibold text-green-600 dark:text-green-400">{ghs(p.amount_paid)}</p>
                  <p class="text-xs text-[var(--fg-muted)]">{p.payment_date}</p>
                </div>
              </div>
            {/each}
          </div>
        </div>
      {/if}
    {:else}
      <div class="flex flex-col items-center justify-center rounded-2xl border border-dashed border-[var(--border)] py-16 text-center">
        <p class="text-sm text-[var(--fg-muted)]">Search for a student above to view and record fee payments.</p>
      </div>
    {/if}
  {/if}

  <!-- ── FEE SETUP (admin only) ─────────────────────────────────────────────── -->
  {#if activeTab === 'setup' && isAdmin}
    <!-- Structures -->
    <div class="flex items-center justify-between">
      <h2 class="text-sm font-semibold text-[var(--fg)]">Fee Structures</h2>
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
            <span class="hidden text-xs text-[var(--fg-muted)] sm:block">
              {#if s.applies_to_class_id}
                {classes.find(c => c.id === s.applies_to_class_id)?.display_name ?? 'Specific class'}
              {:else if s.applies_to_year_group || s.applies_to_programme_id}
                {#if s.applies_to_year_group}{@const r = classes.find(c => c.year_group === s.applies_to_year_group)}{r ? `${r.level} ${s.applies_to_year_group}` : `Year ${s.applies_to_year_group}`}{/if}{s.applies_to_year_group && s.applies_to_programme_id ? ' · ' : ''}{#if s.applies_to_programme_id}{classes.find(c => c.programme_id === s.applies_to_programme_id)?.programme_name ?? ''}{/if}
              {:else}All students{/if}{s.boarding_only ? ' (boarding)' : ''}
            </span>
            <span class="hidden text-xs sm:block {s.is_mandatory ? 'text-green-600 dark:text-green-400' : 'text-[var(--fg-subtle)]'}">{s.is_mandatory ? '✓' : '—'}</span>
            <div class="flex items-center gap-2">
              <button onclick={() => structModal = { editing: s }} class="text-xs text-[var(--fg-muted)] transition hover:text-[var(--fg)]">Edit</button>
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

    <!-- Fee Types -->
    <div class="mt-4">
      <div class="mb-3 flex items-center justify-between">
        <h2 class="text-sm font-semibold text-[var(--fg)]">Fee Types</h2>
        <button onclick={() => typeModal = { editing: null }} class="text-xs font-medium" style="color: var(--brand)">+ Add type</button>
      </div>
      {#if $typesQ.isPending}
        <div class="space-y-2">{#each [0,1,2] as _}<div class="h-10 animate-pulse rounded-xl bg-[var(--card)]"></div>{/each}</div>
      {:else if feeTypes.length === 0}
        <div class="rounded-2xl border border-dashed border-[var(--border)] py-8 text-center">
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
                <button onclick={() => typeModal = { editing: t }} class="text-xs text-[var(--fg-muted)] transition hover:text-[var(--fg)]">Edit</button>
              {/if}
            </div>
          {/each}
        </div>
      {/if}
    </div>
  {/if}
</div>

<!-- Modals -->
{#if payRecord && selected}
  <PaymentModal
    record={payRecord}
    studentId={selected.id}
    {termId}
    remainingBalance={remainingFor(payRecord)}
    onClose={() => payRecord = null}
    onSuccess={() => { payRecord = null; loadFeeData(selected!.id, termId); }}
  />
{/if}

{#if typeModal && isAdmin}
  <FeeTypeModal editing={typeModal.editing} onClose={() => typeModal = null} />
{/if}

{#if structModal && termId && isAdmin}
  <FeeStructureModal
    editing={structModal.editing}
    {termId}
    termName={termName(termId)}
    {feeTypes}
    {classes}
    onClose={() => structModal = null}
  />
{/if}

<style>
  @reference "tailwindcss";
  .sel { @apply rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--fg)] focus:border-[var(--brand)] focus:outline-none transition; }
</style>
