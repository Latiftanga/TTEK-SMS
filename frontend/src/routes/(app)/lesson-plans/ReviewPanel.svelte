<script lang="ts">
  import { createMutation, useQueryClient } from '@tanstack/svelte-query';
  import { reviewLessonPlan, type LessonPlan } from '$lib/api/lessonPlans';
  import { apiError } from '$lib/utils';
  import { toast } from '$lib/stores/toast';
  import { isSchoolAdmin } from '$lib/stores/permissions';

  interface Props {
    plan: LessonPlan;
    classId: string; subjectId: string; academicTermId: string; weekStart: string;
  }
  const { plan, classId, subjectId, academicTermId, weekStart }: Props = $props();

  // Re-synced on every plan change below — this component is reused across
  // different week/class/subject selections, not remounted (same pattern as
  // LessonPlanForm.svelte's own $effect re-sync).
  let notes = $state('');
  $effect(() => { notes = plan.review_notes ?? ''; });

  const qc = useQueryClient();
  function invalidate() {
    qc.invalidateQueries({ queryKey: ['lesson-plans', classId, subjectId, academicTermId, weekStart] });
  }

  const reviewMut = createMutation({
    mutationFn: (status: 'APPROVED' | 'DRAFT') => reviewLessonPlan(plan.id, { status, review_notes: notes || null }),
    onSuccess: () => { invalidate(); toast.success('Review saved.'); },
    onError: (e: unknown) => toast.error(apiError(e, 'Could not save this review.')),
  });
</script>

{#if $isSchoolAdmin}
  <div class="mt-6 space-y-3 rounded-2xl border border-[var(--border)] bg-[var(--card)] p-5">
    <div class="flex items-center justify-between gap-2">
      <h3 class="text-sm font-semibold text-[var(--fg)]">Review</h3>
      <span class="rounded-full px-2.5 py-0.5 text-xs font-semibold {plan.status === 'APPROVED'
        ? 'bg-green-100 text-green-700 dark:bg-green-950/30 dark:text-green-400'
        : 'bg-[var(--hover)] text-[var(--fg-muted)]'}">
        {plan.status === 'APPROVED' ? 'Approved' : 'Draft'}
      </span>
    </div>

    {#if plan.reviewed_at}
      <p class="text-xs text-[var(--fg-muted)]">Last reviewed {new Date(plan.reviewed_at).toLocaleString('en-GH')}</p>
    {/if}

    <label class="block">
      <span class="text-xs font-medium text-[var(--fg-muted)]">Review notes</span>
      <textarea bind:value={notes} rows="2"
        class="mt-1 w-full rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--fg)] focus:border-[var(--brand)] focus:outline-none transition"></textarea>
    </label>

    <div class="flex gap-2">
      {#if plan.status !== 'APPROVED'}
        <button onclick={() => $reviewMut.mutate('APPROVED')} disabled={$reviewMut.isPending}
          class="min-h-[44px] rounded-xl px-4 py-2 text-sm font-semibold text-white transition hover:opacity-90 disabled:opacity-50"
          style="background: var(--brand)">
          {$reviewMut.isPending ? 'Saving…' : 'Approve'}
        </button>
      {:else}
        <button onclick={() => $reviewMut.mutate('DRAFT')} disabled={$reviewMut.isPending}
          class="min-h-[44px] rounded-xl border border-[var(--border)] px-4 py-2 text-sm font-semibold text-[var(--fg-muted)] transition hover:bg-[var(--hover)] disabled:opacity-50">
          {$reviewMut.isPending ? 'Saving…' : 'Send back to draft'}
        </button>
      {/if}
    </div>
  </div>
{/if}
