<script lang="ts">
  import { createQuery, createMutation, useQueryClient } from '@tanstack/svelte-query';
  import { reactiveQuery } from '$lib/query.svelte';
  import { submitExcuseRequest, listMyExcuseRequests, type ExcuseRequest } from '$lib/api/portal';
  import { toast } from '$lib/stores/toast';
  import { apiError } from '$lib/utils';

  interface Props { studentId?: string; }
  const { studentId }: Props = $props();

  const qc = useQueryClient();
  const requestsQ = reactiveQuery(() => ({
    queryKey: ['portal-excuse-requests', studentId ?? 'self'] as const,
    queryFn:  () => listMyExcuseRequests(studentId),
    staleTime: 30_000,
  }));

  let formOpen  = $state(false);
  let startDate = $state('');
  let endDate   = $state('');
  let reason    = $state('');
  let formError = $state('');

  function resetForm() { startDate = ''; endDate = ''; reason = ''; formError = ''; }

  const submitMut = createMutation({
    mutationFn: () => submitExcuseRequest({ start_date: startDate, end_date: endDate, reason }, studentId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['portal-excuse-requests'] });
      toast.success('Excuse request submitted — the school will review it.');
      formOpen = false;
      resetForm();
    },
    onError: (e: unknown) => { formError = apiError(e, 'Could not submit this request.'); },
  });

  function submit() {
    formError = '';
    if (!startDate || !endDate || !reason.trim()) {
      formError = 'Date range and reason are required.';
      return;
    }
    if (endDate < startDate) {
      formError = 'End date must be on or after the start date.';
      return;
    }
    $submitMut.mutate();
  }

  const STATUS_COLOR: Record<string, string> = {
    PENDING:  'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400',
    APPROVED: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400',
    REJECTED: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400',
  };

  function fmt(d: string) {
    return new Date(d).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' });
  }
</script>

<div class="mt-6">
  <div class="mb-3 flex items-center justify-between">
    <h2 class="text-xs font-semibold uppercase tracking-widest text-[var(--fg-subtle)]">Absence excuse requests</h2>
    <button onclick={() => { formOpen = !formOpen; if (!formOpen) resetForm(); }}
      class="min-h-[44px] rounded-xl border border-[var(--border)] px-3 py-1.5 text-xs font-semibold text-[var(--fg)] transition hover:bg-[var(--hover)]">
      {formOpen ? 'Cancel' : '+ Report an absence'}
    </button>
  </div>

  {#if formOpen}
    <div class="mb-4 rounded-2xl border border-[var(--border)] bg-[var(--card)] p-5">
      <div class="grid grid-cols-2 gap-3">
        <div>
          <label for="excuse-start" class="mb-1 block text-xs font-medium text-[var(--fg-muted)]">From</label>
          <input id="excuse-start" type="date" bind:value={startDate}
            class="min-h-[44px] w-full rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--fg)] focus:border-[var(--brand)] focus:outline-none" />
        </div>
        <div>
          <label for="excuse-end" class="mb-1 block text-xs font-medium text-[var(--fg-muted)]">To</label>
          <input id="excuse-end" type="date" bind:value={endDate}
            class="min-h-[44px] w-full rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--fg)] focus:border-[var(--brand)] focus:outline-none" />
        </div>
      </div>
      <div class="mt-3">
        <label for="excuse-reason" class="mb-1 block text-xs font-medium text-[var(--fg-muted)]">Reason</label>
        <textarea id="excuse-reason" rows="3" bind:value={reason} placeholder="e.g. Fever, saw a doctor on Monday"
          class="w-full rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--fg)] focus:border-[var(--brand)] focus:outline-none"></textarea>
      </div>
      {#if formError}<p class="mt-2 text-xs text-red-500">{formError}</p>{/if}
      <button onclick={submit} disabled={$submitMut.isPending}
        class="mt-3 min-h-[44px] w-full rounded-xl py-2 text-sm font-semibold text-white transition hover:opacity-90 disabled:opacity-50"
        style="background: var(--brand)">
        {$submitMut.isPending ? 'Submitting…' : 'Submit request'}
      </button>
    </div>
  {/if}

  {#if $requestsQ.isPending}
    <div class="h-16 animate-pulse rounded-2xl bg-[var(--card)]"></div>
  {:else if ($requestsQ.data ?? []).length === 0}
    <p class="rounded-2xl border border-dashed border-[var(--border)] p-4 text-center text-xs text-[var(--fg-muted)]">
      No excuse requests yet.
    </p>
  {:else}
    <div class="space-y-2">
      {#each $requestsQ.data ?? [] as r (r.id)}
        <div class="rounded-2xl border border-[var(--border)] bg-[var(--card)] px-4 py-3">
          <div class="flex items-center justify-between gap-2">
            <p class="text-sm font-medium text-[var(--fg)]">{fmt(r.start_date)} – {fmt(r.end_date)}</p>
            <span class="rounded-full px-2 py-0.5 text-[10px] font-semibold {STATUS_COLOR[r.status]}">{r.status}</span>
          </div>
          <p class="mt-1 text-xs text-[var(--fg-muted)]">{r.reason}</p>
          {#if r.review_notes}
            <p class="mt-1 text-xs italic text-[var(--fg-subtle)]">"{r.review_notes}"</p>
          {/if}
        </div>
      {/each}
    </div>
  {/if}
</div>
