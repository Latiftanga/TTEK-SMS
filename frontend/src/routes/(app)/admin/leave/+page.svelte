<script lang="ts">
  import { createQuery, createMutation, useQueryClient } from '@tanstack/svelte-query';
  import { listPendingLeave, reviewLeave, type Leave } from '$lib/api/staff';
  import { goto } from '$app/navigation';
  import { toast } from '$lib/stores/toast';
  import { setPageTitle } from '$lib/stores/title';

  const qc = useQueryClient();
  setPageTitle('Leave Requests');

  const leaveQ = createQuery({
    queryKey: ['pending-leave'],
    queryFn:  listPendingLeave,
    staleTime: 30_000,
  });

  const leaves = $derived<Leave[]>($leaveQ.data ?? []);

  // ── Review mutation ───────────────────────────────────────────────────────────
  let reviewing = $state<{ id: string; action: 'APPROVED' | 'REJECTED' } | null>(null);

  const reviewMut = createMutation({
    mutationFn: ({ id, action }: { id: string; action: 'APPROVED' | 'REJECTED' }) =>
      reviewLeave(id, { status: action }),
    onSuccess: (_, vars) => {
      qc.invalidateQueries({ queryKey: ['pending-leave'] });
      reviewing = null;
      const labels = { APPROVED: 'Leave approved.', REJECTED: 'Leave rejected.' };
      toast.success(labels[vars.action]);
    },
    onError: (e: unknown) => {
      reviewing = null;
      toast.error((e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? 'Could not process leave request.');
    },
  });

  function fmtDate(iso: string) {
    return new Date(iso).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' });
  }
</script>


<div class="space-y-6">
  <div class="flex items-center justify-between gap-3">
    <div>
      <h1 class="text-xl font-bold text-[var(--fg)]">Leave Requests</h1>
      <p class="mt-0.5 text-sm text-[var(--fg-muted)]">Staff leave requests awaiting review.</p>
    </div>
    {#if !$leaveQ.isPending && leaves.length > 0}
      <span class="rounded-full bg-amber-50 px-3 py-1 text-sm font-semibold text-amber-700 ring-1 ring-amber-200 dark:bg-amber-950/30 dark:text-amber-400 dark:ring-amber-800">
        {leaves.length} pending
      </span>
    {/if}
  </div>

  {#if $leaveQ.isPending}
    <div class="space-y-2">{#each [1,2,3] as _}<div class="h-20 animate-pulse rounded-2xl bg-[var(--card)]"></div>{/each}</div>

  {:else if leaves.length === 0}
    <div class="flex flex-col items-center justify-center rounded-2xl border border-dashed border-[var(--border)] px-6 py-16 text-center">
      <svg class="mb-3 h-10 w-10 text-[var(--fg-subtle)]" fill="none" stroke="currentColor" stroke-width="1.2" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/>
      </svg>
      <p class="text-sm font-medium text-[var(--fg-muted)]">No pending leave requests</p>
      <p class="mt-1 text-xs text-[var(--fg-subtle)]">Leave requests submitted from staff profiles will appear here.</p>
    </div>

  {:else}
    <div class="overflow-hidden rounded-2xl border border-[var(--border)] bg-[var(--card)]">
      <!-- Desktop header -->
      <div class="hidden grid-cols-[1fr_auto_auto_auto] gap-4 border-b border-[var(--border)] px-5 py-2.5 text-[10px] font-semibold uppercase tracking-widest text-[var(--fg-subtle)] sm:grid">
        <span>Staff</span><span>Dates</span><span>Reason</span><span></span>
      </div>

      {#each leaves as lv (lv.id)}
        <div class="border-b border-[var(--border)] last:border-0">
          <!-- Main row -->
          <div class="grid grid-cols-[1fr_auto] items-start gap-3 px-5 py-4 sm:grid-cols-[1fr_auto_auto_auto] sm:items-center sm:gap-4">
            <!-- Staff info -->
            <div>
              <button onclick={() => goto(`/admin/staff/${lv.staff_member_id}`)}
                class="text-sm font-semibold text-[var(--fg)] underline-offset-2 hover:underline hover:text-[var(--brand)] transition">
                {lv.staff_name ?? 'Unknown staff member'}
              </button>
              <p class="mt-0.5 font-mono text-[10px] text-[var(--fg-subtle)]">{lv.staff_number ?? lv.staff_member_id}</p>
              <p class="mt-0.5 text-xs text-[var(--fg-muted)]">{lv.leave_type} · {lv.days_count} day{lv.days_count !== 1 ? 's' : ''}</p>
            </div>

            <!-- Dates -->
            <p class="text-xs text-[var(--fg-muted)]">{fmtDate(lv.start_date)} – {fmtDate(lv.end_date)}</p>

            <!-- Reason -->
            <p class="hidden max-w-xs truncate text-xs text-[var(--fg-muted)] sm:block">
              {#if lv.reason}{lv.reason}{:else}<span class="text-[var(--fg-subtle)] italic">No reason given</span>{/if}
            </p>

            <!-- Actions -->
            {#if reviewing?.id === lv.id}
              <div class="flex items-center gap-2 rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2">
                <span class="text-xs text-[var(--fg-muted)]">
                  {reviewing.action === 'APPROVED' ? 'Approve this leave request?' : 'Reject this request?'}
                </span>
                <button onclick={() => $reviewMut.mutate({ id: lv.id, action: reviewing!.action })}
                  disabled={$reviewMut.isPending}
                  class="rounded-lg px-2.5 py-1 text-xs font-semibold text-white transition hover:opacity-90 disabled:opacity-50
                         {reviewing.action === 'APPROVED' ? 'bg-green-600 hover:bg-green-700' : 'bg-red-600 hover:bg-red-700'}">
                  {$reviewMut.isPending ? '…' : 'Yes'}
                </button>
                <button onclick={() => reviewing = null} class="text-xs text-[var(--fg-muted)] hover:text-[var(--fg)] transition">Cancel</button>
              </div>
            {:else}
              <div class="flex gap-1.5">
                <button onclick={() => reviewing = { id: lv.id, action: 'APPROVED' }}
                  class="rounded-lg border border-green-200 bg-green-50 px-2.5 py-1.5 text-xs font-semibold text-green-700 transition hover:border-green-400 dark:border-green-800 dark:bg-green-950/30 dark:text-green-400">
                  Approve
                </button>
                <button onclick={() => reviewing = { id: lv.id, action: 'REJECTED' }}
                  class="rounded-lg border border-[var(--border)] px-2.5 py-1.5 text-xs font-semibold text-[var(--fg-muted)] transition hover:border-red-300 hover:text-red-600 dark:hover:text-red-400">
                  Reject
                </button>
              </div>
            {/if}
          </div>

          <!-- Mobile reason row -->
          {#if lv.reason}
            <p class="border-t border-[var(--border)] px-5 py-2 text-xs text-[var(--fg-muted)] sm:hidden">
              Reason: {lv.reason}
            </p>
          {/if}
        </div>
      {/each}
    </div>

    <p class="text-xs text-[var(--fg-subtle)]">
      Approved and rejected requests are archived off this view.
    </p>
  {/if}
</div>
