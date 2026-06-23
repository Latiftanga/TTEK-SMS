<script lang="ts">
  import type { FinanceDashboard } from '$lib/api/dashboard';
  import StatCard from '$lib/components/StatCard.svelte';

  interface Props { data: FinanceDashboard; }
  const { data }: Props = $props();

  const hour = new Date().getHours();
  const salutation = hour < 12 ? 'Good morning' : hour < 17 ? 'Good afternoon' : 'Good evening';

  function fmtGHS(n: number) {
    return `GHS ${Number(n).toLocaleString('en-GH', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  }

  const pct       = $derived(Math.min(100, Math.round(data.collection_pct)));
  const remaining = $derived(Math.max(0, Number(data.term_expected) - Number(data.term_collected)));
  const C = 2 * Math.PI * 40;

  const actions = $derived.by(() => [
    { href: '/fees/pay',         label: 'Record Payment',   sub: 'Accept a new payment',   primary: true  },
    { href: '/fees?outstanding', label: 'View Outstanding', sub: `${data.outstanding_students} students`, primary: false },
    { href: '/fees/discounts',   label: 'Manage Discounts', sub: 'Apply or review',         primary: false },
    { href: '/fees/report',      label: 'Fee Report',       sub: 'Export & analyse',        primary: false },
  ]);

  const icons = {
    creditCard: `<path stroke-linecap="round" stroke-linejoin="round" d="M3 10h18M7 15h1m4 0h1m-7 4h12a3 3 0 003-3V8a3 3 0 00-3-3H6a3 3 0 00-3 3v8a3 3 0 003 3z"/>`,
    clock:      `<path stroke-linecap="round" stroke-linejoin="round" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"/>`,
    trendDown:  `<path stroke-linecap="round" stroke-linejoin="round" d="M13 17h8m0 0V9m0 8l-8-8-4 4-6-6"/>`,
  };
</script>

<!-- Greeting — full width -->
<div class="mb-5">
  <h1 class="text-2xl font-bold text-[var(--fg)]">{salutation}, {data.greeting_name.split(' ')[0]}.</h1>
  <p class="mt-0.5 text-sm text-[var(--fg-muted)]">Here's your fee collection overview for this term.</p>
</div>

<!-- Two-column on xl: left = hero ring, right = stats + actions -->
<div class="grid grid-cols-1 gap-5 xl:grid-cols-[3fr_2fr]">

  <!-- LEFT: hero ring card -->
  <div>
    <div class="relative overflow-hidden rounded-2xl p-6 text-white"
         style="background: linear-gradient(135deg, var(--brand) 0%, color-mix(in oklab, var(--brand) 72%, #312e81) 100%)">

      <p class="mb-5 text-sm font-semibold opacity-80 uppercase tracking-widest">Term Collection</p>
      <div class="flex items-center gap-6">
        <div class="relative flex-shrink-0">
          <svg class="w-28 h-28 xl:w-36 xl:h-36" viewBox="0 0 96 96">
            <circle cx="48" cy="48" r="40" fill="none" stroke="rgba(255,255,255,0.2)" stroke-width="7"/>
            <circle cx="48" cy="48" r="40" fill="none" stroke="white" stroke-width="7"
              stroke-linecap="round"
              stroke-dasharray="{C}" stroke-dashoffset="{C * (1 - pct / 100)}"
              transform="rotate(-90 48 48)"
              style="transition: stroke-dashoffset 900ms cubic-bezier(0.4,0,0.2,1)"/>
          </svg>
          <div class="absolute inset-0 flex flex-col items-center justify-center">
            <span class="text-2xl font-bold leading-none xl:text-3xl">{pct}%</span>
            <span class="mt-0.5 text-[10px] opacity-70 uppercase tracking-widest">done</span>
          </div>
        </div>
        <div class="flex-1 min-w-0">
          <p class="text-3xl font-bold leading-tight xl:text-4xl">{fmtGHS(Number(data.term_collected))}</p>
          <p class="mt-1 text-sm opacity-75">collected this term</p>
          <div class="mt-3 h-px w-full bg-white/20"></div>
          <p class="mt-3 text-sm opacity-80">
            <span class="font-semibold">{fmtGHS(remaining)}</span> remaining of {fmtGHS(Number(data.term_expected))}
          </p>
        </div>
      </div>
    </div>
  </div>

  <!-- RIGHT: stat cards + actions -->
  <div class="space-y-5">

    <div class="grid grid-cols-3 xl:grid-cols-1 gap-3">
      <StatCard label="Payments Today"  value={data.payments_today}
        iconPath={icons.creditCard}
        color="bg-green-50 dark:bg-green-950/40" iconColor="text-green-600 dark:text-green-400"
        href="/fees" />
      <StatCard label="Outstanding"     value={data.outstanding_students}
        iconPath={icons.clock}
        color="bg-red-50 dark:bg-red-950/40" iconColor="text-red-500 dark:text-red-400"
        href="/fees?outstanding" alert={data.outstanding_students > 0} trend="students" />
      <StatCard label="Remaining"       value={fmtGHS(remaining)}
        iconPath={icons.trendDown}
        color="bg-amber-50 dark:bg-amber-950/40" iconColor="text-amber-600 dark:text-amber-400" />
    </div>

    <div>
      <p class="mb-2.5 text-[11px] font-semibold uppercase tracking-widest text-[var(--fg-muted)]">Actions</p>
      <div class="overflow-hidden rounded-2xl border border-[var(--border)] bg-[var(--card)] divide-y divide-[var(--border)]">
        {#each actions as action}
          <a href={action.href} class="group flex items-center gap-4 px-5 py-3.5 transition hover:bg-[var(--bg)]">
            <div class="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg
                        {action.primary ? 'text-white' : 'bg-gray-100 dark:bg-gray-800'}"
                 style={action.primary ? 'background-color: var(--brand)' : ''}>
              {#if action.primary}
                <svg class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M12 4v16m8-8H4"/>
                </svg>
              {:else}
                <svg class="h-4 w-4 text-gray-400 dark:text-gray-500" fill="none" stroke="currentColor" stroke-width="1.5" viewBox="0 0 24 24">
                  <polyline points="9 18 15 12 9 6"/>
                </svg>
              {/if}
            </div>
            <div class="flex-1 min-w-0">
              <p class="text-sm font-semibold text-[var(--fg)]">{action.label}</p>
              <p class="text-[11px] text-[var(--fg-muted)]">{action.sub}</p>
            </div>
            <svg class="h-4 w-4 text-gray-300 dark:text-gray-700 transition-transform group-hover:translate-x-0.5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
              <polyline points="9 18 15 12 9 6"/>
            </svg>
          </a>
        {/each}
      </div>
    </div>

  </div>
</div>
