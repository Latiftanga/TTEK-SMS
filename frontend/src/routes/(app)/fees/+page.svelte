<script lang="ts">
  import { createQuery } from '@tanstack/svelte-query';
  import { writable } from 'svelte/store';
  import { listAllTerms, type AcademicTerm } from '$lib/api/academic';
  import { listStudents, type StudentSummary } from '$lib/api/students';
  import {
    listStudentFeeRecords, getFeeSummary, listPayments,
    ghs, PAYMENT_METHOD_LABELS,
    type FeeRecord, type FeePayment, type FeeSummary,
  } from '$lib/api/fees';
  import PaymentModal from './PaymentModal.svelte';

  const termsQ = createQuery({ queryKey: ['all-terms'], queryFn: listAllTerms, staleTime: 5 * 60_000 });
  const terms  = $derived<AcademicTerm[]>([...($termsQ.data ?? [])].sort((a, b) => b.start_date.localeCompare(a.start_date)));
  let termId = $state('');
  $effect(() => {
    if (!termId && terms.length) termId = terms.find(t => t.is_current)?.id ?? terms[0]?.id ?? '';
  });

  // Student search
  let searchText = $state('');
  let showResults = $state(false);
  const searchOpts = writable({ queryKey: ['student-search', ''] as const, queryFn: () => listStudents({ search: '', limit: 8, active_only: true }), enabled: false });
  $effect(() => {
    const q = searchText.trim();
    searchOpts.set({ queryKey: ['student-search', q] as const, queryFn: () => listStudents({ search: q, limit: 8, active_only: true }), enabled: q.length >= 2 });
    showResults = q.length >= 2;
  });
  const searchQ = createQuery(searchOpts);
  const searchResults = $derived<StudentSummary[]>($searchQ.data ?? []);

  // Selected student + fee data
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
    } finally {
      loading = false;
    }
  }

  $effect(() => {
    if (selected && termId) loadFeeData(selected.id, termId);
  });

  function pick(s: StudentSummary) {
    selected = s; searchText = ''; showResults = false;
  }

  // Per-record paid amounts
  const paidByRecord = $derived.by(() => {
    const m = new Map<string, number>();
    for (const p of payments) {
      m.set(p.fee_record_id, (m.get(p.fee_record_id) ?? 0) + parseFloat(p.amount_paid));
    }
    return m;
  });

  // Payment modal
  let payRecord = $state<FeeRecord | null>(null);
  function remainingFor(r: FeeRecord) {
    return Math.max(0, parseFloat(r.amount_due) - (paidByRecord.get(r.id) ?? 0));
  }

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

  <!-- Student search -->
  <div class="relative">
    <div class="flex items-center gap-2 rounded-2xl border border-[var(--border)] bg-[var(--card)] px-4 py-3">
      <svg class="h-4 w-4 shrink-0 text-[var(--fg-muted)]" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><circle cx="11" cy="11" r="8"/><path stroke-linecap="round" stroke-linejoin="round" d="M21 21l-4.35-4.35"/></svg>
      <input bind:value={searchText} onfocus={() => { if (searchText.length >= 2) showResults = true; }}
        placeholder="Search student by name or admission number…"
        class="min-w-0 flex-1 bg-transparent text-sm text-[var(--fg)] placeholder:text-[var(--fg-subtle)] focus:outline-none" />
      {#if selected}
        <button onclick={() => { selected = null; records = []; payments = []; summary = null; searchText = ''; }}
          class="shrink-0 text-xs text-[var(--fg-muted)] transition hover:text-[var(--fg)]">
          Clear ✕
        </button>
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
    <!-- Student header -->
    <div class="rounded-2xl border border-[var(--border)] bg-[var(--card)] p-5">
      <div class="flex items-center gap-3">
        <div class="flex h-10 w-10 shrink-0 items-center justify-center rounded-full text-sm font-bold text-white" style="background: var(--brand)">{initials(selected)}</div>
        <div>
          <p class="font-semibold text-[var(--fg)]">{selected.display_name}</p>
          <p class="text-xs text-[var(--fg-muted)]">{selected.admission_number}{selected.current_class_name ? ' · ' + selected.current_class_name : ''}</p>
        </div>
      </div>

      {#if loading}
        <div class="mt-4 grid grid-cols-3 gap-3">
          {#each [0,1,2] as _}<div class="h-14 animate-pulse rounded-xl bg-[var(--hover)]"></div>{/each}
        </div>
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

    <!-- Fee records -->
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

    <!-- Payment history -->
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
</div>

{#if payRecord && selected}
  <PaymentModal
    record={payRecord}
    studentId={selected.id}
    termId={termId}
    remainingBalance={remainingFor(payRecord)}
    onClose={() => payRecord = null}
    onSuccess={() => { payRecord = null; loadFeeData(selected!.id, termId); }}
  />
{/if}

<style>
  @reference "tailwindcss";
  .sel { @apply rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--fg)] focus:border-[var(--brand)] focus:outline-none transition; }
</style>
