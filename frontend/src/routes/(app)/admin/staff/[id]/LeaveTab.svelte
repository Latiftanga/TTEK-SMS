<script lang="ts">
  import { createQuery, createMutation, useQueryClient } from '@tanstack/svelte-query';
  import { listLeave, submitLeave } from '$lib/api/staff';
  import Badge from '$lib/components/Badge.svelte';
  import EmptyState from '$lib/components/EmptyState.svelte';

  interface Props { staffId: string; }
  const { staffId }: Props = $props();

  const qc = useQueryClient();

  const leaveQ = createQuery({
    queryKey: ['staff-leave', staffId],
    queryFn:  () => listLeave(staffId),
    staleTime: 60_000,
  });

  const LEAVE_TYPES = ['Annual', 'Sick', 'Maternity', 'Paternity', 'Study', 'Emergency', 'Unpaid'];

  type BadgeColor = 'amber' | 'green' | 'red' | 'gray';
  const STATUS_COLOR: Record<string, BadgeColor> = {
    PENDING: 'amber', APPROVED: 'green', REJECTED: 'red', CANCELLED: 'gray',
  };
  const STATUS_LABEL: Record<string, string> = {
    PENDING: 'Pending', APPROVED: 'Approved', REJECTED: 'Rejected', CANCELLED: 'Cancelled',
  };

  let showForm  = $state(false);
  let form      = $state({ leave_type: '', start_date: '', end_date: '', reason: '' });
  let formError = $state('');

  // Auto-calculate days from date range
  const calcDays = $derived(() => {
    if (!form.start_date || !form.end_date) return 0;
    const diff = new Date(form.end_date).getTime() - new Date(form.start_date).getTime();
    return Math.max(0, Math.round(diff / 86_400_000) + 1);
  });

  const submitMut = createMutation({
    mutationFn: () => submitLeave(staffId, {
      leave_type:  form.leave_type,
      start_date:  form.start_date,
      end_date:    form.end_date,
      days_count:  calcDays(),
      reason:      form.reason || undefined,
    }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['staff-leave', staffId] });
      showForm = false;
      form = { leave_type: '', start_date: '', end_date: '', reason: '' };
      formError = '';
    },
    onError: (e: unknown) => {
      formError = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? 'Failed to submit leave.';
    },
  });

  function fmtDate(d: string) {
    return new Date(d).toLocaleDateString('en-GH', { day: 'numeric', month: 'short', year: 'numeric' });
  }
</script>

