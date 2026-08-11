<script lang="ts">
  import { createMutation, useQueryClient } from '@tanstack/svelte-query';
  import { bulkPublishAssessments } from '$lib/api/assessments';
  import { updateTerm, type AcademicTerm } from '$lib/api/academic';
  import { toast } from '$lib/stores/toast';

  interface Props {
    canManage: boolean; classId: string; termId: string;
    selectedTerm: AcademicTerm | undefined;
  }
  const { canManage, classId, termId, selectedTerm }: Props = $props();

  const qc = useQueryClient();

  const resultsLockMut = createMutation({
    mutationFn: ({ id, on }: { id: string; on: boolean }) => updateTerm(id, { results_locked: on }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['academic-years'] });
      qc.invalidateQueries({ queryKey: ['all-terms'] });
    },
  });

  // Publishes every approved, not-yet-published assessment for the whole
  // class+term in one action — not filtered by the Subject/Category pickers
  // above it on the page, same class+term-wide scope as the Lock results toggle.
  const bulkPublishMut = createMutation({
    mutationFn: () => bulkPublishAssessments(classId, termId),
    onSuccess: (result) => {
      qc.invalidateQueries({ queryKey: ['assessments', classId, termId] });
      const parts = [`${result.published} published`];
      if (result.skipped_unapproved) parts.push(`${result.skipped_unapproved} skipped (unapproved scores)`);
      if (result.already_published) parts.push(`${result.already_published} already published`);
      toast.success(parts.join(', '));
    },
    onError: () => toast.error('Could not bulk-publish assessments.'),
  });
</script>

<!-- Actions — own row, separate from the filter grid so buttons don't fight
     the selects for space on a phone. -->
<div class="mb-5 flex flex-wrap items-center gap-2">
  {#if canManage && termId && selectedTerm}
    <button
      onclick={() => $resultsLockMut.mutate({ id: termId, on: !selectedTerm.results_locked })}
      disabled={$resultsLockMut.isPending}
      title={selectedTerm.results_locked
        ? 'Unlock — scores and behaviour records for this term can be edited again'
        : 'Lock — freeze scores and behaviour records for this term (overridable with a reason)'}
      class="flex min-h-[44px] items-center gap-1.5 rounded-xl border px-3 py-2 text-xs font-semibold transition disabled:opacity-50
        {selectedTerm.results_locked
          ? 'border-red-200 bg-red-50 text-red-700 hover:bg-red-100 dark:border-red-800 dark:bg-red-950/30 dark:text-red-400'
          : 'border-[var(--border)] bg-[var(--card)] text-[var(--fg-muted)] hover:border-[var(--brand)] hover:text-[var(--brand)]'}">
      <svg class="h-3.5 w-3.5 shrink-0" fill="none" stroke="currentColor" stroke-width="1.75" viewBox="0 0 24 24">
        {#if selectedTerm.results_locked}
          <path stroke-linecap="round" stroke-linejoin="round" d="M13.5 10.5V6.75a4.5 4.5 0 119 0v3.75M3.75 21.75h10.5a2.25 2.25 0 002.25-2.25v-6.75a2.25 2.25 0 00-2.25-2.25H3.75a2.25 2.25 0 00-2.25 2.25v6.75a2.25 2.25 0 002.25 2.25z"/>
        {:else}
          <path stroke-linecap="round" stroke-linejoin="round" d="M16.5 10.5V6.75a4.5 4.5 0 10-9 0v3.75m-.75 11.25h10.5a2.25 2.25 0 002.25-2.25v-6.75a2.25 2.25 0 00-2.25-2.25H6.75a2.25 2.25 0 00-2.25 2.25v6.75a2.25 2.25 0 002.25 2.25z"/>
        {/if}
      </svg>
      {$resultsLockMut.isPending ? '…' : selectedTerm.results_locked ? 'Results locked' : 'Lock results'}
    </button>
  {/if}
  {#if canManage && classId && termId}
    <button
      onclick={() => $bulkPublishMut.mutate()}
      disabled={$bulkPublishMut.isPending}
      title="Publish every approved, not-yet-published assessment for this class and term"
      class="flex min-h-[44px] items-center gap-1.5 rounded-xl border border-[var(--border)] bg-[var(--card)] px-3 py-2 text-xs font-semibold text-[var(--fg-muted)] transition hover:border-[var(--brand)] hover:text-[var(--brand)] disabled:opacity-50">
      <svg class="h-3.5 w-3.5 shrink-0" fill="none" stroke="currentColor" stroke-width="1.75" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" d="M3.75 13.5l10.5-11.25L12 10.5h8.25L9.75 21.75 12 13.5H3.75z"/>
      </svg>
      {$bulkPublishMut.isPending ? 'Publishing…' : 'Publish all approved'}
    </button>
  {/if}
</div>
