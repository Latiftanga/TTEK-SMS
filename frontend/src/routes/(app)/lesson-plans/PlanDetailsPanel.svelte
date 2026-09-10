<script lang="ts">
  import { createMutation, useQueryClient } from '@tanstack/svelte-query';
  import {
    updateLessonPlan, deleteLessonPlan, type LessonPlan, type LessonPlanPayload,
  } from '$lib/api/lessonPlans';
  import { apiError } from '$lib/utils';
  import { toast } from '$lib/stores/toast';
  import ConfirmModal from '$lib/components/ConfirmModal.svelte';

  interface Props {
    classId: string; subjectId: string; academicTermId: string; weekStart: string;
    plan: LessonPlan;
  }
  const { classId, subjectId, academicTermId, weekStart, plan }: Props = $props();

  const CORE_COMPETENCIES = [
    'Communication & Collaboration', 'Critical Thinking & Problem Solving',
    'Creativity & Innovation', 'Digital Literacy', 'Personal Development & Leadership',
  ];

  let open = $state(false);
  let form = $state<LessonPlanPayload>({ topic: '' });
  let selectedCompetencies = $state<string[]>([]);
  let showDeleteConfirm = $state(false);
  let syncedPlanId = $state<string | undefined>(undefined);

  // Re-sync only when the parent hands us a genuinely different plan (a
  // different week/class/subject was selected) — this component instance is
  // reused across those changes, not remounted. Keying on plan.id (rather
  // than the plan object reference) means a background refetch of the same
  // plan — from a chat reply, a regeneration, or an approve/reject
  // elsewhere on the page — doesn't clobber in-progress edits here.
  $effect(() => {
    if (plan.id === syncedPlanId) return;
    syncedPlanId = plan.id;
    form = { ...plan };
    selectedCompetencies = plan.core_competencies ? plan.core_competencies.split(', ') : [];
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
    mutationFn: () => updateLessonPlan(plan.id, form),
    onSuccess: () => { invalidate(); toast.success('Lesson plan updated.'); },
    onError: (e: unknown) => toast.error(apiError(e, 'Could not save this lesson plan.')),
  });

  const deleteMut = createMutation({
    mutationFn: () => deleteLessonPlan(plan.id),
    onSuccess: () => { invalidate(); showDeleteConfirm = false; toast.success('Lesson plan deleted.'); },
    onError: (e: unknown) => { toast.error(apiError(e, 'Could not delete this lesson plan.')); showDeleteConfirm = false; },
  });

  function handleSave() {
    if (!form.topic?.trim()) { toast.error('Topic is required.'); return; }
    $saveMut.mutate();
  }
</script>

{#if !open}
  <button onclick={() => open = true}
    class="flex w-full items-center justify-between rounded-2xl border border-dashed border-[var(--border)]
           px-5 py-4 text-left transition hover:border-[var(--brand)]/40 hover:bg-[var(--brand)]/5">
    <div>
      <p class="text-sm font-semibold text-[var(--fg)]">Plan details</p>
      <p class="mt-0.5 text-xs text-[var(--fg-muted)]">Topic, curriculum reference, resources, activities, reflection notes</p>
    </div>
    <svg class="h-4 w-4 shrink-0 text-[var(--fg-subtle)]" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
      <path stroke-linecap="round" stroke-linejoin="round" d="M19.5 8.25l-7.5 7.5-7.5-7.5"/>
    </svg>
  </button>
{:else}
  <div class="space-y-4 rounded-2xl border border-[var(--border)] bg-[var(--card)] p-5">
    <div class="flex items-center justify-between gap-2">
      <p class="text-sm font-semibold text-[var(--fg)]">Plan details</p>
      <button onclick={() => open = false} class="text-xs font-semibold text-[var(--fg-muted)] hover:text-[var(--fg)]">Collapse</button>
    </div>

    <label class="block">
      <span class="lx">Topic <span class="text-red-500">*</span></span>
      <input bind:value={form.topic} placeholder="e.g. Fractions — addition and subtraction" class="inp mt-1" />
    </label>

    <div class="grid gap-4 sm:grid-cols-2">
      <label class="block">
        <span class="lx">Content standard</span>
        <textarea bind:value={form.content_standard} rows="2" class="inp mt-1"></textarea>
      </label>
      <label class="block">
        <span class="lx">Indicator</span>
        <textarea bind:value={form.indicator} rows="2" class="inp mt-1"></textarea>
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
        {$saveMut.isPending ? 'Saving…' : 'Save changes'}
      </button>
      <button onclick={() => showDeleteConfirm = true}
        class="min-h-[44px] rounded-xl border border-[var(--border)] px-4 py-2 text-sm text-red-600 transition hover:border-red-200 hover:bg-red-50 dark:hover:border-red-800 dark:hover:bg-red-950/30">
        Delete
      </button>
    </div>
  </div>
{/if}

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
