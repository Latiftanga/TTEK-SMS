<script lang="ts">
  import { createQuery } from '@tanstack/svelte-query';
  import { reactiveQuery } from '$lib/query.svelte';
  import { page } from '$app/stores';
  import { goto } from '$app/navigation';
  import { listMySubjects } from '$lib/api/assessments';
  import { listLessonPlans } from '$lib/api/lessonPlans';
  import { listYears } from '$lib/api/academic';
  import { resolveDefaultTerm } from '$lib/academicPeriod';
  import { setPageTitle } from '$lib/stores/title';
  import PageHeader from '$lib/components/PageHeader.svelte';
  import LessonPlanForm from './LessonPlanForm.svelte';
  import GeneratedContentPanel from './GeneratedContentPanel.svelte';
  import ChatPanel from './ChatPanel.svelte';
  import ReviewPanel from './ReviewPanel.svelte';
  setPageTitle('Lesson Plans');

  // ── Filters — persisted in the URL, same convention as /assessments ──────────
  const sp       = $derived($page.url.searchParams);
  const classId    = $derived(sp.get('class')   ?? '');
  const subjectId  = $derived(sp.get('subject') ?? '');
  const termId     = $derived(sp.get('term')    ?? '');
  const weekParam  = $derived(sp.get('week')    ?? '');

  function setFilter(key: string, value: string) {
    const url = new URL($page.url);
    if (value) url.searchParams.set(key, value);
    else       url.searchParams.delete(key);
    goto(url.toString(), { replaceState: true, noScroll: true });
  }
  function setClassSubject(classIdVal: string, subjectIdVal: string) {
    const url = new URL($page.url);
    if (classIdVal)   url.searchParams.set('class', classIdVal);   else url.searchParams.delete('class');
    if (subjectIdVal) url.searchParams.set('subject', subjectIdVal); else url.searchParams.delete('subject');
    goto(url.toString(), { replaceState: true, noScroll: true });
  }

  const yearsQ = createQuery({ queryKey: ['academic-years'], queryFn: listYears, staleTime: 5 * 60_000 });
  const allTerms = $derived(($yearsQ.data ?? []).flatMap(y => y.terms.map(t => ({ ...t, yearName: y.name }))));

  // Browsing/picker context, not operational data entry — planning ahead for
  // a future term (or adding reflection notes to a past one) is a legitimate
  // use of a personal planner, so this defaults to current-else-latest
  // rather than never-guess (see lib/academicPeriod.ts's own doc comment on
  // the distinction).
  $effect(() => {
    const def = resolveDefaultTerm(allTerms);
    if (def && !termId) setFilter('term', def.id);
  });

  // (class, subject) combos the caller teaches — same data /assessments
  // already fetches via /assessments/my-subjects, reused as-is rather than
  // duplicating a picker endpoint.
  const mySubjectsQ = reactiveQuery(() => ({
    queryKey: ['my-subjects', termId] as const,
    queryFn:  () => listMySubjects(termId),
    enabled:  !!termId,
    staleTime: 5 * 60_000,
  }));
  const myClassSubjectPairs = $derived(
    [...($mySubjectsQ.data ?? [])].sort((a, b) =>
      a.class_name.localeCompare(b.class_name) || a.subject_name.localeCompare(b.subject_name)
    )
  );
  const pairKey = (p: { class_id: string; subject_id: string }) => `${p.class_id}::${p.subject_id}`;
  const selectedPairKey = $derived(classId && subjectId ? `${classId}::${subjectId}` : '');

  $effect(() => {
    if (myClassSubjectPairs.length === 1 && !classId) {
      const only = myClassSubjectPairs[0];
      setClassSubject(only.class_id, only.subject_id);
    }
  });

  // ── Week navigator ────────────────────────────────────────────────────────────
  function mondayOf(d: Date): Date {
    const copy = new Date(d);
    const day = copy.getDay(); // 0=Sun..6=Sat
    const diff = day === 0 ? -6 : 1 - day;
    copy.setDate(copy.getDate() + diff);
    copy.setHours(0, 0, 0, 0);
    return copy;
  }
  function toIso(d: Date): string { return d.toISOString().slice(0, 10); }

  const weekStart = $derived(weekParam ? toIso(mondayOf(new Date(weekParam))) : toIso(mondayOf(new Date())));

  $effect(() => {
    if (!weekParam) setFilter('week', weekStart);
  });

  function shiftWeek(days: number) {
    const d = new Date(weekStart);
    d.setDate(d.getDate() + days);
    setFilter('week', toIso(mondayOf(d)));
  }

  function fmtWeek(iso: string): string {
    const start = new Date(iso);
    const end = new Date(start);
    end.setDate(end.getDate() + 4); // Mon–Fri, the school week
    const opts: Intl.DateTimeFormatOptions = { day: 'numeric', month: 'short' };
    return `${start.toLocaleDateString('en-GH', opts)} – ${end.toLocaleDateString('en-GH', opts)}`;
  }

  // ── This week's plan (at most one, per the class+subject+week uniqueness) ───
  const plansQ = reactiveQuery(() => ({
    queryKey: ['lesson-plans', classId, subjectId, termId, weekStart] as const,
    queryFn:  () => listLessonPlans(classId, subjectId, termId, weekStart),
    enabled:  !!(classId && subjectId && termId && weekStart),
    staleTime: 30_000,
  }));
  const existingPlan = $derived(($plansQ.data ?? [])[0] ?? null);
