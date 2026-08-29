<script lang="ts">
  import { createMutation, useQueryClient } from '@tanstack/svelte-query';
  import {
    createLessonPlan, updateLessonPlan, deleteLessonPlan,
    type LessonPlan, type LessonPlanPayload,
  } from '$lib/api/lessonPlans';
  import { apiError } from '$lib/utils';
  import { toast } from '$lib/stores/toast';
  import ConfirmModal from '$lib/components/ConfirmModal.svelte';
  import AiAssistPanel from './AiAssistPanel.svelte';

  interface Props {
    classId: string; subjectId: string; academicTermId: string; weekStart: string;
    plan: LessonPlan | null;
  }
  const { classId, subjectId, academicTermId, weekStart, plan }: Props = $props();

  const CORE_COMPETENCIES = [
    'Communication & Collaboration', 'Critical Thinking & Problem Solving',
    'Creativity & Innovation', 'Digital Literacy', 'Personal Development & Leadership',
  ];

  function emptyForm(): LessonPlanPayload {
    return {
      topic: '', content_standard: '', indicator: '', learning_objectives: '',
      core_competencies: '', teaching_resources: '', activities: '',
      assessment_strategy: '', reflection_notes: '',
    };
  }

  // Populated by the $effect below on every mount (initial and re-sync
  // alike) — starting empty here avoids duplicating that computation.
  let form = $state<LessonPlanPayload>(emptyForm());
  let selectedCompetencies = $state<string[]>([]);
  let showAiAssist = $state(false);
  let showDeleteConfirm = $state(false);

  // Re-sync when the parent hands us a different plan (a different week/
  // class/subject was selected) — this component instance is reused across
  // those changes, not remounted.
  $effect(() => {
    form = plan ? { ...plan } : emptyForm();
    selectedCompetencies = plan?.core_competencies ? plan.core_competencies.split(', ') : [];
  });

  function toggleCompetency(c: string) {
    selectedCompetencies = selectedCompetencies.includes(c)
      ? selectedCompetencies.filter(x => x !== c)
      : [...selectedCompetencies, c];
    form.core_competencies = selectedCompetencies.join(', ');
  }

  const qc = useQueryClient();
  function invalidate() {
    qc.invalidateQueries({ queryKey: ['lesson-plans', classId, subjectId, academicTermId, weekStart] });
  }

  const saveMut = createMutation({
    mutationFn: () => plan
      ? updateLessonPlan(plan.id, form)
      : createLessonPlan({
          ...form, class_id: classId, subject_id: subjectId,
          academic_term_id: academicTermId, week_start_date: weekStart,
        }),
    onSuccess: () => { invalidate(); toast.success(plan ? 'Lesson plan updated.' : 'Lesson plan saved.'); },
    onError: (e: unknown) => toast.error(apiError(e, 'Could not save this lesson plan.')),
  });

  const deleteMut = createMutation({
    mutationFn: () => deleteLessonPlan(plan!.id),
    onSuccess: () => { invalidate(); showDeleteConfirm = false; toast.success('Lesson plan deleted.'); },
    onError: (e: unknown) => { toast.error(apiError(e, 'Could not delete this lesson plan.')); showDeleteConfirm = false; },
  });

  function handleSave() {
    if (!form.topic?.trim()) { toast.error('Topic is required.'); return; }
    $saveMut.mutate();
  }
</script>

