<script lang="ts">
  import type { ApproverDashboard } from '$lib/api/dashboard';
  import StatCard from '$lib/components/StatCard.svelte';

  interface Props { data: ApproverDashboard; }
  const { data }: Props = $props();

  const hour = new Date().getHours();
  const salutation = hour < 12 ? 'Good morning' : hour < 17 ? 'Good afternoon' : 'Good evening';

  const approved   = $derived(() => Math.max(0, data.assessments_this_term - data.pending_approvals));
  const approvalPct = $derived(() => data.assessments_this_term > 0
    ? Math.round((approved() / data.assessments_this_term) * 100) : 0);
  const allClear = $derived(() => data.pending_approvals === 0);

  const C = 2 * Math.PI * 30;
</script>

<!-- Greeting — full width -->
<div class="mb-6">
  <h1 class="text-2xl font-bold text-[var(--fg)]">{salutation}, {data.greeting_name.split(' ')[0]}.</h1>
  <p class="mt-0.5 text-sm text-[var(--fg-muted)]">
    {#if allClear()}
      All score submissions are approved. You're up to date.
    {:else}
      {data.pending_approvals} score submission{data.pending_approvals === 1 ? '' : 's'} waiting for your review.
    {/if}
  </p>
</div>

<!-- Two-column on xl: left = stats + ring, right = actions -->
<div class="grid grid-cols-1 gap-5 xl:grid-cols-[3fr_2fr]">

  <!-- LEFT -->
  <div class="space-y-5">

    <div class="grid grid-cols-2 gap-3">
      <StatCard
        label="Pending Approvals" value={data.pending_approvals}
        icon="⏳" color="bg-amber-50 dark:bg-amber-950/40" iconColor="text-amber-600 dark:text-amber-400"
        href="/scores?filter=pending" alert={data.pending_approvals > 0}
      />
      <StatCard
        label="This Term" value={data.assessments_this_term}
        icon="📝" color="bg-blue-50 dark:bg-blue-950/40" iconColor="text-blue-600 dark:text-blue-400"
        href="/scores" trend={`${approved()} approved`}
      />
    </div>

    {#if data.assessments_this_term > 0}
      <div class="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
        <p class="mb-4 text-[11px] font-semibold uppercase tracking-widest text-[var(--fg-muted)]">Approval progress</p>
        <div class="flex items-center gap-6">
          <div class="relative flex-shrink-0">
            <svg class="w-20 h-20" viewBox="0 0 80 80">
              <circle cx="40" cy="40" r="30" fill="none" class="stroke-gray-100 dark:stroke-gray-800" stroke-width="6"/>
              <circle cx="40" cy="40" r="30" fill="none"
                stroke={allClear() ? '#22c55e' : approvalPct() < 50 ? '#f59e0b' : 'var(--brand)'}
                stroke-width="6" stroke-linecap="round"
                stroke-dasharray="{C}" stroke-dashoffset="{C * (1 - approvalPct() / 100)}"
                transform="rotate(-90 40 40)"
                style="transition: stroke-dashoffset 800ms cubic-bezier(0.4,0,0.2,1)"/>
            </svg>
            <div class="absolute inset-0 flex flex-col items-center justify-center">
              <span class="text-lg font-bold text-[var(--fg)]">{approvalPct()}%</span>
            </div>
          </div>
          <div class="flex-1 min-w-0 space-y-2">
            <div class="flex items-center justify-between text-sm">
              <span class="text-[var(--fg-muted)]">Approved</span>
              <span class="font-semibold text-green-600 dark:text-green-400">{approved()}</span>
            </div>
            <div class="flex items-center justify-between text-sm">
              <span class="text-[var(--fg-muted)]">Pending</span>
              <span class="font-semibold {data.pending_approvals > 0 ? 'text-amber-500' : 'text-[var(--fg-muted)]'}">
                {data.pending_approvals}
              </span>
            </div>
            <div class="flex items-center justify-between text-sm">
              <span class="text-[var(--fg-muted)]">Total</span>
              <span class="font-semibold text-[var(--fg)]">{data.assessments_this_term}</span>
            </div>
          </div>
        </div>
      </div>
    {/if}

  </div>

  <!-- RIGHT: actions -->
  <div>
    <p class="mb-2.5 text-[11px] font-semibold uppercase tracking-widest text-[var(--fg-muted)]">Actions</p>
    <div class="overflow-hidden rounded-xl border border-[var(--border)] bg-[var(--card)] divide-y divide-[var(--border)]">
      <a href="/scores?filter=pending" class="group flex items-center gap-4 px-5 py-4 transition hover:bg-[var(--bg)]">
        <div class="flex h-8 w-8 items-center justify-center rounded-lg
                    {data.pending_approvals > 0 ? 'bg-amber-100 dark:bg-amber-900/40' : 'bg-gray-100 dark:bg-gray-800'}">
          {#if data.pending_approvals > 0}
            <span class="h-2 w-2 rounded-full bg-amber-500 animate-pulse"></span>
          {:else}
            <svg class="h-4 w-4 text-gray-400" fill="none" stroke="currentColor" stroke-width="1.5" viewBox="0 0 24 24"><polyline points="20 6 9 17 4 12"/></svg>
          {/if}
        </div>
        <div class="flex-1">
          <p class="text-sm font-semibold text-[var(--fg)]">Approve Scores</p>
          <p class="text-[11px] {data.pending_approvals > 0 ? 'text-amber-600 dark:text-amber-400 font-medium' : 'text-[var(--fg-muted)]'}">
            {data.pending_approvals > 0 ? `${data.pending_approvals} waiting` : 'Nothing pending'}
          </p>
        </div>
        <svg class="h-4 w-4 text-gray-300 dark:text-gray-700 transition-transform group-hover:translate-x-0.5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><polyline points="9 18 15 12 9 6"/></svg>
      </a>
      <a href="/scores" class="group flex items-center gap-4 px-5 py-4 transition hover:bg-[var(--bg)]">
        <div class="flex h-8 w-8 items-center justify-center rounded-lg bg-gray-100 dark:bg-gray-800">
          <svg class="h-4 w-4 text-gray-400 dark:text-gray-500" fill="none" stroke="currentColor" stroke-width="1.5" viewBox="0 0 24 24">
            <line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/>
          </svg>
        </div>
        <div class="flex-1">
          <p class="text-sm font-semibold text-[var(--fg)]">All Assessments</p>
          <p class="text-[11px] text-[var(--fg-muted)]">Browse & manage</p>
        </div>
        <svg class="h-4 w-4 text-gray-300 dark:text-gray-700 transition-transform group-hover:translate-x-0.5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><polyline points="9 18 15 12 9 6"/></svg>
      </a>
    </div>
  </div>

</div>