</script>

<PageHeader title="Lesson Plans" description="Plan your teaching week by week — a personal planner, no approval needed." />

<div class="mb-4 flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-end">
  <div class="sm:w-64">
    <label for="lp-class-subject" class="label">Class & subject</label>
    <select id="lp-class-subject" value={selectedPairKey}
      onchange={e => {
        const [c, s] = e.currentTarget.value.split('::');
        setClassSubject(c ?? '', s ?? '');
      }} class="sel">
      <option value="">Select class & subject…</option>
      {#each myClassSubjectPairs as p (pairKey(p))}
        <option value={pairKey(p)}>{p.class_name} — {p.subject_name}</option>
      {/each}
    </select>
  </div>

  <div class="flex items-center gap-2">
    <button onclick={() => shiftWeek(-7)} aria-label="Previous week"
      class="flex h-11 w-11 items-center justify-center rounded-xl border border-[var(--border)] text-[var(--fg-muted)] transition hover:bg-[var(--hover)]">
      <svg class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" d="M15 19l-7-7 7-7"/>
      </svg>
    </button>
    <div class="min-w-[140px] text-center">
      <p class="text-xs font-medium text-[var(--fg-muted)]">Week of</p>
      <p class="text-sm font-semibold text-[var(--fg)]">{fmtWeek(weekStart)}</p>
    </div>
    <button onclick={() => shiftWeek(7)} aria-label="Next week"
      class="flex h-11 w-11 items-center justify-center rounded-xl border border-[var(--border)] text-[var(--fg-muted)] transition hover:bg-[var(--hover)]">
      <svg class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" d="M9 5l7 7-7 7"/>
      </svg>
    </button>
  </div>
</div>

{#if !classId || !subjectId}
  <div class="rounded-2xl border border-dashed border-[var(--border)] px-6 py-14 text-center">
    <p class="text-sm font-medium text-[var(--fg-muted)]">Select a class & subject to plan your week.</p>
  </div>
{:else if !termId}
  <div class="rounded-2xl border border-dashed border-[var(--border)] px-6 py-14 text-center">
    <p class="text-sm font-medium text-[var(--fg-muted)]">No academic term is set — check with your administrator.</p>
  </div>
{:else if $plansQ.isPending}
  <div class="h-64 animate-pulse rounded-2xl bg-[var(--card)]"></div>
{:else}
  <LessonPlanForm
    {classId} {subjectId} academicTermId={termId} {weekStart}
    plan={existingPlan}
  />
  {#if existingPlan}
    <ChatPanel
      plan={existingPlan} {classId} {subjectId} academicTermId={termId} {weekStart}
    />
    <GeneratedContentPanel
      plan={existingPlan} {classId} {subjectId} academicTermId={termId} {weekStart}
    />
    <ReviewPanel
      plan={existingPlan} {classId} {subjectId} academicTermId={termId} {weekStart}
    />
  {/if}
{/if}

<style>
  @reference "tailwindcss";
  .label { @apply block text-xs font-medium text-[var(--fg-muted)] mb-1; }
  .sel   { @apply w-full min-h-[44px] rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--fg)] focus:border-[var(--brand)] focus:outline-none transition; }
</style>
