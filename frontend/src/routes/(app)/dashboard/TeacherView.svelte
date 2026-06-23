<script lang="ts">
  import type { TeacherDashboard } from '$lib/api/dashboard';
  import StatCard from '$lib/components/StatCard.svelte';

  interface Props { data: TeacherDashboard; }
  const { data }: Props = $props();

  const hour = new Date().getHours();
  const salutation = hour < 12 ? 'Good morning' : hour < 17 ? 'Good afternoon' : 'Good evening';

  const todayLabel = $derived(new Date(data.today_iso).toLocaleDateString('en-GH', {
    weekday: 'long', day: 'numeric', month: 'long',
  }));

  const tasks = $derived.by(() => [
    {
      href: '/attendance',
      label: 'Mark Attendance',
      badge: data.my_class?.attendance_marked_today ? 'Done today' : 'Not yet marked',
      urgent: !data.my_class?.attendance_marked_today,
    },
    {
      href: '/scores',
      label: 'Enter Scores',
      badge: data.pending_score_assessments > 0 ? `${data.pending_score_assessments} pending` : 'No pending',
      urgent: data.pending_score_assessments > 0,
    },
    { href: '/students', label: 'My Students', badge: `${data.my_class?.student_count ?? 0} enrolled`, urgent: false },
    { href: '/reports',  label: 'Report Cards', badge: 'View & download', urgent: false },
  ]);

  const icons = {
    pencil: `<path stroke-linecap="round" stroke-linejoin="round" d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z"/>`,
    userMinus: `<path stroke-linecap="round" stroke-linejoin="round" d="M13 7a4 4 0 11-8 0 4 4 0 018 0zM9 14a6 6 0 00-6 6v1h12v-1a6 6 0 00-6-6zm8-1h4"/>`,
    users: `<path stroke-linecap="round" stroke-linejoin="round" d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z"/>`,
  };
</script>

