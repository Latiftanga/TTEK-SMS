<script lang="ts">
  import { createQuery } from '@tanstack/svelte-query';
  import { listSmsLogs, type SmsLog, type SmsProvider } from '$lib/api/sms';

  const SMS_PROVIDER_LABELS: Record<SmsProvider, string> = {
    AFRICAS_TALKING: "AT",
    HUBTEL:          "Hubtel",
    ARKESEL:         "Arkesel",
    WIGAL:           "WiGal",
    TWILIO:          "Twilio",
  };

  const ENTITY_LABELS: Record<string, string> = {
    fee_payment:        'Fee payment',
    attendance:         'Absence alert',
    report_published:   'Report card',
    manual:             'Manual send',
  };

  type Filter = 'ALL' | 'SENT' | 'FAILED';
  let filter = $state<Filter>('ALL');
  let expanded = $state<Set<string>>(new Set());

  const logsQ = createQuery({
    queryKey: ['sms-logs'],
    queryFn: () => listSmsLogs(100, 0),
    staleTime: 60_000,
  });

  const logs = $derived<SmsLog[]>($logsQ.data ?? []);
  const filtered = $derived(filter === 'ALL' ? logs : logs.filter(l => l.status === filter));

  const sentCount   = $derived(logs.filter(l => l.status === 'SENT').length);
  const failedCount = $derived(logs.filter(l => l.status === 'FAILED').length);

  function toggleExpand(id: string) {
    const next = new Set(expanded);
    next.has(id) ? next.delete(id) : next.add(id);
    expanded = next;
  }

  function fmt(iso: string) {
    const d = new Date(iso);
    return d.toLocaleDateString('en-GB', { day: '2-digit', month: 'short' }) + ' ' +
           d.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' });
  }
</script>

<div class="mt-8">
  <div class="mb-3 flex items-center justify-between">
    <p class="text-sm font-semibold text-[var(--fg)]">Recent activity</p>
    <div class="flex gap-1">
      {#each ([['ALL', 'All'], ['SENT', 'Sent'], ['FAILED', 'Failed']] as [Filter, string][]) as [f, label]}
        <button onclick={() => filter = f}
          class="rounded-lg px-3 py-1 text-xs font-medium transition
                 {filter === f ? 'bg-[var(--brand)] text-white' : 'border border-[var(--border)] text-[var(--fg-muted)] hover:bg-[var(--hover)]'}">
          {label}
          {#if f === 'SENT' && sentCount}{' '}{sentCount}{/if}
          {#if f === 'FAILED' && failedCount}
            <span class="ml-1 rounded-full bg-red-500/20 px-1 text-red-600 dark:text-red-400">{failedCount}</span>
          {/if}
        </button>
      {/each}
    </div>
  </div>

  {#if $logsQ.isPending}
    <div class="space-y-2">
      {#each [0,1,2,4,5] as _}
        <div class="h-10 animate-pulse rounded-lg bg-[var(--hover)]"></div>
      {/each}
    </div>

  {:else if logs.length === 0}
    <div class="rounded-xl border border-dashed border-[var(--border)] py-8 text-center">
      <p class="text-sm text-[var(--fg-muted)]">No messages sent yet. SMS notifications fire automatically on fee receipts, absences, and report publishing.</p>
    </div>

  {:else if filtered.length === 0}
    <p class="text-sm text-[var(--fg-muted)]">No {filter.toLowerCase()} messages in the last 100 entries.</p>

  {:else}
    <div class="overflow-hidden rounded-xl border border-[var(--border)] bg-[var(--card)]">
      <div class="divide-y divide-[var(--border)]">
        {#each filtered as log (log.id)}
          <div class="px-4 py-3">
            <div class="flex items-start gap-3">
              <!-- Status dot -->
              <span class="mt-0.5 h-2 w-2 shrink-0 rounded-full {log.status === 'SENT' ? 'bg-green-500' : 'bg-red-500'}"></span>

              <div class="min-w-0 flex-1">
                <!-- Row 1: time + event + provider + recipient -->
                <div class="flex flex-wrap items-center gap-x-2 gap-y-0.5 text-xs">
                  <span class="tabular-nums text-[var(--fg-subtle)]">{fmt(log.sent_at)}</span>
                  {#if log.entity_type}
                    <span class="rounded bg-[var(--hover)] px-1.5 py-0.5 font-medium text-[var(--fg-muted)]">
                      {ENTITY_LABELS[log.entity_type] ?? log.entity_type}
                    </span>
                  {/if}
                  <span class="rounded bg-[var(--hover)] px-1.5 py-0.5 font-mono text-[var(--fg-muted)]">
                    {SMS_PROVIDER_LABELS[log.provider] ?? log.provider}
                  </span>
                  <span class="font-medium text-[var(--fg)]">{log.recipient}</span>
                </div>

                <!-- Row 2: message preview -->
                <p class="mt-0.5 truncate text-xs text-[var(--fg-muted)]">{log.message}</p>

                <!-- Error detail (expandable) -->
                {#if log.status === 'FAILED' && log.error_message}
                  <button onclick={() => toggleExpand(log.id)}
                    class="mt-1 text-[10px] font-medium text-red-500 transition hover:underline">
                    {expanded.has(log.id) ? '▲ Hide error' : '▼ Show error'}
                  </button>
                  {#if expanded.has(log.id)}
                    <p class="mt-1 rounded-lg bg-red-50 px-3 py-2 text-[10px] font-mono text-red-700 dark:bg-red-950/30 dark:text-red-300">
                      {log.error_message}
                    </p>
                  {/if}
                {/if}
              </div>

              <!-- Status badge -->
              {#if log.status === 'SENT'}
                <span class="shrink-0 text-[10px] font-semibold text-green-600 dark:text-green-400">Sent</span>
              {:else}
                <span class="shrink-0 text-[10px] font-semibold text-red-500">Failed</span>
              {/if}
            </div>
          </div>
        {/each}
      </div>
      {#if logs.length >= 100}
        <div class="border-t border-[var(--border)] px-4 py-3 text-center text-xs text-[var(--fg-muted)]">
          Showing most recent 100 entries.
        </div>
      {/if}
    </div>
  {/if}
</div>
