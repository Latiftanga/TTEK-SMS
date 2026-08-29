<script lang="ts">
  import { createQuery, createMutation, useQueryClient } from '@tanstack/svelte-query';
  import { listPendingExcuseRequests, reviewExcuseRequest } from '$lib/api/attendance';
  import { detailOf, isLocked } from '$lib/apiError';
  import { toast } from '$lib/stores/toast';
  import { setPageTitle } from '$lib/stores/title';
  import OverrideReasonModal from '$lib/components/OverrideReasonModal.svelte';

  setPageTitle('Excuse Requests');

  const qc = useQueryClient();
  const requestsQ = createQuery({ queryKey: ['pending-excuse-requests'], queryFn: listPendingExcuseRequests });

  let overrideFor  = $state<{ id: string; status: 'APPROVED' | 'REJECTED' } | null>(null);
  let overrideError = $state('');

  const reviewMut = createMutation({
    mutationFn: ({ id, status, override_reason }: { id: string; status: 'APPROVED' | 'REJECTED'; override_reason?: string }) =>
      reviewExcuseRequest(id, { status, override_reason }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['pending-excuse-requests'] });
      qc.invalidateQueries({ queryKey: ['att-records'] });
      qc.invalidateQueries({ queryKey: ['att-summaries'] });
      overrideFor = null; overrideError = '';
      toast.success('Excuse request reviewed.');
    },
    onError: (e: unknown, vars) => {
      if (isLocked(e)) { overrideFor = { id: vars.id, status: vars.status }; overrideError = detailOf(e) ?? 'This term is locked.'; return; }
      toast.error(detailOf(e) ?? 'Could not review this request.');
    },
  });

  function review(id: string, status: 'APPROVED' | 'REJECTED') {
    $reviewMut.mutate({ id, status });
  }

  function fmt(d: string) {
    return new Date(d).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' });
  }
</script>

<div class="mx-auto max-w-3xl px-4 py-6">
  <p class="mb-4 text-xs text-[var(--fg-muted)]">
    Pending absence excuse requests submitted by guardians or students. Approving marks every school day in the
    range Excused; rejecting makes no attendance change.
  </p>

  {#if $requestsQ.isPending}
    <div class="space-y-2">{#each [1,2] as _}<div class="h-24 animate-pulse rounded-2xl bg-[var(--card)]"></div>{/each}</div>
  {:else if ($requestsQ.data ?? []).length === 0}
    <div class="rounded-2xl border border-dashed border-[var(--border)] p-10 text-center text-sm text-[var(--fg-muted)]">
      No pending excuse requests.
    </div>
  {:else}
    <div class="space-y-3">
      {#each $requestsQ.data ?? [] as r (r.id)}
        {@const isPending = $reviewMut.isPending && ($reviewMut.variables as { id: string })?.id === r.id}
        <div class="rounded-2xl border border-[var(--border)] bg-[var(--card)] p-5">
          <div class="flex items-start justify-between gap-3">
            <div>
              <p class="text-sm font-semibold text-[var(--fg)]">{r.student_name ?? 'Student'}</p>
              <p class="text-xs text-[var(--fg-muted)]">{fmt(r.start_date)} – {fmt(r.end_date)}</p>
            </div>
          </div>
          <p class="mt-2 text-sm text-[var(--fg)]">{r.reason}</p>
          <div class="mt-3 flex flex-wrap gap-2">
            <button onclick={() => review(r.id, 'APPROVED')} disabled={isPending}
              class="min-h-[44px] rounded-xl bg-emerald-600 px-3 py-1.5 text-xs font-semibold text-white transition hover:opacity-90 disabled:opacity-50">
              Approve
            </button>
            <button onclick={() => review(r.id, 'REJECTED')} disabled={isPending}
              class="min-h-[44px] rounded-xl border border-red-300 px-3 py-1.5 text-xs font-semibold text-red-600 transition hover:bg-red-50 disabled:opacity-50 dark:border-red-800 dark:hover:bg-red-950/20">
              Reject
            </button>
          </div>
        </div>
      {/each}
    </div>
  {/if}
</div>

<OverrideReasonModal
  open={!!overrideFor}
  message="One or more days in this range fall in a locked term. Supply a reason to override — it is written to the audit log."
  errorMessage={overrideError}
  isPending={$reviewMut.isPending}
  onSubmit={(reason) => overrideFor && $reviewMut.mutate({ id: overrideFor.id, status: overrideFor.status, override_reason: reason })}
  onCancel={() => { overrideFor = null; overrideError = ''; }}
/>
