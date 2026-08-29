<script lang="ts">
  // Greeting + pending pill, then a two-column detail section (My Classes/
  // Subjects/Houses/Quick Links). Every grid here is a fixed, deterministic
  // template — never auto-fit/minmax, which stretches/shrinks cards
  // unevenly based on container size and item count instead of aligning
  // them into columns.
  import type { StaffDashboard } from '$lib/api/dashboard';
  import MyClassesCard from './MyClassesCard.svelte';
  import MySubjectsCard from './MySubjectsCard.svelte';
  import MyHousesCard from './MyHousesCard.svelte';
  import MyScheduleCard from './MyScheduleCard.svelte';
  import QuickLinksCard from './QuickLinksCard.svelte';

  interface Props { data: StaffDashboard; }
  const { data }: Props = $props();

  const hour = new Date().getHours();
  const salutation = hour < 12 ? 'Good morning' : hour < 17 ? 'Good afternoon' : 'Good evening';
  const todayLabel = $derived(new Date(data.today_iso).toLocaleDateString('en-GH', {
    weekday: 'long', day: 'numeric', month: 'long',
  }));

  // Every one of these can be true at once — a class teacher who also
  // subject-teaches elsewhere and runs a house sees all three sections,
  // not just whichever "won" a seniority pick.
  const hasClasses  = $derived(data.my_classes.length > 0);
  const hasSubjects = $derived(data.my_subjects.length > 0);
  const hasHouses   = $derived(data.my_houses.length > 0);
  const hasAnything = $derived(hasClasses || hasSubjects || hasHouses);
  // Only meaningful for someone who actually teaches (homeroom or subject) —
  // a housemaster-only login has nothing to teach tomorrow at all.
  const showSchedule = $derived(hasClasses || hasSubjects);

  const unmarkedClasses = $derived(data.my_classes.filter(c => !c.attendance_marked_today));
  const multipleClasses = $derived(data.my_classes.length > 1);
  const totalAbsent     = $derived(data.my_classes.reduce((n, c) => n + c.absent_today, 0));

  const combinedPendingScores = $derived(
    data.pending_score_assessments + data.my_subjects.reduce((n, s) => n + s.pending_score_assessments, 0)
  );

  const totalPendingExeats = $derived(data.my_houses.reduce((n, h) => n + h.pending_exeats, 0));
  const housesNeedingReview = $derived(data.my_houses.filter(h => h.pending_exeats > 0));
  const exeatHref = $derived(
    housesNeedingReview.length === 1 ? `/housing/${housesNeedingReview[0].id}?tab=exeats` : '/housing'
  );

  const absentStudents = $derived(
    data.my_classes.flatMap(c => c.absent_students.map(s => ({ ...s, className: c.name })))
  );

  // One priority action at a time, in order of urgency — the hero and the
  // header pill both key off this single value so they never disagree.
  type Priority = 'attendance' | 'scores' | 'exeats' | 'done' | 'nothing';
  const priority = $derived<Priority>(
    !hasAnything ? 'nothing'
    : unmarkedClasses.length > 0 ? 'attendance'
    : combinedPendingScores > 0 ? 'scores'
    : totalPendingExeats > 0 ? 'exeats'
    : 'done'
  );

  const actionCount = $derived(
    priority === 'attendance' ? unmarkedClasses.length
    : priority === 'scores' ? combinedPendingScores
    : priority === 'exeats' ? totalPendingExeats
    : 0
  );
  const actionHref = $derived(
    priority === 'attendance' ? '/attendance' : priority === 'scores' ? '/assessments' : exeatHref
  );
  const actionLabel = $derived(
    priority === 'attendance' ? `${actionCount} class${actionCount === 1 ? '' : 'es'} to mark`
    : priority === 'scores' ? `${actionCount} score${actionCount === 1 ? '' : 's'} waiting`
    : `${actionCount} exeat${actionCount === 1 ? '' : 's'} to review`
  );

  let showAbsent = $state(false);
</script>

<!-- Greeting -->
<!-- Bounded, centered content width — without this the page was a small
     island of cards adrift in empty space on a wide screen, since the
     card grids below cap individual card width rather than stretching to
     fill whatever the browser happens to be. -->
<div class="mx-auto max-w-5xl">

<div class="mb-6 flex items-start justify-between gap-4">
  <div>
    <h1 class="text-2xl font-bold tracking-tight text-[var(--fg)]">
      {salutation}, {data.greeting_name.split(' ')[0]}.
    </h1>
    <p class="mt-0.5 text-sm text-[var(--fg-muted)]">{todayLabel}</p>
  </div>
  {#if actionCount > 0}
    <a href={actionHref}
       class="flex shrink-0 items-center gap-1.5 rounded-full border border-amber-200 dark:border-amber-700
              bg-amber-50 dark:bg-amber-950/40 px-3 py-1.5 text-xs font-semibold
              text-amber-700 dark:text-amber-400 transition hover:bg-amber-100 dark:hover:bg-amber-900/60">
      <span class="h-1.5 w-1.5 rounded-full bg-amber-500 animate-pulse"></span>
      {actionLabel}
    </a>
  {/if}
</div>

<!-- Detail section — MyClassesCard is the one "hero"-shaped card here (rich
     content, own bordered box — same role as AdminView's "Attendance by
     class"); My Subjects/Houses/QuickLinks are all the same shape (short
     header + list). Branch on which cards are actually present rather than
     one generic grid, so each combination gets a deterministic, correctly
     proportioned layout instead of auto-fit stretching cards to fill space. -->
{#if hasAnything}
  {#if showSchedule}
    <div class="mx-auto mb-6 max-w-2xl">
      <MyScheduleCard schedule={data.tomorrow_schedule} isSchoolDay={data.tomorrow_is_school_day} />
    </div>
  {/if}
  {#if hasClasses}
    <div class="grid grid-cols-1 gap-6 xl:grid-cols-[3fr_2fr]">
      <MyClassesCard classes={data.my_classes} />
      <div class="space-y-6">
        {#if hasSubjects}<MySubjectsCard subjects={data.my_subjects} />{/if}
        {#if hasHouses}<MyHousesCard houses={data.my_houses} />{/if}
        <QuickLinksCard />
      </div>
    </div>

  {:else if hasSubjects && hasHouses}
    <div class="grid grid-cols-1 gap-6 md:grid-cols-2">
      <MySubjectsCard subjects={data.my_subjects} />
      <MyHousesCard houses={data.my_houses} />
    </div>

  {:else if hasSubjects}
    <div class="mx-auto max-w-2xl">
      <MySubjectsCard subjects={data.my_subjects} />
    </div>

  {:else if hasHouses}
    <div class="mx-auto max-w-2xl">
      <MyHousesCard houses={data.my_houses} />
    </div>
  {/if}
{:else}
  <div class="mx-auto max-w-2xl rounded-[1.5rem] border border-dashed border-[var(--border)] bg-[var(--card)] p-8 text-center">
    <h2 class="text-lg font-semibold text-[var(--fg)]">Nothing assigned to you yet this term</h2>
    <p class="mt-1 text-sm text-[var(--fg-muted)]">Once you're assigned a class, subject, or house, it'll show up here.</p>
  </div>
{/if}

<!-- Absent today — collapsed by default, one tap to see names -->
{#if absentStudents.length > 0}
  <div class="mx-auto mt-6 max-w-2xl overflow-hidden rounded-[1.25rem] border border-[var(--border)]">
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
