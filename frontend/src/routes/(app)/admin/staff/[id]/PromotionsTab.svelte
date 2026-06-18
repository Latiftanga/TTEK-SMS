<script lang="ts">
  import { createQuery, createMutation, useQueryClient } from '@tanstack/svelte-query';
  import { listPromotions, addPromotion, type StaffDetail } from '$lib/api/staff';
  import EmptyState from '$lib/components/EmptyState.svelte';

  interface Props { staff: StaffDetail; staffId: string; }
  const { staffId }: Props = $props();

  const qc = useQueryClient();

  const promotionsQuery = createQuery({
    queryKey: ['staff', staffId, 'promotions'],
    queryFn: () => listPromotions(staffId),
  });

  const TEACHING_GRADES = [
    'Superintendent I',
    'Superintendent II',
    'Senior Superintendent II',
    'Senior Superintendent I',
    'Principal Superintendent',
    'Assistant Director II',
    'Assistant Director I',
    'Deputy Director',
    'Director II',
    'Director I',
  ];

  const NON_TEACHING_GROUPS: Record<string, string[]> = {
    'Accounting':            ['Principal Accountant', 'Chief Accountant II', 'Deputy Chief Accountant I', 'Chief Accountant I'],
    'Internal Audit':        ['Principal Internal Auditor', 'Deputy Chief Internal Auditor II', 'Deputy Chief Internal Auditor I', 'Chief Internal Auditor II'],
    'Administration':        ['Principal Administration Officer', 'Deputy Chief Administrative Officer II', 'Deputy Chief Administrative Officer I', 'Chief Administrative Officer II'],
    'Catering':              ['Principal Domestic Bursar', 'Deputy Chief Domestic Bursar', 'Chief Domestic Bursar'],
    'Technical':             ['Principal Chief Technical Officer', 'Deputy Chief Technical Officer', 'Chief Technical Officer'],
    'Supply':                ['Principal Supply Officer', 'Deputy Chief Supply Officer', 'Chief Supply Officer'],
    'Laboratory Technician': ['Principal Laboratory Technician', 'Deputy Chief Laboratory Technician', 'Chief Laboratory Technician'],
    'Secretarial':           ['Private Secretary', 'Senior Private Secretary', 'Principal Private Secretary'],
    'Driver':                ['Principal Driver', 'Chief Driver', 'Yard Foreman'],
  };

  let showForm = $state(false);
  let category = $state<'TEACHING' | 'NON_TEACHING'>('TEACHING');
  let group    = $state('');
  let fromGrade = $state('');
  let toGrade   = $state('');
  let effDate   = $state('');
  let reason    = $state('');
  let formError = $state('');

  const gradeList = $derived(
    category === 'TEACHING'
      ? TEACHING_GRADES
      : group ? (NON_TEACHING_GROUPS[group] ?? []) : []
  );

  function resetForm() {
    category = 'TEACHING'; group = ''; fromGrade = ''; toGrade = ''; effDate = ''; reason = ''; formError = '';
  }

  const addMut = createMutation({
    mutationFn: () => addPromotion(staffId, {
      staff_category: category,
      non_teaching_group: category === 'NON_TEACHING' ? group : undefined,
      from_grade: fromGrade || undefined,
      to_grade: toGrade,
      effective_date: effDate,
      reason: reason || undefined,
    }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['staff', staffId, 'promotions'] });
      showForm = false;
      resetForm();
    },
    onError: (e: unknown) => {
      formError = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? 'Failed.';
    },
  });

  function fmtDate(d: string) {
    return new Date(d).toLocaleDateString('en-GH', { day: 'numeric', month: 'short', year: 'numeric' });
  }

  const CATEGORY_LABEL: Record<string, string> = {
    TEACHING: 'Teaching',
    NON_TEACHING: 'Non-Teaching',
  };
</script>