<div class="space-y-4">
  <div class="flex justify-end">
    <button onclick={() => { showForm = !showForm; formError = ''; }}
      class="flex items-center gap-2 rounded-xl px-4 py-2 text-sm font-semibold text-white transition hover:opacity-90"
      style="background-color: var(--brand)">
      <svg class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" d="M12 4v16m8-8H4"/>
      </svg>
      Submit leave request
    </button>
  </div>

  {#if showForm}
    <div class="rounded-xl border border-[var(--border)] bg-[var(--card)] p-5">
      <div class="grid gap-4 sm:grid-cols-2">
        <div class="sm:col-span-2">
          <label class="mb-1 block text-xs font-medium text-[var(--fg-muted)]">Leave type</label>
          <select bind:value={form.leave_type}
            class="h-10 w-full rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 text-sm text-[var(--fg)] focus:border-[var(--brand)] focus:outline-none">
            <option value="">Select…</option>
            {#each LEAVE_TYPES as lt}<option value={lt}>{lt}</option>{/each}
          </select>
        </div>
        <div>
          <label class="mb-1 block text-xs font-medium text-[var(--fg-muted)]">Start date</label>
          <input type="date" bind:value={form.start_date}
            class="w-full rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--fg)] focus:border-[var(--brand)] focus:outline-none" />
        </div>
        <div>
          <label class="mb-1 block text-xs font-medium text-[var(--fg-muted)]">End date</label>
          <input type="date" bind:value={form.end_date}
            class="w-full rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--fg)] focus:border-[var(--brand)] focus:outline-none" />
        </div>
        {#if calcDays() > 0}
          <div class="sm:col-span-2">
            <p class="text-xs text-[var(--fg-muted)]">
              Duration: <span class="font-semibold text-[var(--fg)]">{calcDays()} day{calcDays() !== 1 ? 's' : ''}</span>
            </p>
          </div>
        {/if}
        <div class="sm:col-span-2">
          <label class="mb-1 block text-xs font-medium text-[var(--fg-muted)]">Reason (optional)</label>
          <textarea bind:value={form.reason} rows="2" placeholder="Reason for leave…"
            class="w-full resize-none rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--fg)] placeholder:text-[var(--fg-muted)] focus:border-[var(--brand)] focus:outline-none">
          </textarea>
        </div>
      </div>
      {#if formError}<p class="mt-2 text-xs text-red-500">{formError}</p>{/if}
      <div class="mt-4 flex gap-2">
        <button onclick={() => $submitMut.mutate()} disabled={$submitMut.isPending || !form.leave_type || !form.start_date || !form.end_date}
          class="rounded-xl px-4 py-2 text-sm font-semibold text-white transition hover:opacity-90 disabled:opacity-50"
          style="background-color: var(--brand)">
          {$submitMut.isPending ? 'Submitting…' : 'Submit request'}
        </button>
        <button onclick={() => { showForm = false; formError = ''; }}
          class="rounded-xl border border-[var(--border)] px-4 py-2 text-sm font-medium text-[var(--fg-muted)] transition hover:bg-[var(--bg)]">
          Cancel
        </button>
      </div>
    </div>
  {/if}

  {#if $leaveQ.isPending}
    <div class="space-y-2">{#each [1,2,3] as _}<div class="skeleton h-14"></div>{/each}</div>
  {:else if ($leaveQ.data ?? []).length === 0}
    <EmptyState
      iconPath="M6.75 3v2.25M17.25 3v2.25M3 18.75V7.5a2.25 2.25 0 012.25-2.25h13.5A2.25 2.25 0 0121 7.5v11.25m-18 0A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75m-18 0v-7.5A2.25 2.25 0 015.25 9h13.5A2.25 2.25 0 0121 11.25v7.5"
      title="No leave requests on record."
      description="Submit a leave request using the button above."
    />
  {:else}
    <div class="overflow-hidden rounded-xl border border-[var(--border)] bg-[var(--card)]">
      <table class="w-full text-sm">
        <thead>
          <tr class="border-b border-[var(--border)] text-left">
            <th class="px-4 py-3 text-xs font-semibold uppercase tracking-widest text-[var(--fg-muted)]">Type</th>
            <th class="hidden px-4 py-3 text-xs font-semibold uppercase tracking-widest text-[var(--fg-muted)] sm:table-cell">Dates</th>
            <th class="px-4 py-3 text-xs font-semibold uppercase tracking-widest text-[var(--fg-muted)]">Days</th>
            <th class="px-4 py-3 text-xs font-semibold uppercase tracking-widest text-[var(--fg-muted)]">Status</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-[var(--border)]">
          {#each ($leaveQ.data ?? []) as l (l.id)}
            <tr class="transition hover:bg-[var(--hover)]">
              <td class="px-4 py-3 font-medium text-[var(--fg)]">{l.leave_type}</td>
              <td class="hidden px-4 py-3 text-[var(--fg-muted)] sm:table-cell">
                {fmtDate(l.start_date)} – {fmtDate(l.end_date)}
              </td>
              <td class="px-4 py-3 text-[var(--fg-muted)]">{l.days_count}</td>
              <td class="px-4 py-3">
                <Badge
                  label={STATUS_LABEL[l.status] ?? l.status}
                  color={STATUS_COLOR[l.status] ?? 'gray'}
                  variant="solid"
                />
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  {/if}
</div>
