<script lang="ts">
  import type { TeacherDashboard } from '$lib/api/dashboard';
  import StatCard from '$lib/components/StatCard.svelte';

  interface Props { data: TeacherDashboard; }
  const { data }: Props = $props();

  function greeting(name: string): string {
    const hour = new Date().getHours();
    const salutation = hour < 12 ? 'Good morning'
      : hour < 17 ? 'Good afternoon'
      : hour < 21 ? 'Good evening'
      : 'Good night';
    return `${salutation}, ${name}`;
  }

  const todayFormatted = $derived(() =>
    new Date(data.today_iso).toLocaleDateString('en-GH', {
      weekday: 'long', day: 'numeric', month: 'long',
    })
  );

  const attendanceIcon = $derived(() =>
    data.my_class?.attendance_marked_today ? '✅' : '⚠️'
  );

  const attendanceSummary = $derived(() => {
    const cls = data.my_class;
    if (!cls) return '';
    if (!cls.attendance_marked_today) return 'Not yet marked';
    return `${cls.present_today} present · ${cls.absent_today} absent`;
  });
</script>

<!-- Greeting -->
<div class="mb-6">
  <h1 class="text-xl font-bold text-gray-900">{greeting(data.greeting_name)}</h1>
  <p class="text-sm text-gray-400">{todayFormatted()}</p>
</div>

<!-- Class status card -->
{#if data.my_class}
  {@const cls = data.my_class}
  <div class="mb-5 rounded-2xl border p-5 {cls.attendance_marked_today ? 'border-green-100 bg-green-50' : 'border-amber-100 bg-amber-50'}">
    <div class="flex items-start justify-between">
      <div>
        <p class="text-xs font-semibold uppercase tracking-widest {cls.attendance_marked_today ? 'text-green-600' : 'text-amber-600'}">
          Your class
        </p>
        <h2 class="mt-0.5 text-2xl font-bold text-gray-900">{cls.name}</h2>
        <p class="mt-0.5 text-sm text-gray-500">{cls.student_count} students enrolled</p>
      </div>
      <span class="text-3xl">{attendanceIcon()}</span>
    </div>
    <p class="mt-3 text-sm font-medium {cls.attendance_marked_today ? 'text-green-700' : 'text-amber-700'}">
      {attendanceSummary()}
    </p>
  </div>
{:else}
  <div class="mb-5 rounded-2xl border border-gray-100 bg-gray-50 p-5 text-sm text-gray-500">
    No class assigned to you for this term.
  </div>
{/if}

<!-- Stat row -->
<div class="mb-5 grid grid-cols-2 gap-3 lg:grid-cols-3">
  <StatCard
    label="Pending Scores"
    value={data.pending_score_assessments}
    icon="✏️"
    color="bg-blue-50"
    iconColor="text-blue-600"
    href="/scores"
    alert={data.pending_score_assessments > 0}
  />
  <StatCard
    label="Absent Today"
    value={data.my_class?.absent_today ?? 0}
    icon="🔴"
    color="bg-red-50"
    iconColor="text-red-500"
    href="/attendance"
    alert={(data.my_class?.absent_today ?? 0) > 0}
  />
  <StatCard
    label="Class Size"
    value={data.my_class?.student_count ?? 0}
    icon="👩‍🎓"
    color="bg-indigo-50"
    iconColor="text-indigo-600"
    href="/students"
  />
</div>

<!-- Quick actions -->
<div class="mb-6">
  <h3 class="mb-3 text-xs font-semibold uppercase tracking-widest text-gray-400">Quick actions</h3>
  <div class="grid grid-cols-2 gap-3">
    <a
      href="/attendance"
      class="flex flex-col items-center justify-center gap-2 rounded-2xl border border-gray-100 bg-white p-5 text-center transition hover:shadow-md active:scale-[0.98]"
    >
      <span class="text-2xl">📋</span>
      <span class="text-sm font-semibold text-gray-800">Mark Attendance</span>
    </a>
    <a
      href="/scores"
      class="flex flex-col items-center justify-center gap-2 rounded-2xl border border-gray-100 bg-white p-5 text-center transition hover:shadow-md active:scale-[0.98]"
    >
      <span class="text-2xl">✏️</span>
      <span class="text-sm font-semibold text-gray-800">Enter Scores</span>
    </a>
    <a
      href="/students"
      class="flex flex-col items-center justify-center gap-2 rounded-2xl border border-gray-100 bg-white p-5 text-center transition hover:shadow-md active:scale-[0.98]"
    >
      <span class="text-2xl">👩‍🎓</span>
      <span class="text-sm font-semibold text-gray-800">My Students</span>
    </a>
    <a
      href="/reports"
      class="flex flex-col items-center justify-center gap-2 rounded-2xl border border-gray-100 bg-white p-5 text-center transition hover:shadow-md active:scale-[0.98]"
    >
      <span class="text-2xl">📄</span>
      <span class="text-sm font-semibold text-gray-800">Report Cards</span>
    </a>
  </div>
</div>

<!-- Absent students list -->
{#if (data.my_class?.absent_students.length ?? 0) > 0}
  <div>
    <h3 class="mb-3 text-xs font-semibold uppercase tracking-widest text-gray-400">Absent today</h3>
    <div class="rounded-2xl border border-gray-100 bg-white overflow-hidden">
      {#each data.my_class!.absent_students as student, i}
        <div class="flex items-center gap-3 px-4 py-3 {i > 0 ? 'border-t border-gray-50' : ''}">
          <span class="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-red-100 text-xs font-bold text-red-600">
            {student.name.split(' ').map(p => p[0]).join('').slice(0, 2)}
          </span>
          <div class="min-w-0">
            <p class="truncate text-sm font-medium text-gray-800">{student.name}</p>
            <p class="text-xs text-gray-400">{student.admission_number}</p>
          </div>
        </div>
      {/each}
    </div>
  </div>
{/if}
