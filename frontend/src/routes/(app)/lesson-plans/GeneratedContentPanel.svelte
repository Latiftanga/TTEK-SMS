<script lang="ts">
  import { createMutation, useQueryClient } from '@tanstack/svelte-query';
  import { reactiveQuery } from '$lib/query.svelte';
  import {
    generateSkeleton, generateLessons, regenerateLesson, regenerateAssessment, listChatMessages,
    type LessonPlan,
  } from '$lib/api/lessonPlans';
  import { apiError } from '$lib/utils';
  import { toast } from '$lib/stores/toast';
  import { isOnline } from '$lib/offline/sync';

  interface Props {
    plan: LessonPlan;
    classId: string; subjectId: string; academicTermId: string; weekStart: string;
  }
  const { plan, classId, subjectId, academicTermId, weekStart }: Props = $props();

  // Same cache key ChatPanel.svelte's own message query already uses — a
  // teacher actively chatting shouldn't also be offered a second, competing
  // "Generate skeleton" entry point; TanStack Query dedupes this against
  // ChatPanel's fetch rather than doubling the request.
  const chatMessagesQ = reactiveQuery(() => ({
    queryKey: ['lesson-plan-chat', plan.id] as const,
    queryFn: () => listChatMessages(plan.id),
    staleTime: 10_000,
  }));
  const hasChatMessages = $derived(($chatMessagesQ.data ?? []).length > 0);

  const content = $derived(plan.generated_content);
  // A plan finalized via ChatPanel (services/lesson_plan_chat.py::finalize_chat)
  // sets lessons/assessment directly and never populates essential_questions —
  // treat having real lessons as "has a skeleton" too, or a chat-built plan
  // renders as if it had nothing in it.
  const hasSkeleton = $derived(
    !!content && (content.essential_questions.length > 0 || content.lessons.length > 0),
  );
  const hasLessons = $derived(!!content && content.lessons.length > 0);

  const qc = useQueryClient();
  function invalidate() {
    qc.invalidateQueries({ queryKey: ['lesson-plans', classId, subjectId, academicTermId, weekStart] });
  }

  const skeletonMut = createMutation({
    mutationFn: () => generateSkeleton(plan.id),
    onSuccess: () => { invalidate(); toast.success('Skeleton generated — review it, then expand into lessons.'); },
    onError: (e: unknown) => toast.error(apiError(e, 'Could not generate a skeleton.')),
  });

  function statusOf(e: unknown): number | undefined {
    return (e as { response?: { status?: number } })?.response?.status;
  }
  function errorCodeOf(e: unknown): string | undefined {
    return (e as { response?: { headers?: Record<string, string> } })?.response?.headers?.['x-error-code'];
  }

  // Only ever surfaces when this class+subject genuinely has no real
  // timetable for this week (services/lesson_plan_occurrences.py::
  // get_occurrences_or_require_count) — a real timetable's count always
  // stays authoritative with no prompt at all.
  let needsLessonCount = $state(false);
  let lessonCount = $state(3);
  const lessonsMut = createMutation({
    mutationFn: (count?: number) => generateLessons(plan.id, count),
    onSuccess: () => { invalidate(); needsLessonCount = false; toast.success('Lessons generated.'); },
    onError: (e: unknown) => {
      if (statusOf(e) === 422 && errorCodeOf(e) === 'lesson_count_required') { needsLessonCount = true; return; }
      toast.error(apiError(e, 'Could not generate lessons.'));
    },
  });

  function lessonKey(lesson: { school_calendar_id: string | null; period_id: string | null; sequence_index: number | null }): string {
    return lesson.school_calendar_id && lesson.period_id
      ? `${lesson.school_calendar_id}::${lesson.period_id}`
      : `seq::${lesson.sequence_index}`;
  }

  let regeneratingKey = $state<string | null>(null);
  const regenLessonMut = createMutation({
    mutationFn: (vars: { calId: string; periodId: string } | { sequenceIndex: number }) =>
      'sequenceIndex' in vars
        ? regenerateLesson(plan.id, { sequenceIndex: vars.sequenceIndex })
        : regenerateLesson(plan.id, { schoolCalendarId: vars.calId, periodId: vars.periodId }),
    onSuccess: () => { invalidate(); toast.success('Lesson regenerated.'); },
    onError: (e: unknown) => toast.error(apiError(e, 'Could not regenerate this lesson.')),
    onSettled: () => { regeneratingKey = null; },
  });

  const regenAssessmentMut = createMutation({
    mutationFn: () => regenerateAssessment(plan.id),
    onSuccess: () => { invalidate(); toast.success('Assessment regenerated.'); },
    onError: (e: unknown) => toast.error(apiError(e, 'Could not regenerate the assessment.')),
  });

  function fmtDate(iso: string): string {
    return new Date(iso).toLocaleDateString('en-GH', { weekday: 'short', day: 'numeric', month: 'short' });
  }
