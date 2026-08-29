<script lang="ts">
  import { createMutation } from '@tanstack/svelte-query';
  import { draftLessonPlanWithAi } from '$lib/api/lessonPlans';
  import { toast } from '$lib/stores/toast';

  interface Props {
    classId: string; subjectId: string; topic: string;
    onUseAsActivities: (text: string) => void;
    onClose: () => void;
  }
  const { classId, subjectId, topic, onUseAsActivities, onClose }: Props = $props();

  function detailOf(e: unknown): string | undefined {
    return (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
  }
  function statusOf(e: unknown): number | undefined {
    return (e as { response?: { status?: number } })?.response?.status;
  }

  let errorMessage = $state('');

  const draftMut = createMutation({
    mutationFn: () => draftLessonPlanWithAi(classId, subjectId, topic),
    onError: (e: unknown) => {
      const status = statusOf(e);
      if (status === 503) errorMessage = detailOf(e) ?? 'No AI provider is configured for this school.';
      else if (status === 429) errorMessage = detailOf(e) ?? 'Daily AI generation limit reached. Try again tomorrow.';
      else { errorMessage = ''; toast.error(detailOf(e) ?? 'Could not generate a draft.'); }
    },
  });

  // Fire once on open — a topic is required to get here (the button that
  // opens this panel is disabled without one), so no separate "Generate" tap.
  $draftMut.mutate();

  async function copyToClipboard() {
    if (!$draftMut.data) return;
    await navigator.clipboard.writeText($draftMut.data.draft_text);
    toast.success('Copied.');
  }
</script>

<div class="mt-3 rounded-2xl border border-[var(--border)] bg-[var(--card)] p-4">
  <div class="mb-2 flex items-center justify-between">
    <p class="text-sm font-semibold text-[var(--fg)]">✨ AI-assist draft</p>
    <button onclick={onClose} aria-label="Close" title="Close"
      class="flex h-8 w-8 items-center justify-center rounded-lg text-[var(--fg-muted)] hover:bg-[var(--hover)]">
      <svg class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12"/>
      </svg>
    </button>
  </div>

  {#if $draftMut.isPending}
    <div class="space-y-2">{#each [1, 2, 3] as _}<div class="h-4 animate-pulse rounded bg-[var(--hover)]"></div>{/each}</div>
  {:else if errorMessage}
    <p class="text-sm text-[var(--fg-muted)]">{errorMessage}</p>
  {:else if $draftMut.data}
    <p class="mb-3 max-h-64 overflow-y-auto whitespace-pre-wrap text-sm text-[var(--fg)]">{$draftMut.data.draft_text}</p>
    <p class="mb-3 text-xs text-[var(--fg-subtle)]">Review before using — this is a starting draft, not a finished plan.</p>
    <div class="flex flex-wrap gap-2">
      <button onclick={() => onUseAsActivities($draftMut.data!.draft_text)}
        class="min-h-[44px] rounded-xl px-4 py-2 text-sm font-semibold text-white transition hover:opacity-90" style="background: var(--brand)">
        Use as Activities
      </button>
      <button onclick={copyToClipboard}
        class="min-h-[44px] rounded-xl border border-[var(--border)] px-4 py-2 text-sm text-[var(--fg-muted)] transition hover:bg-[var(--hover)]">
        Copy
      </button>
    </div>
  {/if}
</div>
