<script lang="ts">
  import type { AdminDashboard } from '$lib/api/dashboard';
  import StatCard from '$lib/components/StatCard.svelte';

  interface Props { data: AdminDashboard; }
  const { data }: Props = $props();

  const hour = new Date().getHours();
  const salutation = hour < 12 ? 'Good morning' : hour < 17 ? 'Good afternoon' : 'Good evening';

  function fmt(n: number) { return n.toLocaleString('en-GH'); }
  function fmtGHS(n: number) {
    return `GHS ${Number(n).toLocaleString('en-GH', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`;
  }

  const attendancePct = $derived(Math.round(data.attendance_pct));
  const collectionPct = $derived(Math.min(100, Math.round(data.term_collection_pct)));

  // No per-stat color mapping anymore — StatCard now keeps a single
  // neutral icon treatment and reserves color for the alert state only.
  const icons = {
    students:   `<path stroke-linecap="round" stroke-linejoin="round" d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z"/>`,
    attendance: `<path stroke-linecap="round" stroke-linejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/>`,
    fees:       `<path stroke-linecap="round" stroke-linejoin="round" d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>`,
    pending:    `<path stroke-linecap="round" stroke-linejoin="round" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"/>`,
    academic:   `<path stroke-linecap="round" stroke-linejoin="round" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"/>`,
    staff:      `<path stroke-linecap="round" stroke-linejoin="round" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z"/>`,
    feeSetup:   `<path stroke-linecap="round" stroke-linejoin="round" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"/><path stroke-linecap="round" stroke-linejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"/>`,
    sms:        `<path stroke-linecap="round" stroke-linejoin="round" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"/>`,
    arrow:      `<path stroke-linecap="round" stroke-linejoin="round" d="M7 17L17 7M17 7H7M17 7v10"/>`,
  };

  const adminLinks = [
    { href: '/admin/academic',   label: 'Academic Setup',    sub: 'Years, terms & calendar',   icon: icons.academic  },
    { href: '/admin/staff',      label: 'Manage Staff',      sub: 'Profiles & permissions',    icon: icons.staff     },
    { href: '/fees',                          label: 'Fee Structure',     sub: 'Types, amounts & waivers',  icon: icons.feeSetup  },
    { href: '/admin/setup?tab=communication', label: 'SMS Notifications', sub: 'Provider & auto-alerts',    icon: icons.sms       },
  ];
</script>