<!-- Greeting — always full width -->
<div class="mb-6 flex items-start justify-between">
  <div>
    <h1 class="text-2xl font-bold text-[var(--fg)]">{salutation}, {data.greeting_name.split(' ')[0]}.</h1>
    <p class="mt-0.5 text-sm text-[var(--fg-muted)]">{todayLabel}</p>
  </div>
  {#if (data.my_class?.absent_today ?? 0) > 0}
    <div class="flex items-center gap-1.5 rounded-full border border-red-200 dark:border-red-800
                bg-red-50 dark:bg-red-950/40 px-3 py-1.5 text-xs font-semibold
                text-red-600 dark:text-red-400">
      <span class="h-1.5 w-1.5 rounded-full bg-red-500 animate-pulse"></span>
      {data.my_class?.absent_today} absent
    </div>
  {/if}
</div>

<!-- Two-column on xl: left = class + stats, right = tasks + absences -->
<div class="grid grid-cols-1 gap-5 xl:grid-cols-[3fr_2fr]">

  <!-- LEFT COLUMN -->
  <div class="space-y-5">

    <!-- Class hero card -->
    {#if data.my_class}
      {@const cls = data.my_class}
      {@const C = 2 * Math.PI * 30}
      {@const pct = cls.attendance_marked_today && cls.student_count > 0
        ? Math.round((cls.present_today / cls.student_count) * 100) : 0}
      {@const low = cls.attendance_marked_today && pct < 75}

      <div class="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
        <p class="mb-4 text-[11px] font-semibold uppercase tracking-widest text-[var(--fg-muted)]">Your Class</p>
        <div class="flex items-center gap-5">
          <div class="relative flex-shrink-0">
            <svg class="w-20 h-20" viewBox="0 0 80 80">
              <circle cx="40" cy="40" r="30" fill="none" class="stroke-gray-100 dark:stroke-gray-800" stroke-width="6"/>
              <circle cx="40" cy="40" r="30" fill="none"
                stroke={!cls.attendance_marked_today ? '#d1d5db' : low ? '#f59e0b' : 'var(--brand)'}
                stroke-width="6" stroke-linecap="round"
                stroke-dasharray="{C}" stroke-dashoffset="{C * (1 - pct / 100)}"
                transform="rotate(-90 40 40)"
                style="transition: stroke-dashoffset 800ms cubic-bezier(0.4,0,0.2,1)"/>
            </svg>
            <div class="absolute inset-0 flex flex-col items-center justify-center">
              <span class="text-lg font-bold text-[var(--fg)]">
                {cls.attendance_marked_today ? `${pct}%` : '—'}
              </span>
            </div>
          </div>
          <div class="min-w-0 flex-1">
            <h2 class="text-xl font-bold text-[var(--fg)] truncate">{cls.name}</h2>
            <p class="text-sm text-[var(--fg-muted)]">{cls.student_count} students enrolled</p>
            <div class="mt-2.5 flex flex-wrap gap-2">
              {#if cls.attendance_marked_today}
                <span class="inline-flex items-center gap-1 rounded-full bg-green-600 px-2.5 py-0.5 text-[11px] font-semibold text-white dark:bg-green-700">
                  <svg class="h-3 w-3" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24"><polyline points="20 6 9 17 4 12"/></svg>
                  {cls.present_today} present
                </span>
                {#if cls.absent_today > 0}
                  <span class="inline-flex items-center gap-1 rounded-full bg-red-50 dark:bg-red-950/50 px-2.5 py-0.5 text-[11px] font-semibold text-red-600 dark:text-red-400">
                    {cls.absent_today} absent
                  </span>
                {/if}
              {:else}
                <span class="inline-flex items-center gap-1.5 rounded-full bg-amber-50 dark:bg-amber-950/40 px-2.5 py-0.5 text-[11px] font-semibold text-amber-700 dark:text-amber-400">
                  <svg class="h-3 w-3" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24">
                    <circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>
                  </svg>
                  Not yet marked
                </span>
              {/if}
            </div>
          </div>
        </div>
        {#if !cls.attendance_marked_today}
          <a href="/attendance"
             class="mt-4 flex w-full items-center justify-center gap-2 rounded-xl py-2.5 text-sm font-semibold text-white transition active:scale-[0.99] hover:opacity-90"
             style="background-color: var(--brand)">
            <svg class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4"/>
            </svg>
            Mark attendance now
          </a>
        {/if}
      </div>
    {:else}
      <div class="rounded-xl border border-dashed border-[var(--border)] bg-[var(--card)] p-6 text-center text-sm text-[var(--fg-muted)]">
        No class assigned to you this term.
      </div>
    {/if}

    <!-- Stat row -->
    <div class="grid grid-cols-3 gap-3">
      <StatCard label="Pending Scores" value={data.pending_score_assessments}
        iconPath={icons.pencil}
        color="bg-blue-50 dark:bg-blue-950/40" iconColor="text-blue-600 dark:text-blue-400"
        href="/scores" alert={data.pending_score_assessments > 0} />
      <StatCard label="Absent Today" value={data.my_class?.absent_today ?? 0}
        iconPath={icons.userMinus}
        color="bg-red-50 dark:bg-red-950/40" iconColor="text-red-500 dark:text-red-400"
        href="/attendance" alert={(data.my_class?.absent_today ?? 0) > 0} />
      <StatCard label="Class Size" value={data.my_class?.student_count ?? 0}
        iconPath={icons.users}
        color="bg-indigo-50 dark:bg-indigo-950/40" iconColor="text-indigo-600 dark:text-indigo-400"
        href="/students" />
    </div>

  </div>

  <!-- RIGHT COLUMN -->
  <div class="space-y-5">

    <!-- Task list -->
    <div>
      <p class="mb-2.5 text-[11px] font-semibold uppercase tracking-widest text-[var(--fg-muted)]">Today's tasks</p>
      <div class="overflow-hidden rounded-xl border border-[var(--border)] bg-[var(--card)] divide-y divide-[var(--border)]">
        {#each tasks as task}
          <a href={task.href} class="group flex items-center gap-4 px-5 py-3.5 transition hover:bg-[var(--bg)]">
            <div class="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg
                        {task.urgent ? 'bg-amber-100 dark:bg-amber-900/40' : 'bg-gray-100 dark:bg-gray-800'}">
              {#if task.urgent}
                <span class="h-2 w-2 rounded-full bg-amber-500 animate-pulse"></span>
              {:else}
                <svg class="h-4 w-4 text-gray-400 dark:text-gray-500" fill="none" stroke="currentColor" stroke-width="1.5" viewBox="0 0 24 24">
                  <polyline points="20 6 9 17 4 12"/>
                </svg>
              {/if}
            </div>
            <div class="flex-1 min-w-0">
              <p class="text-sm font-semibold text-[var(--fg)]">{task.label}</p>
              <p class="text-[11px] {task.urgent ? 'text-amber-600 dark:text-amber-400 font-medium' : 'text-[var(--fg-muted)]'}">{task.badge}</p>
            </div>
            <svg class="h-4 w-4 text-gray-300 dark:text-gray-700 transition-transform group-hover:translate-x-0.5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
              <polyline points="9 18 15 12 9 6"/>
            </svg>
          </a>
        {/each}
      </div>
    </div>

    <!-- Absent students -->
    {#if (data.my_class?.absent_students.length ?? 0) > 0}
      <div>
        <p class="mb-2.5 text-[11px] font-semibold uppercase tracking-widest text-[var(--fg-muted)]">
          Absent today · {data.my_class!.absent_students.length}
        </p>
        <div class="overflow-hidden rounded-xl border border-[var(--border)] bg-[var(--card)] divide-y divide-[var(--border)]">
          {#each data.my_class!.absent_students as s}
            <div class="flex items-center gap-3.5 px-5 py-3">
              <span class="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-red-100 dark:bg-red-950/50 text-[11px] font-bold text-red-600 dark:text-red-400">
                {s.name.split(' ').map((p: string) => p[0]).join('').slice(0, 2).toUpperCase()}
              </span>
              <div class="min-w-0 flex-1">
                <p class="truncate text-sm font-medium text-[var(--fg)]">{s.name}</p>
                <p class="text-[11px] text-[var(--fg-muted)]">{s.admission_number}</p>
              </div>
            </div>
          {/each}
        </div>
      </div>
    {/if}

  </div>
</div>