<div class="space-y-4">
  <div class="flex justify-end">
    <button onclick={() => { showForm = !showForm; resetForm(); }}
      class="flex items-center gap-2 rounded-xl px-4 py-2 text-sm font-semibold text-white transition hover:opacity-90"
      style="background-color: var(--brand)">
      <svg class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" d="M12 4v16m8-8H4"/>
      </svg>
      Record promotion
    </button>
  </div>

  {#if showForm}
    <div class="rounded-xl border border-[var(--border)] bg-[var(--card)] p-5">
      <div class="grid gap-4 sm:grid-cols-2">

        <!-- Category -->
        <div class="sm:col-span-2">
          <label class="mb-1 block text-xs font-medium text-[var(--fg-muted)]">Staff category *</label>
          <div class="flex gap-3">
            {#each [['TEACHING','Teaching Staff'], ['NON_TEACHING','Non-Teaching Staff']] as [val, label]}
              <label class="flex cursor-pointer items-center gap-2">
                <input type="radio" bind:group={category} value={val}
                  onchange={() => { group = ''; fromGrade = ''; toGrade = ''; }}
                  class="accent-[var(--brand)]" />
                <span class="text-sm text-[var(--fg)]">{label}</span>
              </label>
            {/each}
          </div>
        </div>

        <!-- Group (non-teaching only) -->
        {#if category === 'NON_TEACHING'}
          <div class="sm:col-span-2">
            <label class="mb-1 block text-xs font-medium text-[var(--fg-muted)]">Cadre / Group *</label>
            <select bind:value={group} onchange={() => { fromGrade = ''; toGrade = ''; }}
              class="w-full rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--fg)] focus:border-[var(--brand)] focus:outline-none">
              <option value="">Select cadre…</option>
              {#each Object.keys(NON_TEACHING_GROUPS) as g}
                <option value={g}>{g}</option>
              {/each}
            </select>
          </div>
        {/if}

        <!-- From grade -->
        <div>
          <label class="mb-1 block text-xs font-medium text-[var(--fg-muted)]">From grade (leave blank for first entry)</label>
          <select bind:value={fromGrade}
            class="w-full rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--fg)] focus:border-[var(--brand)] focus:outline-none"
            disabled={gradeList.length === 0}>
            <option value="">— none —</option>
            {#each gradeList as g}
              <option value={g}>{g}</option>
            {/each}
          </select>
        </div>

        <!-- To grade -->
        <div>
          <label class="mb-1 block text-xs font-medium text-[var(--fg-muted)]">To grade *</label>
          <select bind:value={toGrade}
            class="w-full rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--fg)] focus:border-[var(--brand)] focus:outline-none"
            disabled={gradeList.length === 0}>
            <option value="">Select grade…</option>
            {#each gradeList as g}
              <option value={g}>{g}</option>
            {/each}
          </select>
        </div>

        <!-- Date -->
        <div>
          <label class="mb-1 block text-xs font-medium text-[var(--fg-muted)]">Effective date *</label>
          <input type="date" bind:value={effDate}
            class="w-full rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--fg)] focus:border-[var(--brand)] focus:outline-none" />
        </div>

        <!-- Reason -->
        <div>
          <label class="mb-1 block text-xs font-medium text-[var(--fg-muted)]">Letter / reference (optional)</label>
          <input type="text" bind:value={reason} placeholder="e.g. GES/HQ/PROMO/2024/001"
            class="w-full rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--fg)] placeholder:text-[var(--fg-muted)] focus:border-[var(--brand)] focus:outline-none" />
        </div>
      </div>

      {#if formError}<p class="mt-2 text-xs text-red-500">{formError}</p>{/if}

      <div class="mt-4 flex gap-2">
        <button
          onclick={() => $addMut.mutate()}
          disabled={$addMut.isPending || !toGrade || !effDate || (category === 'NON_TEACHING' && !group)}
          class="rounded-xl px-4 py-2 text-sm font-semibold text-white transition hover:opacity-90 disabled:opacity-50"
          style="background-color: var(--brand)">
          {$addMut.isPending ? 'Saving…' : 'Record promotion'}
        </button>
        <button onclick={() => { showForm = false; resetForm(); }}
          class="rounded-xl border border-[var(--border)] px-4 py-2 text-sm font-medium text-[var(--fg-muted)] transition hover:bg-[var(--hover)]">
          Cancel
        </button>
      </div>
    </div>
  {/if}

  {#if $promotionsQuery.isPending}
    <div class="skeleton h-24"></div>
  {:else if ($promotionsQuery.data ?? []).length === 0}
    <EmptyState
      iconPath="M2.25 18L9 11.25l4.306 4.307a11.95 11.95 0 015.814-5.519l2.74-1.22m0 0l-5.94-2.28m5.94 2.28l-2.28 5.941"
      title="No promotions recorded yet."
      description="Record GES grade promotions for this staff member."
      action={() => { showForm = true; resetForm(); }}
      actionLabel="Record promotion"
    />
  {:else}
    <div class="overflow-hidden rounded-xl border border-[var(--border)] bg-[var(--card)]">
      {#each $promotionsQuery.data ?? [] as p, i (p.id)}
        <div class="flex items-start gap-4 px-5 py-4 {i > 0 ? 'border-t border-[var(--border)]' : ''}">
          <div class="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-[var(--brand-dim)]">
            <svg class="h-5 w-5 text-[var(--brand)]" fill="none" stroke="currentColor" stroke-width="1.75" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" d="M2.25 18L9 11.25l4.306 4.307a11.95 11.95 0 015.814-5.519l2.74-1.22m0 0l-5.94-2.28m5.94 2.28l-2.28 5.941"/>
            </svg>
          </div>
          <div class="min-w-0 flex-1">
            <div class="flex flex-wrap items-center gap-2">
              {#if p.from_grade}
                <span class="text-sm text-[var(--fg-muted)]">{p.from_grade}</span>
                <svg class="h-4 w-4 shrink-0 text-[var(--fg-muted)]" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M13.5 4.5L21 12m0 0l-7.5 7.5M21 12H3"/>
                </svg>
              {/if}
              <span class="font-semibold text-[var(--fg)]">{p.to_grade}</span>
            </div>
            <p class="mt-0.5 text-xs text-[var(--fg-muted)]">
              {CATEGORY_LABEL[p.staff_category] ?? p.staff_category}{p.non_teaching_group ? ' · ' + p.non_teaching_group : ''}
              · {fmtDate(p.effective_date)}
              {#if p.reason}<span> · {p.reason}</span>{/if}
            </p>
          </div>
        </div>
      {/each}
    </div>
  {/if}
</div>
