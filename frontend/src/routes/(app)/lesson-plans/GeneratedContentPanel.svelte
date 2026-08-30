<script lang="ts">
  import { createMutation, useQueryClient } from '@tanstack/svelte-query';
  import {
    generateSkeleton, generateLessons, regenerateLesson, regenerateAssessment,
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

  const content = $derived(plan.generated_content);
  const hasSkeleton = $derived(!!content && content.essential_questions.length > 0);
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

  const lessonsMut = createMutation({
    mutationFn: () => generateLessons(plan.id),
    onSuccess: () => { invalidate(); toast.success('Lessons generated.'); },
    onError: (e: unknown) => toast.error(apiError(e, 'Could not generate lessons.')),
  });

  let regeneratingKey = $state<string | null>(null);
  const regenLessonMut = createMutation({
    mutationFn: (vars: { calId: string; periodId: string }) => regenerateLesson(plan.id, vars.calId, vars.periodId),
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
      outline you can review before expanding into full lessons.
    </p>
    <button onclick={() => $skeletonMut.mutate()} disabled={$skeletonMut.isPending || !$isOnline}
      class="min-h-[44px] rounded-xl px-4 py-2 text-sm font-semibold text-white transition hover:opacity-90 disabled:opacity-50"
      style="background: var(--brand)">
      {$skeletonMut.isPending ? 'Generating…' : '✨ Generate skeleton'}
    </button>
  {:else}
    <div class="space-y-3">
      <div>
        <p class="lbl">Essential questions</p>
        <ul class="mt-1 list-disc space-y-0.5 pl-5 text-sm text-[var(--fg)]">
          {#each content!.essential_questions as q}<li>{q}</li>{/each}
        </ul>
      </div>
      <div>
        <p class="lbl">Pedagogical strategies</p>
        <ul class="mt-1 list-disc space-y-0.5 pl-5 text-sm text-[var(--fg)]">
          {#each content!.pedagogical_strategies as s}<li>{s}</li>{/each}
        </ul>
      </div>
      <div>
        <p class="lbl">Teaching & learning resources</p>
        <ul class="mt-1 list-disc space-y-0.5 pl-5 text-sm text-[var(--fg)]">
          {#each content!.teaching_learning_resources as r}<li>{r}</li>{/each}
        </ul>
      </div>
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
        <button onclick={() => $lessonsMut.mutate()} disabled={$lessonsMut.isPending || !$isOnline}
          class="min-h-[44px] rounded-xl px-4 py-2 text-sm font-semibold text-white transition hover:opacity-90 disabled:opacity-50"
          style="background: var(--brand)">
          {$lessonsMut.isPending ? 'Expanding…' : 'Expand into lessons →'}
        </button>
      {:else}
        {#if content!.generation_warnings.length > 0}
          <div class="mb-3 rounded-xl border border-amber-200 bg-amber-50 px-4 py-2.5 text-xs text-amber-700 dark:border-amber-900 dark:bg-amber-950/30 dark:text-amber-400">
            {#each content!.generation_warnings as w}<p>{w}</p>{/each}
          </div>
        {/if}
        <div class="space-y-3">
          {#each content!.lessons as lesson (lesson.school_calendar_id + lesson.period_id)}
            {@const key = lesson.school_calendar_id + lesson.period_id}
            <div class="rounded-xl border border-[var(--border)] p-3">
              <div class="flex items-center justify-between gap-2">
                <p class="text-xs font-semibold text-[var(--fg)]">
                  {fmtDate(lesson.lesson_date)} · {lesson.start_time.slice(0, 5)}–{lesson.end_time.slice(0, 5)}
                </p>
                <button
                  onclick={() => { regeneratingKey = key; $regenLessonMut.mutate({ calId: lesson.school_calendar_id, periodId: lesson.period_id }); }}
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

<style>
  @reference "tailwindcss";
  .lbl { @apply text-xs font-medium text-[var(--fg-muted)]; }
</style>
