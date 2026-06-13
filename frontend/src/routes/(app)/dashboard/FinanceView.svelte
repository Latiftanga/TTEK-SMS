<script lang="ts">
  import type { FinanceDashboard } from '$lib/api/dashboard';
  import StatCard from '$lib/components/StatCard.svelte';

  interface Props { data: FinanceDashboard; }
  const { data }: Props = $props();

  function greeting(name: string): string {
    const h = new Date().getHours();
    return `${h < 12 ? 'Good morning' : h < 17 ? 'Good afternoon' : 'Good evening'}, ${name}`;
  }

  function fmtGHS(n: number) {
    return `GHS ${Number(n).toLocaleString('en-GH', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  }

  const collectionPct = $derived(() => Math.round(data.collection_pct));
  const remaining = $derived(() => Number(data.term_expected) - Number(data.term_collected));
</script>

<div class="mb-6">
  <h1 class="text-xl font-bold text-gray-900">{greeting(data.greeting_name)}</h1>
  <p class="text-sm text-gray-400">Term fee collection overview</p>
</div>

<!-- Hero collection card -->
<div class="mb-5 rounded-2xl p-6 text-white" style="background-color: var(--brand)">
  <p class="text-sm font-medium opacity-80">Term collection</p>
  <p class="mt-1 text-4xl font-bold">{collectionPct()}%</p>
  <div class="mt-3 h-2 w-full overflow-hidden rounded-full bg-white/30">
    <div
      class="h-full rounded-full bg-white transition-all duration-700"
      style="width: {collectionPct()}%"
    ></div>
  </div>
  <div class="mt-2 flex justify-between text-xs opacity-70">
    <span>{fmtGHS(Number(data.term_collected))} collected</span>
    <span>{fmtGHS(Number(data.term_expected))} expected</span>
  </div>
</div>

<!-- Stat row -->
<div class="mb-5 grid grid-cols-2 gap-3 lg:grid-cols-3">
  <StatCard
    label="Payments Today"
    value={data.payments_today}
    icon="💳"
    color="bg-green-50"
    iconColor="text-green-600"
    href="/fees"
  />
  <StatCard
    label="Outstanding Students"
    value={data.outstanding_students}
    icon="⏳"
    color="bg-red-50"
    iconColor="text-red-500"
    href="/fees?filter=outstanding"
    alert={data.outstanding_students > 0}
  />
  <StatCard
    label="Remaining"
    value={fmtGHS(remaining())}
    icon="📉"
    color="bg-amber-50"
    iconColor="text-amber-600"
  />
</div>

<!-- Quick actions -->
<div>
  <h3 class="mb-3 text-xs font-semibold uppercase tracking-widest text-gray-400">Quick actions</h3>
  <div class="grid grid-cols-2 gap-3">
    <a href="/fees/pay"
       class="flex flex-col items-center gap-2 rounded-2xl p-5 text-center text-white transition hover:opacity-90 active:scale-[0.98]"
       style="background-color: var(--brand)">
      <span class="text-2xl">💳</span>
      <span class="text-sm font-semibold">Record Payment</span>
    </a>
    <a href="/fees?filter=outstanding"
       class="flex flex-col items-center gap-2 rounded-2xl border border-gray-100 bg-white p-5 text-center transition hover:shadow-md active:scale-[0.98]">
      <span class="text-2xl">📋</span>
      <span class="text-sm font-semibold text-gray-700">View Outstanding</span>
    </a>
    <a href="/fees/discounts"
       class="flex flex-col items-center gap-2 rounded-2xl border border-gray-100 bg-white p-5 text-center transition hover:shadow-md active:scale-[0.98]">
      <span class="text-2xl">🏷️</span>
      <span class="text-sm font-semibold text-gray-700">Discounts</span>
    </a>
    <a href="/fees/report"
       class="flex flex-col items-center gap-2 rounded-2xl border border-gray-100 bg-white p-5 text-center transition hover:shadow-md active:scale-[0.98]">
      <span class="text-2xl">📊</span>
      <span class="text-sm font-semibold text-gray-700">Fee Report</span>
    </a>
  </div>
</div>
