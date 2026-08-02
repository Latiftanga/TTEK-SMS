<script lang="ts">
  import type { TeacherDashboard } from '$lib/api/dashboard';

  interface Props { data: TeacherDashboard; }
  const { data }: Props = $props();

  const hour = new Date().getHours();
  const salutation = hour < 12 ? 'Good morning' : hour < 17 ? 'Good afternoon' : 'Good evening';

  const todayLabel = $derived(new Date(data.today_iso).toLocaleDateString('en-GH', {
    weekday: 'long', day: 'numeric', month: 'long',
  }));

  // A class teacher can hold more than one class — only the ones not yet
  // marked get the full "do this now" card treatment; already-marked classes
  // collapse into one quiet line so the page never shows more than one
  // action per class at a time.
  const hasClasses      = $derived(data.my_classes.length > 0);
  const unmarkedClasses = $derived(data.my_classes.filter(c => !c.attendance_marked_today));
  const markedClasses   = $derived(data.my_classes.filter(c => c.attendance_marked_today));
  const multipleClasses = $derived(data.my_classes.length > 1);
  const totalAbsent     = $derived(data.my_classes.reduce((n, c) => n + c.absent_today, 0));

  const absentStudents = $derived(
    data.my_classes.flatMap(c => c.absent_students.map(s => ({ ...s, className: c.name })))
  );

  // One priority action at a time, in order of urgency — everything else
  // moves to the quieter zone below instead of competing for attention.
  type Priority = 'attendance' | 'scores' | 'done' | 'no-class';
  const priority = $derived<Priority>(
    !hasClasses ? 'no-class'
    : unmarkedClasses.length > 0 ? 'attendance'
    : data.pending_score_assessments > 0 ? 'scores'
    : 'done'
  );

  let showAbsent = $state(false);
</script>

<!-- Greeting — a courtesy line, not the headline -->
<div class="mb-5">
  <h1 class="text-lg font-semibold text-[var(--fg)]">{salutation}, {data.greeting_name.split(' ')[0]}.</h1>
  <p class="text-sm text-[var(--fg-muted)]">{todayLabel}</p>
</div>

