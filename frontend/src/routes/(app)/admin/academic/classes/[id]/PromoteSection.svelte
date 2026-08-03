<script lang="ts">
  import { createQuery, createMutation, useQueryClient } from '@tanstack/svelte-query';
  import { listClasses, listYears, type SchoolClass, type AcademicYear } from '$lib/api/academic';
  import { listStudents, bulkPromoteStudents, type PromotionRecordCreate } from '$lib/api/students';
  import { toast } from '$lib/stores/toast';
  import { detailOf, isLocked } from '$lib/apiError';
  import TargetClassPicker from '$lib/components/TargetClassPicker.svelte';
  import OverrideReasonModal from '$lib/components/OverrideReasonModal.svelte';

  interface Props { classId: string; classData: SchoolClass; }
  const { classId, classData }: Props = $props();

  const qc = useQueryClient();

  let expanded = $state(false);

  // ── Queries (classesQ + yearsQ are shared / cached) ──────────────────────────
  const classesQ  = createQuery({ queryKey: ['classes'],              queryFn: listClasses, staleTime: 5 * 60_000 });
  const yearsQ    = createQuery({ queryKey: ['academic-years'],       queryFn: listYears,   staleTime: 5 * 60_000 });
  const studentsQ = createQuery({ queryKey: ['students', 'class', classId],
    queryFn: () => listStudents({ class_id: classId, active_only: true }), staleTime: 60_000 });

  const allClasses = $derived<SchoolClass[]>($classesQ.data ?? []);
  const years        = $derived<AcademicYear[]>([...($yearsQ.data ?? [])].sort((a, b) => b.start_date.localeCompare(a.start_date)));
  const students     = $derived($studentsQ.data ?? []);

  // ── Target class ──────────────────────────────────────────────────────────────
  let toClassId    = $state('');
  let toYearId     = $state('');
  let alsoEnroll   = $state(true);

  const targetYear = $derived(years.find(y => y.id === toYearId));
  const firstTerm  = $derived([...(targetYear?.terms ?? [])].sort((a, b) => a.start_date.localeCompare(b.start_date))[0] ?? null);

  // ── Student selection ─────────────────────────────────────────────────────────
  let selected = $state(new Set<string>());
  const allSelected = $derived(students.length > 0 && selected.size === students.length);

  function toggleAll() { selected = allSelected ? new Set() : new Set(students.map(s => s.id)); }
  function toggleOne(id: string) {
    const s = new Set(selected); s.has(id) ? s.delete(id) : s.add(id); selected = s;
  }

  // ── Action ────────────────────────────────────────────────────────────────────
  type ActionType = 'promote' | 'repeat' | 'demote';
  let actionType: ActionType = $state('promote');
  let confirmOpen = $state(false);
  let error = $state('');

  const ACTION: Record<ActionType, { label: string; color: string; desc: string }> = {
    promote: { label: 'Promote',     color: 'text-green-600 dark:text-green-400', desc: 'Move up to the next year group' },
    repeat:  { label: 'Repeat year', color: 'text-amber-600 dark:text-amber-400', desc: 'Re-enroll in the same class for a new year' },
    demote:  { label: 'Demote',      color: 'text-red-600 dark:text-red-400',     desc: 'Move down to a lower year group' },
  };
  const ACTION_TO_TYPE: Record<ActionType, PromotionRecordCreate['graduation_type']> = {
    promote: 'PROMOTED', repeat: 'REPEATED', demote: 'DEMOTED',
  };

  let overrideNeeded = $state(false);
  let overrideError  = $state('');

  const promoteMut = createMutation({
    mutationFn: (overrideReason?: string) => {
      const records: PromotionRecordCreate[] = [...selected].map(sid => ({
        student_id: sid, class_id: toClassId, graduation_type: ACTION_TO_TYPE[actionType],
      }));
      return bulkPromoteStudents({
        academic_year_id: toYearId,
        academic_term_id: alsoEnroll && firstTerm ? firstTerm.id : null,
        records,
        override_reason: overrideReason,
      });
    },
    onSuccess: (res) => {
      qc.invalidateQueries({ queryKey: ['students', 'class', classId] });
      const label = ACTION[actionType].label;
      toast.success(`${label}: ${res.processed} student(s). Skipped: ${res.skipped} (already processed for this year).`);
      selected = new Set(); confirmOpen = false; error = ''; overrideNeeded = false; overrideError = '';
    },
    onError: (e: unknown) => {
      if (isLocked(e)) { overrideNeeded = true; overrideError = detailOf(e) ?? 'This mismatch needs a reason.'; return; }
      error = detailOf(e) ?? 'Could not complete.';
      confirmOpen = false;
    },
  });

  function handlePromote() {
    error = '';
    if (!toClassId)       { error = 'Select a target class.'; return; }
    if (!toYearId)        { error = 'Select a target academic year.'; return; }
    if (!selected.size)   { error = 'Select at least one student.'; return; }
    confirmOpen = true;
  }

  const sel = 'w-full rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--fg)] focus:border-[var(--brand)] focus:outline-none transition';
