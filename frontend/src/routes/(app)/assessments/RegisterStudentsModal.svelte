<script lang="ts">
  import { portal } from '$lib/actions/portal';
  import SubjectRosterPanel from '$lib/components/SubjectRosterPanel.svelte';

  interface Props { classId: string; subjectId: string; subjectName: string; onClose: () => void; }
  const { classId, subjectId, subjectName, onClose }: Props = $props();

  function onKeydown(e: KeyboardEvent) { if (e.key === 'Escape') onClose(); }
</script>

<!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
<div use:portal role="dialog" aria-modal="true"
  class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
  onkeydown={onKeydown}>
  <div class="flex w-full max-w-lg flex-col rounded-2xl border border-[var(--border)] bg-[var(--card)] shadow-2xl"
       style="max-height: 90vh">

    <!-- Header -->
    <div class="flex shrink-0 items-center justify-between border-b border-[var(--border)] px-6 py-4">
      <div>
        <h2 class="text-base font-semibold text-[var(--fg)]">Register students — {subjectName}</h2>
        <p class="text-xs text-[var(--fg-muted)]">Select who takes this subject, then save.</p>
      </div>
      <button onclick={onClose} aria-label="Close"
        class="rounded-lg p-1.5 text-[var(--fg-muted)] transition hover:bg-[var(--hover)]">
        <svg class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12"/>
        </svg>
      </button>
    </div>

    <!-- SubjectRosterPanel is self-contained (its own fetch, search, select-all,
         has_scores warning, term-lock override modal, conflict handling) — this
         wrapper only supplies the modal chrome around it. -->
    <div class="min-h-0 flex-1 overflow-y-auto">
      <SubjectRosterPanel {classId} {subjectId} />
    </div>
  </div>
</div>