<div class="mx-auto max-w-2xl space-y-3">

  {#if priority === 'attendance'}
    <!-- ── HERO: mark attendance ─────────────────────────────────────────── -->
    {#each unmarkedClasses as cls (cls.id)}
      <div class="rounded-2xl border border-[var(--border)] bg-[var(--card)] p-6 text-center" style="box-shadow: var(--shadow-sm)">
        <p class="text-xs font-semibold uppercase tracking-wide text-[var(--fg-subtle)]">Today's task</p>
        <h2 class="mt-1 text-2xl font-bold text-[var(--fg)]">{cls.name}</h2>
        <p class="mt-1 text-base text-[var(--fg-muted)]">{cls.student_count} students · attendance not marked yet</p>
        <a href="/attendance"
           class="mt-5 flex min-h-[44px] w-full items-center justify-center gap-2 rounded-xl py-3 text-base font-semibold text-white transition active:scale-[0.98] hover:opacity-90"
           style="background-color: var(--brand)">
          <svg class="h-5 w-5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4"/>
          </svg>
          Mark attendance
        </a>
      </div>
    {/each}
    {#if markedClasses.length > 0}
      <p class="flex items-center gap-1.5 px-1 text-sm text-[var(--fg-muted)]">
        <svg class="h-4 w-4 text-green-600 dark:text-green-500" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24"><polyline points="20 6 9 17 4 12"/></svg>
        {markedClasses.length === 1 ? `${markedClasses[0].name} already marked` : `${markedClasses.length} other classes already marked`}
      </p>
    {/if}

  {:else if priority === 'scores'}
    <!-- ── HERO: enter scores ────────────────────────────────────────────── -->
    <div class="rounded-2xl border border-[var(--border)] bg-[var(--card)] p-6 text-center" style="box-shadow: var(--shadow-sm)">
      <p class="text-xs font-semibold uppercase tracking-wide text-[var(--fg-subtle)]">Today's task</p>
      <h2 class="mt-1 text-2xl font-bold text-[var(--fg)]">Enter scores</h2>
      <p class="mt-1 text-base text-[var(--fg-muted)]">
        {data.pending_score_assessments} assessment{data.pending_score_assessments === 1 ? '' : 's'} waiting
      </p>
      <a href="/assessments"
         class="mt-5 flex min-h-[44px] w-full items-center justify-center gap-2 rounded-xl py-3 text-base font-semibold text-white transition active:scale-[0.98] hover:opacity-90"
         style="background-color: var(--brand)">
        <svg class="h-5 w-5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z"/>
        </svg>
        Enter scores
      </a>
    </div>
    <p class="flex items-center gap-1.5 px-1 text-sm text-[var(--fg-muted)]">
      <svg class="h-4 w-4 text-green-600 dark:text-green-500" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24"><polyline points="20 6 9 17 4 12"/></svg>
      Attendance marked for today
    </p>

  {:else if priority === 'done'}
    <!-- ── All caught up ─────────────────────────────────────────────────── -->
    <div class="rounded-2xl border border-[var(--border)] bg-[var(--card)] p-8 text-center" style="box-shadow: var(--shadow-sm)">
      <svg class="mx-auto h-12 w-12 text-green-600 dark:text-green-500" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
        <circle cx="12" cy="12" r="10"/><polyline points="8 12.5 11 15.5 16 9"/>
      </svg>
      <h2 class="mt-3 text-xl font-bold text-[var(--fg)]">You're all caught up</h2>
      <p class="mt-1 text-sm text-[var(--fg-muted)]">Attendance is marked and there are no scores waiting.</p>
    </div>

  {:else}
    <!-- ── No class assigned — nothing to claim "done" here, this dashboard
         doesn't track subject-only teaching workload ─────────────────────── -->
    <div class="rounded-2xl border border-dashed border-[var(--border)] bg-[var(--card)] p-8 text-center">
      <h2 class="text-lg font-semibold text-[var(--fg)]">No class assigned to you this term</h2>
      <p class="mt-1 text-sm text-[var(--fg-muted)]">If you teach a subject, go to Assessments to enter scores.</p>
      <a href="/assessments"
         class="mt-4 inline-flex items-center justify-center gap-2 rounded-xl px-5 py-3 text-base font-semibold text-white transition hover:opacity-90"
         style="background-color: var(--brand)">
        Go to Assessments
      </a>
    </div>
  {/if}

  <!-- ── Quieter zone: everything else, one tap away ─────────────────────── -->
  {#if hasClasses}
    <div class="mt-2 overflow-hidden rounded-xl border border-[var(--border)] divide-y divide-[var(--border)]">
      <a href="/students" class="flex items-center justify-between gap-3 px-4 py-3 text-sm transition hover:bg-[var(--hover)]">
        <span class="font-medium text-[var(--fg)]">My Students</span>
        <span class="text-[var(--fg-muted)]">View &amp; register →</span>
      </a>
      <a href="/reports" class="flex items-center justify-between gap-3 px-4 py-3 text-sm transition hover:bg-[var(--hover)]">
        <span class="font-medium text-[var(--fg)]">Reports</span>
        <span class="text-[var(--fg-muted)]">View &amp; download →</span>
      </a>
    </div>
  {/if}

  <!-- ── Absent today — collapsed by default, one tap to see names ───────── -->
  {#if absentStudents.length > 0}
    <div class="overflow-hidden rounded-xl border border-[var(--border)]">
      <button onclick={() => showAbsent = !showAbsent}
        class="flex w-full items-center justify-between gap-3 px-4 py-3 text-sm transition hover:bg-[var(--hover)]">
        <span class="font-medium text-[var(--fg)]">Absent today · {totalAbsent}</span>
        <svg class="h-4 w-4 shrink-0 text-[var(--fg-subtle)] transition-transform duration-150 {showAbsent ? 'rotate-90' : ''}"
          fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" d="M9 5l7 7-7 7"/>
        </svg>
      </button>
      {#if showAbsent}
        <div class="divide-y divide-[var(--border)] border-t border-[var(--border)]">
          {#each absentStudents as s}
            <div class="flex items-center gap-3 px-4 py-2.5">
              <span class="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-red-100 dark:bg-red-950/50 text-xs font-bold text-red-600 dark:text-red-400">
                {s.name.split(' ').map((p: string) => p[0]).join('').slice(0, 2).toUpperCase()}
              </span>
              <div class="min-w-0 flex-1">
                <p class="truncate text-sm font-medium text-[var(--fg)]">{s.name}</p>
                <p class="text-xs text-[var(--fg-muted)]">
                  {s.admission_number}{multipleClasses ? ` · ${s.className}` : ''}
                </p>
              </div>
            </div>
          {/each}
        </div>
      {/if}
    </div>
  {/if}

</div>
