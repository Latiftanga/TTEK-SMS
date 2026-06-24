<script lang="ts">
  import type { ExeatRead } from '$lib/api/housing';

  interface Props {
    dotColor: string;
    heading: string;
    pending: ExeatRead[];
    approved: ExeatRead[];
    approvedLabel: string;
    destinationHeader: string;
    onApprove: (id: string) => void;
    onReject: (id: string) => void;
    onReturn: (id: string) => void;
    actionPending?: boolean;
  }

  const {
    dotColor, heading, pending, approved, approvedLabel,
    destinationHeader, onApprove, onReject, onReturn, actionPending = false,
  }: Props = $props();
</script>

<section class="mb-8">
  <p class="mb-3 flex items-center gap-2 text-xs font-semibold uppercase tracking-widest text-[var(--fg-subtle)]">
    <span class="inline-block h-2 w-2 rounded-full {dotColor}"></span>
    {heading}
  </p>

  {#if pending.length > 0}
    <div class="mb-3 overflow-hidden rounded-2xl border border-[var(--border)] bg-[var(--card)]">
      <p class="border-b border-[var(--border)] px-4 py-2 text-xs font-semibold text-amber-600 dark:text-amber-400">
        Pending approval ({pending.length})
      </p>
      <table class="w-full text-sm">
        <thead><tr class="border-b border-[var(--border)] text-left text-[10px] font-semibold uppercase tracking-widest text-[var(--fg-subtle)]">
          <th class="px-4 py-3">Student</th>
          <th class="hidden px-4 py-3 sm:table-cell">Reason</th>
          <th class="hidden px-4 py-3 md:table-cell">{destinationHeader}</th>
          <th class="hidden px-4 py-3 md:table-cell">From</th>
          <th class="hidden px-4 py-3 md:table-cell">Until</th>
          <th class="px-4 py-3"></th>
        </tr></thead>
        <tbody>
          {#each pending as e (e.id)}
            <tr class="border-b border-[var(--border)] last:border-0">
              <td class="px-4 py-3">
                <p class="font-medium text-[var(--fg)]">{e.student_name ?? '—'}</p>
                <p class="text-[10px] text-[var(--fg-subtle)]">{e.admission_number ?? ''}</p>
              </td>
              <td class="hidden px-4 py-3 text-xs text-[var(--fg-muted)] sm:table-cell max-w-[160px] truncate">{e.reason}</td>
              <td class="hidden px-4 py-3 text-[var(--fg-muted)] md:table-cell">{e.destination}</td>
              <td class="hidden px-4 py-3 text-[var(--fg-muted)] md:table-cell">{e.departure_date}</td>
              <td class="hidden px-4 py-3 text-[var(--fg-muted)] md:table-cell">{e.return_date}</td>
              <td class="px-4 py-3">
                <div class="flex gap-2">
                  <button onclick={() => onApprove(e.id)} disabled={actionPending}
                    class="rounded-lg bg-green-50 px-2.5 py-1 text-xs font-semibold text-green-700 transition
                           hover:bg-green-100 dark:bg-green-950/40 dark:text-green-400 disabled:opacity-50">
                    Approve
                  </button>
                  <button onclick={() => onReject(e.id)} disabled={actionPending}
                    class="rounded-lg bg-red-50 px-2.5 py-1 text-xs font-semibold text-red-700 transition
                           hover:bg-red-100 dark:bg-red-950/40 dark:text-red-400 disabled:opacity-50">
                    Reject
                  </button>
                </div>
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  {/if}

  {#if approved.length > 0}
    <div class="overflow-hidden rounded-2xl border border-[var(--border)] bg-[var(--card)]">
      <p class="border-b border-[var(--border)] px-4 py-2 text-xs font-semibold text-blue-600 dark:text-blue-400">
        {approvedLabel} ({approved.length})
      </p>
      <table class="w-full text-sm">
        <thead><tr class="border-b border-[var(--border)] text-left text-[10px] font-semibold uppercase tracking-widest text-[var(--fg-subtle)]">
          <th class="px-4 py-3">Student</th>
          <th class="hidden px-4 py-3 sm:table-cell">{destinationHeader}</th>
          <th class="hidden px-4 py-3 sm:table-cell">From</th>
          <th class="px-4 py-3">Expected back</th>
          <th class="px-4 py-3"></th>
        </tr></thead>
        <tbody>
          {#each approved as e (e.id)}
            {@const overdue = e.return_date < new Date().toISOString().slice(0,10)}
            <tr class="border-b border-[var(--border)] last:border-0 {overdue ? 'bg-red-50/50 dark:bg-red-950/10' : ''}">
              <td class="px-4 py-3">
                <p class="font-medium text-[var(--fg)]">{e.student_name ?? '—'}</p>
                <p class="text-[10px] text-[var(--fg-subtle)]">{e.admission_number ?? ''}</p>
              </td>
              <td class="hidden px-4 py-3 text-[var(--fg-muted)] sm:table-cell">{e.destination}</td>
              <td class="hidden px-4 py-3 text-[var(--fg-muted)] sm:table-cell">{e.departure_date}</td>
              <td class="px-4 py-3 font-medium {overdue ? 'text-red-600 dark:text-red-400' : 'text-[var(--fg)]'}">
                {e.return_date}{#if overdue} <span class="text-[10px] font-bold">OVERDUE</span>{/if}
              </td>
              <td class="px-4 py-3 text-right">
                <button onclick={() => onReturn(e.id)}
                  class="rounded-lg border border-[var(--border)] px-2.5 py-1 text-xs font-semibold
                         text-[var(--fg)] hover:bg-[var(--hover)] transition">
                  Record return
                </button>
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  {/if}

  {#if pending.length === 0 && approved.length === 0}
    <div class="rounded-2xl border border-dashed border-[var(--border)] p-6 text-center">
      <p class="text-sm text-[var(--fg-muted)]">No active {heading.toLowerCase()}.</p>
    </div>
  {/if}
</section>
