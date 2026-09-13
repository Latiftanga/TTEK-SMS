<script lang="ts">
  import SubjectRosterPanel from '$lib/components/SubjectRosterPanel.svelte';
  import CurriculumMaterialsPanel from './CurriculumMaterialsPanel.svelte';

  interface Props { subjectId: string; classId: string; classSubjectId: string; }
  const { subjectId, classId, classSubjectId }: Props = $props();
</script>

<div class="border-t border-[var(--border)] bg-[var(--hover)]/40 px-4 py-3 space-y-3">
  <!-- Students -->
  <div>
    <p class="mb-1 text-[10px] font-bold uppercase tracking-widest text-[var(--fg-subtle)]">Students</p>
    <SubjectRosterPanel {classId} {subjectId} />
  </div>

  <div class="border-t border-[var(--border)] pt-3">
    <CurriculumMaterialsPanel {classSubjectId} />
  </div>
</div>