</script>

<!-- Once a real conversation is underway, "Generate lesson plan from this
     conversation" (ChatPanel, above) is the one obvious next action — a
     second, independent "Generate skeleton" entry point here would just be
     a confusing, competing way to do the same thing. This panel only
     re-appears, still chat-driven, once real content actually exists. -->
{#if hasSkeleton || !hasChatMessages}
<div class="mt-6 space-y-4 rounded-2xl border border-[var(--border)] bg-[var(--card)] p-5">
  <div class="flex items-center justify-between gap-2">
    <h3 class="text-sm font-semibold text-[var(--fg)]">AI-assisted plan</h3>
    {#if !$isOnline}
      <span class="text-xs font-medium text-[var(--fg-muted)]">Offline — connect to generate</span>
    {/if}
  </div>

  {#if !hasSkeleton}
    <p class="text-xs text-[var(--fg-muted)]">
      Generate essential questions, teaching strategies, and resources first — a cheap-to-iterate
      outline you can review before expanding into full lessons. (Prefer to just describe the
      lesson instead? Chat above and use "Generate lesson plan from this conversation" there.)
    </p>
    <button onclick={() => $skeletonMut.mutate()} disabled={$skeletonMut.isPending || !$isOnline}
      class="min-h-[44px] rounded-xl px-4 py-2 text-sm font-semibold text-white transition hover:opacity-90 disabled:opacity-50"
      style="background: var(--brand)">
      {$skeletonMut.isPending ? 'Generating…' : '✨ Generate skeleton'}
    </button>
  {:else}
    <div class="space-y-3">
      {#if content!.essential_questions.length > 0}
        <div>
          <p class="lbl">Essential questions</p>
          <ul class="mt-1 list-disc space-y-0.5 pl-5 text-sm text-[var(--fg)]">
            {#each content!.essential_questions as q}<li>{q}</li>{/each}
          </ul>
        </div>
      {/if}
      {#if content!.pedagogical_strategies.length > 0}
        <div>
          <p class="lbl">Pedagogical strategies</p>
          <ul class="mt-1 list-disc space-y-0.5 pl-5 text-sm text-[var(--fg)]">
            {#each content!.pedagogical_strategies as s}<li>{s}</li>{/each}
          </ul>
        </div>
      {/if}
      {#if content!.teaching_learning_resources.length > 0}
        <div>
          <p class="lbl">Teaching & learning resources</p>
          <ul class="mt-1 list-disc space-y-0.5 pl-5 text-sm text-[var(--fg)]">
            {#each content!.teaching_learning_resources as r}<li>{r}</li>{/each}
          </ul>
        </div>
      {/if}
      {#if content!.differentiation_notes}
        <div>
          <p class="lbl">Differentiation notes</p>
          <p class="mt-1 text-sm text-[var(--fg)]">{content!.differentiation_notes}</p>
        </div>
      {/if}
      <button onclick={() => $skeletonMut.mutate()} disabled={$skeletonMut.isPending || !$isOnline}
        class="min-h-[44px] rounded-xl border border-[var(--border)] px-3 text-xs font-semibold text-[var(--fg-muted)] transition hover:bg-[var(--hover)] disabled:opacity-50">
        {$skeletonMut.isPending ? 'Regenerating…' : 'Regenerate skeleton'}
      </button>
    </div>

    <div class="border-t border-[var(--border)] pt-4">
      {#if !hasLessons}
        {#if needsLessonCount}
          <div class="space-y-2 rounded-xl border border-amber-200 bg-amber-50 p-3 dark:border-amber-900 dark:bg-amber-950/30">
            <p class="text-xs text-amber-700 dark:text-amber-400">
              No real scheduled lessons found on the timetable for this class/subject this week —
              how many lessons would you like to plan?
            </p>
            <div class="flex items-center gap-2">
              <input type="number" min="1" max="20" bind:value={lessonCount} inputmode="numeric"
                class="w-20 rounded-lg border border-[var(--border)] bg-[var(--bg)] px-2 py-1.5 text-sm text-[var(--fg)]" />
              <button onclick={() => $lessonsMut.mutate(lessonCount)} disabled={$lessonsMut.isPending || !$isOnline}
                class="min-h-[36px] rounded-lg px-3 text-xs font-semibold text-white disabled:opacity-50" style="background: var(--brand)">
                {$lessonsMut.isPending ? 'Generating…' : 'Generate'}
              </button>
            </div>
          </div>
        {:else}
          <button onclick={() => $lessonsMut.mutate(undefined)} disabled={$lessonsMut.isPending || !$isOnline}
            class="min-h-[44px] rounded-xl px-4 py-2 text-sm font-semibold text-white transition hover:opacity-90 disabled:opacity-50"
            style="background: var(--brand)">
            {$lessonsMut.isPending ? 'Expanding…' : 'Expand into lessons →'}
          </button>
        {/if}
      {:else}
        {#if content!.generation_warnings.length > 0}
          <div class="mb-3 rounded-xl border border-amber-200 bg-amber-50 px-4 py-2.5 text-xs text-amber-700 dark:border-amber-900 dark:bg-amber-950/30 dark:text-amber-400">
            {#each content!.generation_warnings as w}<p>{w}</p>{/each}
          </div>
        {/if}
        <div class="space-y-3">
          {#each content!.lessons as lesson (lessonKey(lesson))}
            {@const key = lessonKey(lesson)}
            <div class="rounded-xl border border-[var(--border)] p-3">
              <div class="flex items-center justify-between gap-2">
                <p class="text-xs font-semibold text-[var(--fg)]">
                  {#if lesson.lesson_date && lesson.start_time && lesson.end_time}
                    {fmtDate(lesson.lesson_date)} · {lesson.start_time.slice(0, 5)}–{lesson.end_time.slice(0, 5)}
                  {:else}
                    Lesson {lesson.sequence_index}
                  {/if}
                </p>
                <button
                  onclick={() => {
                    regeneratingKey = key;
                    if (lesson.school_calendar_id && lesson.period_id) {
                      $regenLessonMut.mutate({ calId: lesson.school_calendar_id, periodId: lesson.period_id });
                    } else {
                      $regenLessonMut.mutate({ sequenceIndex: lesson.sequence_index! });
                    }
                  }}
                  disabled={$regenLessonMut.isPending || !$isOnline}
                  class="min-h-[32px] rounded-lg border border-[var(--border)] px-2 text-[11px] font-semibold text-[var(--fg-muted)] transition hover:bg-[var(--hover)] disabled:opacity-50">
                  {regeneratingKey === key && $regenLessonMut.isPending ? 'Regenerating…' : 'Regenerate'}
                </button>
              </div>
              <div class="mt-2 space-y-1.5 text-sm text-[var(--fg)]">
                <p><span class="font-medium">Introduction:</span> {lesson.introduction}</p>
                <p><span class="font-medium">Main lesson:</span> {lesson.main_lesson}</p>
                <p><span class="font-medium">Closure:</span> {lesson.closure}</p>
              </div>
            </div>
          {/each}
        </div>

        {#if content!.assessment}
          <div class="mt-3 rounded-xl border border-[var(--border)] p-3">
            <div class="flex items-center justify-between gap-2">
              <p class="text-xs font-semibold text-[var(--fg)]">Assessment</p>
              <button onclick={() => $regenAssessmentMut.mutate()} disabled={$regenAssessmentMut.isPending || !$isOnline}
                class="min-h-[32px] rounded-lg border border-[var(--border)] px-2 text-[11px] font-semibold text-[var(--fg-muted)] transition hover:bg-[var(--hover)] disabled:opacity-50">
                {$regenAssessmentMut.isPending ? 'Regenerating…' : 'Regenerate'}
              </button>
            </div>
            <div class="mt-2 grid gap-3 sm:grid-cols-2">
              <div class="text-sm text-[var(--fg)]">
                <p class="lbl">Formative</p>
                <p><span class="font-medium">Mode:</span> {content!.assessment.formative.mode}</p>
                <p><span class="font-medium">Task:</span> {content!.assessment.formative.task}</p>
                <p><span class="font-medium">Mark scheme:</span> {content!.assessment.formative.mark_scheme}</p>
              </div>
              <div class="text-sm text-[var(--fg)]">
                <p class="lbl">Transcript assessment</p>
                <p><span class="font-medium">Mode:</span> {content!.assessment.transcript_assessment.mode}</p>
                <p><span class="font-medium">Task:</span> {content!.assessment.transcript_assessment.task}</p>
                <p><span class="font-medium">Rubric:</span> {content!.assessment.transcript_assessment.rubric}</p>
              </div>
            </div>
          </div>
        {/if}
      {/if}
    </div>
  {/if}
</div>
{/if}

<style>
  @reference "tailwindcss";
  .lbl { @apply text-xs font-medium text-[var(--fg-muted)]; }
</style>
