<script lang="ts">
  import { portal } from '$lib/actions/portal';
  import type { SchoolPeriod } from '$lib/api/schoolPeriods';
  import type { ClassSubject, Subject } from '$lib/api/academic';
  import type { StaffSummary } from '$lib/api/staff';
  import type { TimetableSlot } from '$lib/api/timetable';

  interface Props {
    open: boolean;
    period: SchoolPeriod | null;
    classSubjects: ClassSubject[];
    allSubjects: Subject[];
    subjectMap: Map<string, Subject>;
    teachingStaff: StaffSummary[];
    currentSlot: TimetableSlot | undefined;
    subjectTeacherBySubject: Map<string, string>;
    isPending: boolean;
    errorMessage: string;
    errorCode: string | null;
    onSave: (args: { subjectId: string; staffMemberId: string }) => void;
    onClear: () => void;
    onCancel: () => void;
  }
  const {
    open, period, classSubjects, allSubjects, subjectMap, teachingStaff, currentSlot,
    subjectTeacherBySubject, isPending, errorMessage, errorCode, onSave, onClear, onCancel,
  }: Props = $props();

  let subjectId = $state('');
  let staffMemberId = $state('');

  // Re-seed local state whenever a different period is opened (open flips
  // false→true, or the same modal is reused for a new cell).
  $effect(() => {
    if (!open) return;
    subjectId = currentSlot?.subject_id ?? '';
    staffMemberId = currentSlot?.staff_member_id ?? '';
  });

  function onSubjectChange() {
    if (!staffMemberId && subjectId) {
      const existingTeacher = subjectTeacherBySubject.get(subjectId);
      if (existingTeacher) staffMemberId = existingTeacher;
    }
  }

  const subjectName = $derived(subjectId ? (subjectMap.get(subjectId)?.name ?? '') : '');

  // Any active subject can be scheduled here, not just ones already on this
  // class's curriculum — picking one that isn't yet auto-adds it (see
  // services/timetable.py::upsert_timetable_slot's own docstring), so
  // there's no separate "add subject to curriculum" step required before
  // transcribing a printed timetable. Grouped in the dropdown purely so an
  // admin can tell at a glance which pick is "new" for this class.
  const classSubjectIds = $derived(new Set(classSubjects.map(cs => cs.subject_id)));
  const onCurriculum    = $derived(allSubjects.filter(s => classSubjectIds.has(s.id)));
  const newToClass      = $derived(allSubjects.filter(s => !classSubjectIds.has(s.id)));
  const isNewSubject    = $derived(!!subjectId && !classSubjectIds.has(subjectId));

  function onKeydown(e: KeyboardEvent) { if (e.key === 'Escape') onCancel(); }

  const sel = 'w-full rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--fg)] focus:border-[var(--brand)] focus:outline-none transition';
</script>

{#if open && period}
  <!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
  <div use:portal role="dialog" aria-modal="true"
    class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
    onkeydown={onKeydown}>
    <div class="w-full max-w-sm rounded-2xl border border-[var(--border)] bg-[var(--card)] p-6 shadow-2xl">
      <h2 class="text-base font-semibold text-[var(--fg)]">{period.name}</h2>
      <p class="mt-0.5 text-xs text-[var(--fg-muted)]">{period.start_time.slice(0,5)}–{period.end_time.slice(0,5)}</p>

      <div class="mt-4 space-y-3">
        <div>
          <p class="mb-1 text-[10px] font-bold uppercase tracking-widest text-[var(--fg-subtle)]">Subject</p>
          <select bind:value={subjectId} onchange={onSubjectChange} class={sel}>
            <option value="">Choose a subject…</option>
            {#if onCurriculum.length > 0}
              <optgroup label="This class's subjects">
                {#each onCurriculum as s (s.id)}<option value={s.id}>{s.name}</option>{/each}
              </optgroup>
            {/if}
            {#if newToClass.length > 0}
              <optgroup label="Add a new subject to this class">
                {#each newToClass as s (s.id)}<option value={s.id}>{s.name}</option>{/each}
              </optgroup>
            {/if}
          </select>
        </div>

        <div>
          <p class="mb-1 text-[10px] font-bold uppercase tracking-widest text-[var(--fg-subtle)]">Teacher</p>
          <select bind:value={staffMemberId}
            class="{sel} {errorCode === 'no_teacher_assigned' ? 'border-red-500' : ''}">
            <option value="">Choose a teacher…</option>
            {#each teachingStaff as s (s.id)}
              <option value={s.id}>{s.display_name}</option>
            {/each}
          </select>
        </div>

        {#if isNewSubject}
          <p class="rounded-xl bg-[var(--hover)] p-2.5 text-[11px] leading-snug text-[var(--fg-muted)]">
            {subjectName} isn't on this class's curriculum yet — saving will add it (as a core subject; switch it to elective from the Subjects tab if needed).
          </p>
        {/if}

        {#if subjectId}
          <p class="rounded-xl bg-[var(--hover)] p-2.5 text-[11px] leading-snug text-[var(--fg-muted)]">
            Heads up: this sets {subjectName}'s teacher for this class's whole year —
            it changes on every other period where {subjectName} appears on this
            timetable too, not just this one.
          </p>
        {/if}

        {#if errorMessage}<p class="text-xs text-red-500">{errorMessage}</p>{/if}
      </div>

      <div class="mt-5 flex items-center justify-between gap-3">
        {#if currentSlot}
          <button onclick={onClear} disabled={isPending}
            class="text-xs text-[var(--fg-subtle)] transition hover:text-red-500 disabled:opacity-50">
            Clear this period
          </button>
        {:else}
          <span></span>
        {/if}
        <div class="flex gap-2">
          <button onclick={onCancel} disabled={isPending}
            class="rounded-lg px-4 py-2 text-sm text-[var(--fg-muted)] transition hover:bg-[var(--hover)] disabled:opacity-50">
            Cancel
          </button>
          <button onclick={() => onSave({ subjectId, staffMemberId })}
            disabled={!subjectId || !staffMemberId || isPending}
            class="rounded-lg px-4 py-2 text-sm font-semibold text-white transition disabled:opacity-50"
            style="background:var(--brand)">
            {isPending ? 'Saving…' : 'Save'}
          </button>
        </div>
      </div>
    </div>
  </div>
{/if}
