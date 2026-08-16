<script lang="ts">
  import type { AcademicTerm } from '$lib/api/academic';
  import type { MySubjectAssignment } from '$lib/api/assessments';

  interface Props {
    canManage: boolean;
    classId: string; subjectId: string; termId: string;
    myClasses: { id: string; display_name: string }[];
    subjectsForClass: MySubjectAssignment[];
    myClassSubjectPairs: MySubjectAssignment[];
    allTerms: (AcademicTerm & { yearName: string })[];
    onSetFilter: (key: string, value: string) => void;
    onSetClassSubject: (classId: string, subjectId: string) => void;
  }
  const {
    canManage, classId, subjectId, termId,
    myClasses, subjectsForClass, myClassSubjectPairs, allTerms,
    onSetFilter, onSetClassSubject,
  }: Props = $props();

  const pairKey = (p: { class_id: string; subject_id: string }) => `${p.class_id}::${p.subject_id}`;
  const selectedPairKey = $derived(classId && subjectId ? `${classId}::${subjectId}` : '');
</script>

<!-- Filters — progressive disclosure: a teacher picks Class & subject in one
     step (the system already knows their teaching pairs); admin/approver
     keep the Class → Subject two-step, since they need to browse classes
     that don't have a subject assigned yet. Each auto-selects itself when
     there's only one option, so most callers never even see more than one
     select here. A single stacked column on phones; reverts to a wrapping
     row from sm: up where there's room to read them side by side. -->
<div class="mb-3 flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-end">
  {#if canManage}
    <div class="sm:w-44">
      <label for="f-class" class="label">Class</label>
      <select id="f-class" value={classId} onchange={e => onSetFilter('class', e.currentTarget.value)} class="sel">
        <option value="">Select class…</option>
        {#each myClasses as c}<option value={c.id}>{c.display_name}</option>{/each}
      </select>
    </div>
    {#if classId}
      <div class="sm:w-44">
        <label for="f-subject" class="label">Subject</label>
        <select id="f-subject" value={subjectId} onchange={e => onSetFilter('subject', e.currentTarget.value)} class="sel">
          <option value="">Select subject…</option>
          {#each subjectsForClass as p}<option value={p.subject_id}>{p.subject_name}</option>{/each}
        </select>
      </div>
    {/if}
  {:else}
    <div class="sm:w-64">
      <label for="f-class-subject" class="label">Class & subject</label>
      <select id="f-class-subject" value={selectedPairKey}
        onchange={e => {
          const [c, s] = e.currentTarget.value.split('::');
          onSetClassSubject(c ?? '', s ?? '');
        }} class="sel">
        <option value="">Select class & subject…</option>
        {#each myClassSubjectPairs as p (pairKey(p))}
          <option value={pairKey(p)}>{p.class_name} — {p.subject_name}</option>
        {/each}
      </select>
    </div>
  {/if}
  {#if canManage}
    <!-- Admin/approver keep a real term picker — they legitimately browse past
         terms' assessments. A class/subject teacher is locked to the current
         term server-side (services/scoring.py::submit_scores), and the current
         term is already shown in the top bar, so no picker or label is shown
         to them here at all. Not part of the Class→Subject chain, so it's
         always shown. -->
    <div class="sm:flex-1 sm:min-w-[180px]">
      <label for="f-term" class="label">Term</label>
      <select id="f-term" value={termId} onchange={e => onSetFilter('term', e.currentTarget.value)} class="sel">
        <option value="">Select term…</option>
        {#each allTerms as t}<option value={t.id}>{t.yearName} — {t.name}</option>{/each}
      </select>
    </div>
  {/if}
</div>

<style>
  @reference "tailwindcss";
  .label { @apply block text-xs font-medium text-[var(--fg-muted)] mb-1; }
  .sel   { @apply w-full min-h-[44px] rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--fg)] focus:border-[var(--brand)] focus:outline-none transition; }
</style>