{#if !plan}
  <div class="mb-4 rounded-xl border border-amber-200 bg-amber-50 px-4 py-2.5 text-xs text-amber-700 dark:border-amber-900 dark:bg-amber-950/30 dark:text-amber-400">
    No plan yet for this week — fill in the form below and save.
  </div>
{/if}

<div class="space-y-4 rounded-2xl border border-[var(--border)] bg-[var(--card)] p-5">
  <label class="block">
    <span class="lx">Topic <span class="text-red-500">*</span></span>
    <div class="mt-1 flex gap-2">
      <input bind:value={form.topic} placeholder="e.g. Fractions — addition and subtraction" class="inp flex-1" />
      <button onclick={() => showAiAssist = !showAiAssist} disabled={!form.topic?.trim()}
        class="min-h-[44px] shrink-0 rounded-xl border border-[var(--border)] px-3 text-sm font-semibold text-[var(--fg-muted)] transition hover:bg-[var(--hover)] disabled:opacity-50">
        ✨ AI-assist
      </button>
    </div>
  </label>

  {#if showAiAssist}
    <AiAssistPanel
      {classId} {subjectId} topic={form.topic}
      onUseAsActivities={(text) => { form.activities = text; showAiAssist = false; }}
      onClose={() => showAiAssist = false}
    />
  {/if}

  <div class="grid gap-4 sm:grid-cols-2">
    <label class="block">
      <span class="lx">Content standard</span>
      <input bind:value={form.content_standard} placeholder="e.g. B4.1.1.1" class="inp mt-1" />
    </label>
    <label class="block">
      <span class="lx">Indicator</span>
      <input bind:value={form.indicator} placeholder="e.g. B4.1.1.1.1" class="inp mt-1" />
    </label>
  </div>

  <label class="block">
    <span class="lx">Learning objectives</span>
    <textarea bind:value={form.learning_objectives} rows="2" class="inp mt-1"></textarea>
  </label>

  <div>
    <span class="lx">Core competencies</span>
    <div class="mt-1.5 flex flex-wrap gap-x-4 gap-y-2">
      {#each CORE_COMPETENCIES as c}
        <label class="flex min-h-[44px] items-center gap-1.5 text-sm text-[var(--fg)]">
          <input type="checkbox" checked={selectedCompetencies.includes(c)} onchange={() => toggleCompetency(c)}
            class="h-4 w-4 rounded border-[var(--border)]" />
          {c}
        </label>
      {/each}
    </div>
  </div>

  <label class="block">
    <span class="lx">Teaching / learning resources</span>
    <textarea bind:value={form.teaching_resources} rows="2" class="inp mt-1"></textarea>
  </label>

  <label class="block">
    <span class="lx">Activities</span>
    <textarea bind:value={form.activities} rows="4" class="inp mt-1"></textarea>
  </label>

  <label class="block">
    <span class="lx">Assessment strategy</span>
    <textarea bind:value={form.assessment_strategy} rows="2" class="inp mt-1"></textarea>
  </label>

  <label class="block">
    <span class="lx">Reflection notes <span class="font-normal text-[var(--fg-subtle)]">(fill in after teaching)</span></span>
    <textarea bind:value={form.reflection_notes} rows="2" class="inp mt-1"></textarea>
  </label>

  <div class="flex flex-wrap items-center justify-between gap-2 pt-1">
    <button onclick={handleSave} disabled={$saveMut.isPending}
      class="min-h-[44px] rounded-xl px-4 py-2 text-sm font-semibold text-white transition hover:opacity-90 disabled:opacity-50" style="background: var(--brand)">
      {$saveMut.isPending ? 'Saving…' : plan ? 'Save changes' : 'Save lesson plan'}
    </button>
    {#if plan}
      <button onclick={() => showDeleteConfirm = true}
        class="min-h-[44px] rounded-xl border border-[var(--border)] px-4 py-2 text-sm text-red-600 transition hover:border-red-200 hover:bg-red-50 dark:hover:border-red-800 dark:hover:bg-red-950/30">
        Delete
      </button>
    {/if}
  </div>
</div>

<ConfirmModal
  open={showDeleteConfirm}
  title="Delete this lesson plan?"
  message="{form.topic} for this week will be permanently removed."
  confirmLabel="Delete"
  variant="danger"
  isPending={$deleteMut.isPending}
  onConfirm={() => $deleteMut.mutate()}
  onCancel={() => showDeleteConfirm = false}
/>

<style>
  @reference "tailwindcss";
  .lx  { @apply block text-xs font-medium text-[var(--fg-muted)]; }
  .inp { @apply w-full rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--fg)] focus:border-[var(--brand)] focus:outline-none transition; }
</style>