<!-- Greeting -->
<div class="mb-6 flex items-start justify-between gap-4">
  <div>
    <h1 class="text-2xl font-bold tracking-tight text-[var(--fg)]">
      {salutation}, {data.greeting_name.split(' ')[0]}.
    </h1>
    <p class="mt-0.5 text-sm text-[var(--fg-muted)]">{data.school_name}</p>
  </div>
  {#if data.pending_approvals > 0}
    <a href="/assessments"
       class="flex shrink-0 items-center gap-1.5 rounded-full border border-amber-200 dark:border-amber-700
              bg-amber-50 dark:bg-amber-950/40 px-3 py-1.5 text-xs font-semibold
              text-amber-700 dark:text-amber-400 transition hover:bg-amber-100 dark:hover:bg-amber-900/60">
      <span class="h-1.5 w-1.5 rounded-full bg-amber-500 animate-pulse"></span>
      {data.pending_approvals} awaiting approval
    </a>
  {/if}
</div>

<!-- 4 stat cards -->
<div class="mb-7 grid grid-cols-2 gap-4 lg:grid-cols-4">
  <StatCard
    label="Enrolled"
    value={fmt(data.total_students)}
    iconPath={icons.students}
    href="/students"
  />
  <StatCard
    label="Present Today"
    value="{attendancePct}%"
    iconPath={icons.attendance}
    trend="{fmt(data.today_present)} of {fmt(data.today_total)}"
    href="/attendance"
    alert={data.attendance_pct < 80 && data.today_total > 0}
  />
  <StatCard
    label="Fees Collected"
    value="{collectionPct}%"
    iconPath={icons.fees}
    trend={fmtGHS(Number(data.term_collected))}
    href="/fees"
    alert={data.term_collection_pct < 50}
  />
  <StatCard
    label="Awaiting Approval"
    value={fmt(data.pending_approvals)}
    iconPath={icons.pending}
    href="/assessments"
    alert={data.pending_approvals > 0}
  />
</div>

<!-- Two-column on xl -->
<div class="grid grid-cols-1 gap-6 xl:grid-cols-[3fr_2fr]">

  <!-- LEFT: class-level attendance -->
  {#if data.class_attendance.length > 0}
    <div class="rounded-[1.25rem] border border-[var(--border)] bg-[var(--card)] p-6"
         style="box-shadow: var(--shadow-md);">
      <div class="mb-5 flex items-center justify-between">
        <div>
          <p class="text-sm font-semibold text-[var(--fg)]">Attendance by class</p>
          <p class="text-[11px] text-[var(--fg-muted)] mt-0.5">Today's presence rate</p>
        </div>
        <a href="/attendance"
           class="text-xs font-semibold transition hover:opacity-80"
           style="color: var(--brand)">View all →</a>
      </div>
      <div class="space-y-4">
        {#each data.class_attendance as cls}
          {@const pct = cls.total > 0 ? cls.pct : 0}
          {@const low = cls.marked && pct < 70 && cls.total > 0}
          <!-- A class with zero records ("not marked yet") is distinct from
               one that was marked with a genuinely low presence rate — both
               used to render as an identical 0% bar. -->
          {#if !cls.marked}
            <a href="/attendance"
               class="group -mx-2 block rounded-lg px-2 py-1 transition hover:bg-amber-50 dark:hover:bg-amber-950/30">
              <div class="mb-1.5 flex items-center justify-between gap-2">
                <span class="text-[0.8125rem] font-medium text-[var(--fg)]">{cls.name}</span>
                <span class="flex items-center gap-1 text-sm font-bold text-amber-600 dark:text-amber-400">
                  Mark now
                  <svg class="h-3.5 w-3.5 transition-transform group-hover:translate-x-0.5" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M9 5l7 7-7 7"/>
                  </svg>
                </span>
              </div>
              <div class="h-2 w-full overflow-hidden rounded-full bg-gray-100 dark:bg-gray-800"></div>
              <p class="mt-1 text-[11px] text-[var(--fg-muted)]">{cls.total} students · not marked yet</p>
            </a>
          {:else}
            <div>
              <div class="mb-1.5 flex items-center justify-between">
                <span class="text-[0.8125rem] font-medium text-[var(--fg)]">{cls.name}</span>
                <div class="flex items-center gap-1.5">
                  {#if low}
                    <svg class="h-3.5 w-3.5 text-red-500" fill="none" stroke="currentColor"
                         stroke-width="2" viewBox="0 0 24 24">
                      <path stroke-linecap="round" stroke-linejoin="round"
                            d="M12 9v4m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/>
                    </svg>
                  {/if}
                  <span class="text-sm font-bold {low ? 'text-red-600 dark:text-red-400' : 'text-[var(--fg)]'}">{pct}%</span>
                </div>
              </div>
              <div class="h-2 w-full overflow-hidden rounded-full bg-gray-100 dark:bg-gray-800">
                <div class="h-full rounded-full transition-all duration-700 {low ? 'bg-red-400' : ''}"
                     style="width: {pct}%; {!low ? 'background-color: var(--brand)' : ''}"></div>
              </div>
              <p class="mt-1 text-[11px] text-[var(--fg-muted)]">{cls.present} of {cls.total} present</p>
            </div>
          {/if}
        {/each}
      </div>
    </div>
  {/if}

  <!-- RIGHT: fee summary + admin links -->
  <div class="space-y-6">

    <!-- Fee collection -->
    <div class="rounded-[1.25rem] border border-[var(--border)] bg-[var(--card)] p-6"
         style="box-shadow: var(--shadow-sm);">
      <div class="mb-4 flex items-center justify-between">
        <div>
          <p class="text-sm font-semibold text-[var(--fg)]">Term fee collection</p>
          <p class="text-[11px] text-[var(--fg-muted)] mt-0.5">{fmtGHS(Number(data.term_collected))} of {fmtGHS(Number(data.term_expected))}</p>
        </div>
        <a href="/fees" class="text-xs font-semibold transition hover:opacity-80" style="color: var(--brand)">
          View records →
        </a>
      </div>
      <div class="flex items-end gap-2 mb-3">
        <span class="text-[2rem] font-bold leading-none tracking-tight text-[var(--fg)]">{collectionPct}%</span>
        <span class="mb-0.5 text-xs text-[var(--fg-muted)]">collected</span>
      </div>
      <div class="h-2 w-full overflow-hidden rounded-full bg-gray-100 dark:bg-gray-800">
        <div class="h-full rounded-full transition-all duration-700"
             style="width: {collectionPct}%; background-color: var(--brand)"></div>
      </div>
    </div>

    <!-- Admin quick links -->
    <div>
      <p class="mb-2.5 text-[0.6875rem] font-semibold uppercase tracking-widest text-[var(--fg-muted)]">
        Administration
      </p>
      <div class="overflow-hidden rounded-[1.25rem] border border-[var(--border)] bg-[var(--card)]
                  divide-y divide-[var(--border)]"
           style="box-shadow: var(--shadow-sm);">
        {#each adminLinks as link}
          <a href={link.href}
             class="group flex items-center gap-3.5 px-4 py-3.5 transition hover:bg-[var(--hover)]">
            <div class="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl
                        bg-[var(--hover)] transition group-hover:bg-[var(--card)]">
              <svg class="h-4 w-4 text-[var(--fg-muted)]" fill="none" stroke="currentColor"
                   stroke-width="1.6" viewBox="0 0 24 24">
                {@html link.icon}
              </svg>
            </div>
            <div class="flex-1 min-w-0">
              <p class="text-[0.8125rem] font-semibold text-[var(--fg)]">{link.label}</p>
              <p class="text-[0.6875rem] text-[var(--fg-muted)]">{link.sub}</p>
            </div>
            <svg class="h-4 w-4 text-[var(--fg-subtle)] transition-transform group-hover:translate-x-0.5"
                 fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
              {@html icons.arrow}
            </svg>
          </a>
        {/each}
      </div>
    </div>

  </div>
</div>
