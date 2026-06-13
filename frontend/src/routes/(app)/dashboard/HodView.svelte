<script lang="ts">
  import type { HodDashboard } from '$lib/api/dashboard';
  import StatCard from '$lib/components/StatCard.svelte';

  interface Props { data: HodDashboard; }
  const { data }: Props = $props();

  function greeting(name: string): string {
    const h = new Date().getHours();
    return `${h < 12 ? 'Good morning' : h < 17 ? 'Good afternoon' : 'Good evening'}, ${name}`;
  }

  const approvalProgress = $derived(() => {
    const total = data.assessments_this_term;
    if (!total) return 0;
    const approved = Math.max(0, total - data.pending_approvals);
    return Math.round((approved / total) * 100);
  });
</script>

<div class="mb-6">
  <h1 class="text-xl font-bold text-gray-900">{greeting(data.greeting_name)}</h1>
  <p class="text-sm text-gray-400">
    {data.pending_approvals > 0
      ? `You have ${data.pending_approvals} score submission${data.pending_approvals === 1 ? '' : 's'} waiting for approval.`
      : 'All submitted scores are approved. 🎉'}
  </p>
</div>

<div class="mb-5 grid grid-cols-2 gap-3">
  <StatCard
    label="Pending Approvals"
    value={data.pending_approvals}
    icon="📋"
    color="bg-amber-50"
    iconColor="text-amber-600"
    href="/scores"
    alert={data.pending_approvals > 0}
  />
  <StatCard
    label="Assessments This Term"
    value={data.assessments_this_term}
    icon="📝"
    color="bg-blue-50"
    iconColor="text-blue-600"
    href="/scores"
  />
</div>

<!-- Approval progress bar -->
{#if data.assessments_this_term > 0}
  <div class="mb-5 rounded-2xl border border-gray-100 bg-white p-5">
    <div class="mb-1 flex items-center justify-between text-sm">
      <span class="font-medium text-gray-700">Approval progress</span>
      <span class="font-semibold text-gray-800">{approvalProgress()}%</span>
    </div>
    <div class="h-2.5 w-full overflow-hidden rounded-full bg-gray-100">
      <div
        class="h-full rounded-full transition-all duration-700"
        style="width: {approvalProgress()}%; background-color: var(--brand)"
      ></div>
    </div>
    <p class="mt-1.5 text-xs text-gray-400">
      {data.assessments_this_term - data.pending_approvals} of {data.assessments_this_term} assessments fully approved
    </p>
  </div>
{/if}

<!-- Actions -->
<div>
  <h3 class="mb-3 text-xs font-semibold uppercase tracking-widest text-gray-400">Quick actions</h3>
  <div class="grid grid-cols-2 gap-3">
    <a href="/scores?filter=pending"
       class="flex flex-col items-center gap-2 rounded-2xl border border-amber-100 bg-amber-50 p-5 text-center transition hover:shadow-md active:scale-[0.98]">
      <span class="text-2xl">⚡</span>
      <span class="text-sm font-semibold text-amber-800">Approve Scores</span>
    </a>
    <a href="/scores"
       class="flex flex-col items-center gap-2 rounded-2xl border border-gray-100 bg-white p-5 text-center transition hover:shadow-md active:scale-[0.98]">
      <span class="text-2xl">📊</span>
      <span class="text-sm font-semibold text-gray-700">All Assessments</span>
    </a>
  </div>
</div>
