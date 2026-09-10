<script lang="ts">
  import { createMutation, useQueryClient } from '@tanstack/svelte-query';
  import { reactiveQuery } from '$lib/query.svelte';
  import {
    listCurriculumUnitsForPlanning, createLessonPlan, sendChatMessage,
  } from '$lib/api/lessonPlans';
  import type { CurriculumUnit } from '$lib/api/curriculumUnits';
  import { apiError } from '$lib/utils';
  import { toast } from '$lib/stores/toast';
  import { isOnline } from '$lib/offline/sync';

  interface Props {
    classId: string; subjectId: string; academicTermId: string; weekStart: string;
  }
  const { classId, subjectId, academicTermId, weekStart }: Props = $props();

  // Real, cited content from an uploaded curriculum material — never
  // auto-mapped from the calendar week (pacing drifts too easily: a lesson
  // can get bumped to another day, a holiday shifts things), the teacher
  // picks the matching unit themselves from this short list.
  const unitsQ = reactiveQuery(() => ({
    queryKey: ['curriculum-units-for-planning', classId, subjectId, academicTermId] as const,
    queryFn: () => listCurriculumUnitsForPlanning(classId, subjectId, academicTermId),
    enabled: !!(classId && subjectId && academicTermId),
    staleTime: 30_000,
  }));
  const units = $derived($unitsQ.data ?? []);

  let showRawChat = $state(false);
  let draft = $state('');

  const qc = useQueryClient();
  function invalidatePlans() {
    qc.invalidateQueries({ queryKey: ['lesson-plans', classId, subjectId, academicTermId, weekStart] });
  }

  const startFromUnitMut = createMutation({
    mutationFn: (unit: CurriculumUnit) => createLessonPlan({
      class_id: classId, subject_id: subjectId, academic_term_id: academicTermId, week_start_date: weekStart,
      topic: (unit.topics?.split('\n')[0] || unit.unit_label || `Unit ${unit.sequence_number}`).slice(0, 300),
      curriculum_unit_id: unit.id,
    }),
    onSuccess: () => { invalidatePlans(); toast.success('Lesson plan started.'); },
    onError: (e: unknown) => toast.error(apiError(e, 'Could not start a lesson plan for this unit.')),
  });

  // No matching unit — the chat itself asks for the topic. The teacher's
  // first reply becomes the plan's topic, and the LessonPlan row is created
  // transparently behind that first exchange (then replayed as the real
  // first chat message, so the conversation and its AI reply continue
  // normally once ChatPanel takes over).
  const startFromChatMut = createMutation({
    mutationFn: async (message: string) => {
      const plan = await createLessonPlan({
        class_id: classId, subject_id: subjectId, academic_term_id: academicTermId, week_start_date: weekStart,
        topic: message.slice(0, 300),
      });
      await sendChatMessage(plan.id, message);
      return plan;
    },
    onSuccess: () => { invalidatePlans(); draft = ''; },
    onError: (e: unknown) => toast.error(apiError(e, 'Could not start this conversation.')),
  });

  function handleSend() {
    if (!draft.trim() || $startFromChatMut.isPending) return;
    $startFromChatMut.mutate(draft.trim());
  }
</script>

{#if !showRawChat && units.length > 0}
  <div class="space-y-3 rounded-2xl border border-[var(--border)] bg-[var(--card)] p-5">
    <h3 class="text-sm font-semibold text-[var(--fg)]">What are you teaching this week?</h3>
    <p class="text-xs text-[var(--fg-muted)]">
      Pick the matching unit from your uploaded curriculum material — this fills in
      the content standard and indicator for you.
    </p>
    <div class="space-y-1.5">
      {#each units as u (u.id)}
        <button onclick={() => $startFromUnitMut.mutate(u)} disabled={$startFromUnitMut.isPending}
          class="block w-full rounded-xl border border-[var(--border)] px-3 py-2.5 text-left transition hover:bg-[var(--hover)] disabled:opacity-50">
          <p class="text-sm font-medium text-[var(--fg)]">
            {u.unit_label ?? `Unit ${u.sequence_number}`}{u.topics ? ` — ${u.topics.split('\n')[0]}` : ''}
          </p>
          {#if u.strand}
            <p class="text-xs text-[var(--fg-muted)]">{u.strand}{u.sub_strand ? ` — ${u.sub_strand}` : ''}</p>
          {/if}
        </button>
      {/each}
    </div>
    <button onclick={() => showRawChat = true}
      class="text-xs font-semibold text-[var(--fg-muted)] underline transition hover:text-[var(--fg)]">
      None of these — I'll describe my own topic
    </button>
  </div>
{:else}
  <div class="space-y-3 rounded-2xl border border-[var(--border)] bg-[var(--card)] p-5">
    <div class="flex items-center justify-between gap-2">
      <h3 class="text-sm font-semibold text-[var(--fg)]">Chat with the AI assistant</h3>
      {#if !$isOnline}
        <span class="text-xs font-medium text-[var(--fg-muted)]">Offline — connect to chat</span>
      {/if}
    </div>
    <div class="rounded-xl border border-[var(--border)] bg-[var(--bg)] p-3">
      <div class="max-w-[85%] rounded-xl border border-[var(--border)] bg-[var(--card)] px-3 py-2 text-sm text-[var(--fg)]">
        What are you teaching this week? Tell me the topic and I'll help you plan it.
      </div>
    </div>
    <div class="flex gap-2">
      <textarea bind:value={draft} rows="2" placeholder="e.g. Introduction to fractions…"
        onkeydown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend(); } }}
        class="flex-1 rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--fg)] focus:border-[var(--brand)] focus:outline-none transition"></textarea>
      <button onclick={handleSend} disabled={!draft.trim() || $startFromChatMut.isPending || !$isOnline}
        class="min-h-[44px] shrink-0 rounded-xl px-4 py-2 text-sm font-semibold text-white transition hover:opacity-90 disabled:opacity-50"
        style="background: var(--brand)">
        {$startFromChatMut.isPending ? 'Starting…' : 'Send'}
      </button>
    </div>
    {#if units.length > 0}
      <button onclick={() => showRawChat = false}
        class="text-xs font-semibold text-[var(--fg-muted)] underline transition hover:text-[var(--fg)]">
        ← Back to unit list
      </button>
    {/if}
  </div>
{/if}
