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

  const attendancePct = $derived(() => Math.round(data.attendance_pct));
  const collectionPct = $derived(() => Math.min(100, Math.round(data.term_collection_pct)));

  const adminLinks = [
    { href: '/admin/academic',  label: 'Academic Setup',     sub: 'Years, terms, calendar'   },
    { href: '/admin/structure', label: 'Classes & Subjects',  sub: 'Organise the school'      },
    { href: '/admin/staff',     label: 'Manage Staff',        sub: 'Profiles & permissions'   },
    { href: '/admin/sms',       label: 'SMS Config',          sub: 'Notifications & provider' },
  ];
</script>

<!-- Greeting — full width -->
<div class="mb-6 flex items-start justify-between gap-4">
  <div>
    <h1 class="text-2xl font-bold text-[var(--fg)]">{salutation}, {data.greeting_name.split(' ')[0]}.</h1>
    <p class="mt-0.5 text-sm text-[var(--fg-muted)]">{data.school_name}</p>
  </div>
  {#if data.pending_approvals > 0}
    <a href="/scores?filter=pending"
       class="flex shrink-0 items-center gap-1.5 rounded-full border border-amber-200 dark:border-amber-700
              bg-amber-50 dark:bg-amber-950/40 px-3 py-1.5 text-xs font-semibold
              text-amber-700 dark:text-amber-400 transition hover:bg-amber-100 dark:hover:bg-amber-900/60">
      <span class="h-1.5 w-1.5 rounded-full bg-amber-500 animate-pulse"></span>
      {data.pending_approvals} pending
    </a>
  {/if}
</div>

<!-- 4 stat cards — full width, always -->
<div class="mb-6 grid grid-cols-2 gap-3 lg:grid-cols-4">
  <StatCard label="Enrolled" value={fmt(data.total_students)}
    icon="👥" color="bg-indigo-50 dark:bg-indigo-950/40" iconColor="text-indigo-600 dark:text-indigo-400"
    href="/students" />
  <StatCard label="Present Today" value="{attendancePct()}%"
    icon="✅" color="bg-green-50 dark:bg-green-950/40" iconColor="text-green-600 dark:text-green-400"
    trend="{fmt(data.today_present)} of {fmt(data.today_total)}"
    href="/attendance" alert={data.attendance_pct < 80 && data.today_total > 0} />
  <StatCard label="Fees Collected" value="{collectionPct()}%"
    icon="💰" color="bg-emerald-50 dark:bg-emerald-950/40" iconColor="text-emerald-600 dark:text-emerald-400"
    trend={fmtGHS(Number(data.term_collected))}
    href="/fees" alert={data.term_collection_pct < 50} />
  <StatCard label="Awaiting Approval" value={fmt(data.pending_approvals)}
    icon="⏳" color="bg-amber-50 dark:bg-amber-950/40" iconColor="text-amber-600 dark:text-amber-400"
    href="/scores" alert={data.pending_approvals > 0} />
</div>

<!-- Two-column on xl: left = attendance, right = fees + admin links -->
<div class="grid grid-cols-1 gap-5 xl:grid-cols-[3fr_2fr]">

  <!-- LEFT: class-level attendance -->
  {#if data.class_attendance.length > 0}
    <div class="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
      <div class="mb-4 flex items-center justify-between">
        <p class="text-[11px] font-semibold uppercase tracking-widest text-[var(--fg-muted)]">
          Attendance · by class
        </p>
        <a href="/attendance" class="text-[11px] font-semibold hover:underline" style="color: var(--brand)">
          View all →
        </a>
      </div>
      <div class="space-y-4">
        {#each data.class_attendance as cls}
          {@const pct = cls.total > 0 ? cls.pct : 0}
          {@const low = pct < 70 && cls.total > 0}
          <div>
            <div class="mb-1.5 flex items-center justify-between">
              <span class="text-sm font-medium text-[var(--fg)]">{cls.name}</span>
              <div class="flex items-center gap-1.5">
                {#if low}
                  <svg class="h-3.5 w-3.5 text-red-500" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M12 9v4m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/>
                  </svg>
                {/if}
                <span class="text-sm font-bold {low ? 'text-red-600 dark:text-red-400' : 'text-[var(--fg)]'}">{pct}%</span>
              </div>
            </div>
            <div class="h-1.5 w-full overflow-hidden rounded-full bg-gray-100 dark:bg-gray-800">
              <div class="h-full rounded-full transition-all duration-700 {low ? 'bg-red-400' : ''}"
                   style="width: {pct}%; {!low ? 'background-color: var(--brand)' : ''}"></div>
            </div>
            <p class="mt-1 text-[10px] text-[var(--fg-muted)]">{cls.present} of {cls.total} present</p>
          </div>
        {/each}
      </div>
    </div>
  {/if}

  <!-- RIGHT: fee summary + admin links -->
  <div class="space-y-5">

    <!-- Fee bar -->
    <div class="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
      <div class="mb-3 flex items-center justify-between">
        <p class="text-[11px] font-semibold uppercase tracking-widest text-[var(--fg-muted)]">Term fee collection</p>
        <a href="/fees" class="text-[11px] font-semibold hover:underline" style="color: var(--brand)">
          View records →
        </a>
      </div>
      <div class="flex items-end justify-between mb-2">
        <span class="text-3xl font-bold text-[var(--fg)]">{collectionPct()}%</span>
        <span class="text-sm text-[var(--fg-muted)]">{fmtGHS(Number(data.term_collected))} / {fmtGHS(Number(data.term_expected))}</span>
      </div>
      <div class="h-2.5 w-full overflow-hidden rounded-full bg-gray-100 dark:bg-gray-800">
        <div class="h-full rounded-full transition-all duration-700"
             style="width: {collectionPct()}%; background-color: var(--brand)"></div>
      </div>
    </div>

    <!-- Admin quick links -->
    <div>
      <p class="mb-2.5 text-[11px] font-semibold uppercase tracking-widest text-[var(--fg-muted)]">Administration</p>
      <div class="overflow-hidden rounded-xl border border-[var(--border)] bg-[var(--card)] divide-y divide-[var(--border)]">
        {#each adminLinks as link}
          <a href={link.href} class="group flex items-center gap-4 px-5 py-3.5 transition hover:bg-[var(--bg)]">
            <div class="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-gray-100 dark:bg-gray-800">
              <svg class="h-4 w-4 text-gray-400 dark:text-gray-500" fill="none" stroke="currentColor" stroke-width="1.5" viewBox="0 0 24 24">
                <polyline points="9 18 15 12 9 6"/>
              </svg>
            </div>
            <div class="flex-1 min-w-0">
              <p class="text-sm font-semibold text-[var(--fg)]">{link.label}</p>
              <p class="text-[11px] text-[var(--fg-muted)]">{link.sub}</p>
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
