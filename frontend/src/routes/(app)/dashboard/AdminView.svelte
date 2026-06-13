<script lang="ts">
  import type { AdminDashboard } from '$lib/api/dashboard';
  import StatCard from '$lib/components/StatCard.svelte';

  interface Props { data: AdminDashboard; }
  const { data }: Props = $props();

  function greeting(name: string): string {
    const h = new Date().getHours();
    return `${h < 12 ? 'Good morning' : h < 17 ? 'Good afternoon' : 'Good evening'}, ${name}`;
  }

  function fmt(n: number) {
    return n.toLocaleString('en-GH');
  }

  function fmtGHS(n: number) {
    return `GHS ${n.toLocaleString('en-GH', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`;
  }

  const attendancePct = $derived(() => Math.round(data.attendance_pct));
  const collectionPct = $derived(() => Math.round(data.term_collection_pct));
</script>

<!-- Greeting -->
<div class="mb-6">
  <h1 class="text-xl font-bold text-gray-900">{greeting(data.greeting_name)}</h1>
  <p class="text-sm text-gray-400">{data.school_name}</p>
</div>

<!-- Top stat cards -->
<div class="mb-5 grid grid-cols-2 gap-3 lg:grid-cols-4">
  <StatCard
    label="Students Enrolled"
    value={fmt(data.total_students)}
    icon="👩‍🎓"
    color="bg-indigo-50"
    iconColor="text-indigo-600"
    href="/students"
  />
  <StatCard
    label="Present Today"
    value="{attendancePct()}%"
    icon="✅"
    color="bg-green-50"
    iconColor="text-green-600"
    trend="{fmt(data.today_present)} of {fmt(data.today_total)}"
    href="/attendance"
    alert={data.attendance_pct < 80 && data.today_total > 0}
  />
  <StatCard
    label="Fees Collected"
    value="{collectionPct()}%"
    icon="💰"
    color="bg-emerald-50"
    iconColor="text-emerald-600"
    trend={fmtGHS(Number(data.term_collected))}
    href="/fees"
    alert={data.term_collection_pct < 50}
  />
  <StatCard
    label="Pending Approvals"
    value={fmt(data.pending_approvals)}
    icon="📋"
    color="bg-amber-50"
    iconColor="text-amber-600"
    href="/scores"
    alert={data.pending_approvals > 0}
  />
</div>

<!-- Attendance by class -->
{#if data.class_attendance.length > 0}
  <div class="mb-5 rounded-2xl border border-gray-100 bg-white p-5">
    <h3 class="mb-4 text-xs font-semibold uppercase tracking-widest text-gray-400">
      Attendance today · by class
    </h3>
    <div class="space-y-3">
      {#each data.class_attendance as cls}
        {@const pct = cls.total > 0 ? cls.pct : 0}
        {@const low = pct < 70 && cls.total > 0}
        <div>
          <div class="mb-1 flex items-center justify-between text-sm">
            <span class="font-medium text-gray-700">{cls.name}</span>
            <span class="font-semibold {low ? 'text-red-600' : 'text-gray-700'}">
              {pct}%
              {#if low}<span class="text-xs">⚠</span>{/if}
            </span>
          </div>
          <div class="h-2 w-full overflow-hidden rounded-full bg-gray-100">
            <div
              class="h-full rounded-full transition-all duration-500 {low ? 'bg-red-400' : ''}"
              style="width: {pct}%; {!low ? 'background-color: var(--brand)' : ''}"
            ></div>
          </div>
          <p class="mt-0.5 text-xs text-gray-400">{cls.present} of {cls.total} present</p>
        </div>
      {/each}
    </div>
  </div>
{/if}

<!-- Fee collection progress -->
<div class="mb-5 rounded-2xl border border-gray-100 bg-white p-5">
  <h3 class="mb-1 text-xs font-semibold uppercase tracking-widest text-gray-400">
    Term fee collection
  </h3>
  <div class="mb-3 flex items-end justify-between">
    <span class="text-2xl font-bold text-gray-900">{collectionPct()}%</span>
    <span class="text-sm text-gray-400">
      {fmtGHS(Number(data.term_collected))} of {fmtGHS(Number(data.term_expected))}
    </span>
  </div>
  <div class="h-3 w-full overflow-hidden rounded-full bg-gray-100">
    <div
      class="h-full rounded-full transition-all duration-700"
      style="width: {collectionPct()}%; background-color: var(--brand)"
    ></div>
  </div>
  <a href="/fees" class="mt-3 inline-block text-xs font-medium hover:underline" style="color: var(--brand)">
    View fee records →
  </a>
</div>

<!-- Quick actions -->
<div>
  <h3 class="mb-3 text-xs font-semibold uppercase tracking-widest text-gray-400">Quick actions</h3>
  <div class="grid grid-cols-2 gap-3 lg:grid-cols-4">
    {#each [
      { href: '/admin/academic', icon: '📅', label: 'Academic Setup' },
      { href: '/admin/structure', icon: '🏫', label: 'Classes & Subjects' },
      { href: '/admin/staff', icon: '👩‍🏫', label: 'Manage Staff' },
      { href: '/admin/sms', icon: '📱', label: 'SMS Config' },
    ] as action}
      <a
        href={action.href}
        class="flex flex-col items-center justify-center gap-2 rounded-2xl border border-gray-100 bg-white p-4 text-center transition hover:shadow-md active:scale-[0.98]"
      >
        <span class="text-xl">{action.icon}</span>
        <span class="text-xs font-medium text-gray-700">{action.label}</span>
      </a>
    {/each}
  </div>
</div>