</script>

<!-- Collapsed trigger -->
{#if !expanded}
  <button onclick={() => expanded = true}
    class="flex w-full items-center justify-between rounded-2xl border border-dashed border-[var(--border)]
           px-5 py-4 text-left transition hover:border-[var(--brand)]/40 hover:bg-[var(--brand)]/5">
    <div>
      <p class="text-sm font-semibold text-[var(--fg)]">Bulk Promote / Transfer</p>
      <p class="mt-0.5 text-xs text-[var(--fg-muted)]">Move or re-enroll students from this class</p>
    </div>
    <svg class="h-4 w-4 shrink-0 text-[var(--fg-subtle)]" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
      <path stroke-linecap="round" stroke-linejoin="round" d="M19.5 8.25l-7.5 7.5-7.5-7.5"/>
    </svg>
  </button>
{:else}
  <div class="space-y-4">

    <!-- Action type -->
    <div class="flex gap-2">
      {#each Object.entries(ACTION) as [key, meta]}
        <button onclick={() => { actionType = key as ActionType; toClassId = ''; }}
          class="flex-1 rounded-xl border px-3 py-2.5 text-left transition
                 {actionType === key
                   ? 'border-[var(--brand)] bg-[var(--brand)]/5 ring-1 ring-[var(--brand)]'
                   : 'border-[var(--border)] bg-[var(--card)] hover:border-[var(--brand)]/40'}">
          <p class="text-sm font-semibold {actionType === key ? meta.color : 'text-[var(--fg)]'}">{meta.label}</p>
          <p class="mt-0.5 text-[10px] text-[var(--fg-muted)]">{meta.desc}</p>
        </button>
      {/each}
    </div>

    <!-- Target selectors -->
    <div class="rounded-2xl border border-[var(--border)] bg-[var(--card)] p-4 space-y-3">
      <div class="grid gap-3 sm:grid-cols-2">
        <div>
          <label class="mb-1 block text-xs font-medium text-[var(--fg-muted)]">Target academic year *</label>
          <select bind:value={toYearId} class={sel}>
            <option value="">Select year…</option>
            {#each years as y}<option value={y.id}>{y.name}{y.is_current ? ' (current)' : ''}</option>{/each}
          </select>
        </div>
        <TargetClassPicker
          fromClass={classData} classes={allClasses}
          value={toClassId} onChange={(id) => toClassId = id} mode={actionType}
          label="Target class *" />
      </div>
      {#if toYearId && firstTerm}
        <label class="flex cursor-pointer items-center gap-2.5">
          <input type="checkbox" bind:checked={alsoEnroll} class="h-4 w-4 rounded accent-[var(--brand)]" />
          <span class="text-sm text-[var(--fg)]">Also register in <strong>{firstTerm.name}</strong> (first term)</span>
        </label>
      {/if}
    </div>

    <!-- Student list -->
    {#if $studentsQ.isPending}
      <div class="space-y-2">{#each [1,2,3,4] as _}<div class="h-11 animate-pulse rounded-xl bg-[var(--card)]"></div>{/each}</div>
    {:else if students.length === 0}
      <p class="rounded-2xl border border-dashed border-[var(--border)] py-8 text-center text-sm text-[var(--fg-muted)]">No active students in this class.</p>
    {:else}
      <div class="overflow-hidden rounded-2xl border border-[var(--border)] bg-[var(--card)]">
        <div class="flex items-center justify-between border-b border-[var(--border)] px-4 py-3">
          <label class="flex cursor-pointer items-center gap-2.5 text-sm font-medium text-[var(--fg)]">
            <input type="checkbox" checked={allSelected} onchange={toggleAll} class="h-4 w-4 rounded accent-[var(--brand)]" />
            {selected.size > 0 ? `${selected.size} of ${students.length} selected` : `${students.length} students`}
          </label>
          {#if selected.size > 0}
            <button onclick={() => selected = new Set()} class="text-xs text-[var(--fg-muted)] hover:text-[var(--fg)] transition">Clear</button>
          {/if}
        </div>
        {#each students as s (s.id)}
          <label class="flex cursor-pointer items-center gap-3 border-b border-[var(--border)] px-4 py-2.5 last:border-0
                         transition hover:bg-[var(--hover)] {selected.has(s.id) ? 'bg-[var(--brand)]/5' : ''}">
            <input type="checkbox" checked={selected.has(s.id)} onchange={() => toggleOne(s.id)} class="h-4 w-4 shrink-0 rounded accent-[var(--brand)]" />
            <span class="flex-1 text-sm font-medium text-[var(--fg)]">{s.display_name}</span>
            <span class="font-mono text-[10px] text-[var(--fg-subtle)]">{s.admission_number}</span>
          </label>
        {/each}
      </div>

      {#if error}<p class="rounded-xl bg-red-50 px-4 py-2 text-sm text-red-600 dark:bg-red-950/30 dark:text-red-400">{error}</p>{/if}

      {#if !confirmOpen}
        <div class="flex gap-2">
          <button onclick={handlePromote} disabled={selected.size === 0}
            class="flex-1 rounded-xl py-2.5 text-sm font-semibold text-white transition hover:opacity-90 disabled:opacity-40"
            style="background: var(--brand)">
            {ACTION[actionType].label} {selected.size > 0 ? `${selected.size} student${selected.size > 1 ? 's' : ''}` : 'selected'} →
          </button>
          <button onclick={() => { expanded = false; selected = new Set(); error = ''; confirmOpen = false; }}
            class="rounded-xl border border-[var(--border)] px-4 py-2.5 text-sm text-[var(--fg-muted)] hover:bg-[var(--hover)] transition">
            Collapse
          </button>
        </div>
      {:else}
        <div class="rounded-2xl border border-[var(--border)] bg-[var(--card)] p-4 space-y-3">
          <p class="text-sm font-semibold text-[var(--fg)]">Confirm {ACTION[actionType].label.toLowerCase()}</p>
          <p class="text-sm text-[var(--fg-muted)]">
            Move <strong>{selected.size}</strong> student{selected.size > 1 ? 's' : ''} from
            <strong>{classData.display_name}</strong> →
            <strong>{allClasses.find(c => c.id === toClassId)?.display_name ?? '—'}</strong>
            ({years.find(y => y.id === toYearId)?.name ?? '—'})
            {#if alsoEnroll && firstTerm}, then register in <strong>{firstTerm.name}</strong>{/if}.
          </p>
          {#if actionType === 'demote'}
            <p class="rounded-lg bg-amber-50 px-3 py-2 text-xs font-medium text-amber-700 dark:bg-amber-950/30 dark:text-amber-400">
              Demotion is uncommon — double-check the target class before confirming.
            </p>
          {/if}
          <div class="flex gap-2">
            <button onclick={() => $promoteMut.mutate(undefined)} disabled={$promoteMut.isPending}
              class="rounded-xl px-5 py-2 text-sm font-semibold text-white transition hover:opacity-90 disabled:opacity-50"
              style="background: {actionType === 'demote' ? '#dc2626' : 'var(--brand)'}">
              {$promoteMut.isPending ? 'Processing…' : `Confirm ${ACTION[actionType].label}`}
            </button>
            <button onclick={() => { confirmOpen = false; error = ''; }}
              class="rounded-xl border border-[var(--border)] px-4 py-2 text-sm text-[var(--fg-muted)] hover:bg-[var(--hover)] transition">
              Back
            </button>
          </div>
        </div>
      {/if}
    {/if}

  </div>
{/if}

<OverrideReasonModal
  open={overrideNeeded}
  title="Class mismatch"
  errorMessage={overrideError}
  isPending={$promoteMut.isPending}
  onSubmit={(reason) => $promoteMut.mutate(reason)}
  onCancel={() => { overrideNeeded = false; overrideError = ''; }}
/>
