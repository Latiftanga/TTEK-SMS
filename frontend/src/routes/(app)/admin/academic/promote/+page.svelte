<script lang="ts">
  import { createQuery, createMutation, useQueryClient } from '@tanstack/svelte-query';
  import { listClasses, listYears, type SchoolClass, type AcademicYear } from '$lib/api/academic';
  import { listStudents, bulkAssignStudentsToClass, bulkEnrollStudents } from '$lib/api/students';
  import { writable } from 'svelte/store';
  import { toast } from '$lib/stores/toast';
  import { setPageTitle } from '$lib/stores/title';

  const qc = useQueryClient();
  setPageTitle('Bulk Promotion');

  const classesQ = createQuery({ queryKey: ['classes'],        queryFn: listClasses, staleTime: 5 * 60_000 });
  const yearsQ   = createQuery({ queryKey: ['academic-years'], queryFn: listYears,   staleTime: 5 * 60_000 });

  // ── Selections ────────────────────────────────────────────────────────────────
  let fromClassId = $state('');
  let toClassId   = $state('');
  let toYearId    = $state('');
  let alsoEnroll  = $state(true); // also register in first term of target year

  const classes = $derived<SchoolClass[]>($classesQ.data ?? []);
  const years   = $derived<AcademicYear[]>(
    [...($yearsQ.data ?? [])].sort((a, b) => b.start_date.localeCompare(a.start_date))
  );

  // Suggest the next-year class when "from" is chosen
  const fromClass = $derived(classes.find(c => c.id === fromClassId));
  const suggestedToClass = $derived.by(() => {
    if (!fromClass) return null;
    return classes.find(
      c => c.level === fromClass.level
        && c.year_group === fromClass.year_group + 1
        && c.programme_id === fromClass.programme_id
        && (c.stream ?? null) === (fromClass.stream ?? null)
    ) ?? null;
  });

  // Auto-fill target class when suggestion available and not yet manually chosen
  let toClassManual = $state(false);
  $effect(() => {
    if (suggestedToClass && !toClassManual) toClassId = suggestedToClass.id;
  });

  // First term of target year (for enroll-on-promote)
  const targetYear = $derived(years.find(y => y.id === toYearId));
  const firstTerm  = $derived(
    [...(targetYear?.terms ?? [])].sort((a, b) => a.start_date.localeCompare(b.start_date))[0] ?? null
  );

  // ── Load students from source class ──────────────────────────────────────────
  const studentOpts = writable({
    queryKey: ['students', 'class', fromClassId] as const,
    queryFn: () => listStudents({ class_id: fromClassId, active_only: true }),
    enabled: false,
    staleTime: 60_000,
  });
  $effect(() => {
    const cid = fromClassId;
    studentOpts.set({
      queryKey: ['students', 'class', cid] as const,
      queryFn: () => listStudents({ class_id: cid, active_only: true }),
      enabled: !!cid,
      staleTime: 60_000,
    });
  });
  const studentsQ = createQuery(studentOpts);
  const students  = $derived($studentsQ.data ?? []);

  // ── Selection ─────────────────────────────────────────────────────────────────
  let selected = $state(new Set<string>());

  $effect(() => {
    // Clear selection when source class changes
    void fromClassId; selected = new Set();
  });

  const allSelected = $derived(students.length > 0 && selected.size === students.length);

  function toggleAll() {
    selected = allSelected ? new Set() : new Set(students.map(s => s.id));
  }
  function toggleOne(id: string) {
    const s = new Set(selected);
    s.has(id) ? s.delete(id) : s.add(id);
    selected = s;
  }

  // ── Promote mutation ──────────────────────────────────────────────────────────
  type ActionType = 'promote' | 'repeat' | 'demote';
  let actionType: ActionType = $state('promote');
  let confirmOpen = $state(false);
  let promoteErr  = $state('');

  const promoteMut = createMutation({
    mutationFn: async () => {
      const items = [...selected].map(sid => ({
        student_id: sid, class_id: toClassId, academic_year_id: toYearId,
      }));
      const result = await bulkAssignStudentsToClass(items);

      if (alsoEnroll && firstTerm) {
        const enrollItems = [...selected].map(sid => ({
          student_id: sid, academic_term_id: firstTerm.id,
        }));
        await bulkEnrollStudents(enrollItems);
      }

      return result;
    },
    onSuccess: (res) => {
      qc.invalidateQueries({ queryKey: ['students', 'class', fromClassId] });
      qc.invalidateQueries({ queryKey: ['student-class-assignments'] });
      const label = actionType === 'promote' ? 'Promoted' : actionType === 'repeat' ? 'Re-enrolled' : 'Demoted';
      toast.success(`${label}: ${res.enrolled} student(s). Skipped: ${res.skipped} (already assigned).`);
      selected = new Set(); confirmOpen = false; promoteErr = '';
    },
    onError: (e: unknown) => {
      promoteErr = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
        ?? 'Could not complete operation.';
      confirmOpen = false;
    },
  });

  function handlePromote() {
    promoteErr = '';
    if (!fromClassId) { promoteErr = 'Select a source class.'; return; }
    if (!toClassId)   { promoteErr = 'Select a target class.'; return; }
    if (!toYearId)    { promoteErr = 'Select a target academic year.'; return; }
    if (selected.size === 0) { promoteErr = 'Select at least one student.'; return; }
    confirmOpen = true;
  }

  const ACTION_LABELS: Record<ActionType, { label: string; color: string; desc: string }> = {
    promote: { label: 'Promote',     color: 'text-green-600 dark:text-green-400',  desc: 'Move up to the next year group' },
    repeat:  { label: 'Repeat year', color: 'text-amber-600 dark:text-amber-400',  desc: 'Re-enroll in the same class for a new year' },
    demote:  { label: 'Demote',      color: 'text-red-600 dark:text-red-400',      desc: 'Move down to a lower year group' },
  };
</script>


<div class="space-y-6">
  <div>
    <h1 class="text-xl font-bold text-[var(--fg)]">Class Promotion</h1>
    <p class="mt-0.5 text-sm text-[var(--fg-muted)]">Move a group of students to a new class for the next academic year.</p>
  </div>

  <!-- Action type selector -->
  <div class="flex gap-2">
    {#each Object.entries(ACTION_LABELS) as [key, meta]}
      <button onclick={() => { actionType = key as ActionType; toClassManual = false; }}
        class="flex-1 rounded-xl border px-4 py-3 text-left transition
               {actionType === key
                 ? 'border-[var(--brand)] bg-[var(--brand)]/5 ring-1 ring-[var(--brand)]'
                 : 'border-[var(--border)] bg-[var(--card)] hover:border-[var(--brand)]/40'}">
        <p class="text-sm font-semibold {actionType === key ? meta.color : 'text-[var(--fg)]'}">{meta.label}</p>
        <p class="mt-0.5 text-[11px] text-[var(--fg-muted)]">{meta.desc}</p>
      </button>
    {/each}
  </div>

  <!-- Config card -->
  <div class="rounded-2xl border border-[var(--border)] bg-[var(--card)] p-5">
    <div class="grid gap-4 sm:grid-cols-2">
      <!-- From -->
      <div class="space-y-3 rounded-xl border border-[var(--border)] p-4">
        <p class="text-[10px] font-bold uppercase tracking-widest text-[var(--fg-subtle)]">From</p>
        <div>
          <label class="lx">Source class</label>
          <select bind:value={fromClassId} onchange={() => toClassManual = false} class="sel mt-1">
            <option value="">Select class…</option>
            {#each classes as c}<option value={c.id}>{c.display_name}</option>{/each}
          </select>
        </div>
      </div>

      <!-- To -->
      <div class="space-y-3 rounded-xl border border-[var(--border)] p-4">
        <p class="text-[10px] font-bold uppercase tracking-widest text-[var(--fg-subtle)]">To</p>
        <div>
          <label class="lx">Target academic year</label>
          <select bind:value={toYearId} class="sel mt-1">
            <option value="">Select year…</option>
            {#each years as y}<option value={y.id}>{y.name}{y.is_current ? ' (current)' : ''}</option>{/each}
          </select>
        </div>
        <div>
          <label class="lx">Target class
            {#if suggestedToClass && !toClassManual}
              <span class="ml-1 rounded-full bg-green-50 px-1.5 py-0.5 text-[10px] font-semibold text-green-700 dark:bg-green-950/30 dark:text-green-400">suggested</span>
            {/if}
          </label>
          <select bind:value={toClassId} onchange={() => toClassManual = true} class="sel mt-1">
            <option value="">Select class…</option>
            {#each classes as c}<option value={c.id}>{c.display_name}</option>{/each}
          </select>
        </div>
      </div>
    </div>

    <!-- Also enroll in first term -->
    {#if toYearId && firstTerm}
      <label class="mt-4 flex cursor-pointer items-center gap-2.5">
        <input type="checkbox" bind:checked={alsoEnroll} class="h-4 w-4 rounded accent-[var(--brand)]" />
        <span class="text-sm text-[var(--fg)]">
          Also register students in <strong>{firstTerm.name}</strong> (first term of selected year)
        </span>
      </label>
    {/if}
  </div>

  <!-- Student list -->
  {#if !fromClassId}
    <div class="rounded-2xl border border-dashed border-[var(--border)] py-12 text-center">
      <p class="text-sm text-[var(--fg-muted)]">Select a source class to see students.</p>
    </div>
  {:else if $studentsQ.isPending}
    <div class="space-y-2">{#each [1,2,3,4,5] as _}<div class="h-12 animate-pulse rounded-xl bg-[var(--card)]"></div>{/each}</div>
  {:else if students.length === 0}
    <div class="rounded-2xl border border-dashed border-[var(--border)] py-12 text-center">
      <p class="text-sm text-[var(--fg-muted)]">No active students found in this class.</p>
    </div>
  {:else}
    <div class="overflow-hidden rounded-2xl border border-[var(--border)] bg-[var(--card)]">
      <!-- List header -->
      <div class="flex items-center justify-between border-b border-[var(--border)] px-4 py-3">
        <label class="flex cursor-pointer items-center gap-2.5 text-sm font-medium text-[var(--fg)]">
          <input type="checkbox" checked={allSelected} onchange={toggleAll} class="h-4 w-4 rounded accent-[var(--brand)]" />
          {selected.size > 0 ? `${selected.size} of ${students.length} selected` : `${students.length} students`}
        </label>
        {#if selected.size > 0}
          <button onclick={() => selected = new Set()} class="text-xs text-[var(--fg-muted)] hover:text-[var(--fg)] transition">
            Clear selection
          </button>
        {/if}
      </div>

      {#each students as s (s.id)}
        <label class="flex cursor-pointer items-center gap-3 border-b border-[var(--border)] px-4 py-3 last:border-0
                       transition hover:bg-[var(--hover)] {selected.has(s.id) ? 'bg-[var(--brand)]/5' : ''}">
          <input type="checkbox" checked={selected.has(s.id)} onchange={() => toggleOne(s.id)}
            class="h-4 w-4 shrink-0 rounded accent-[var(--brand)]" />
          <div class="flex-1 min-w-0">
            <p class="text-sm font-medium text-[var(--fg)]">{s.display_name}</p>
            <p class="text-[10px] font-mono text-[var(--fg-subtle)]">{s.admission_number}</p>
          </div>
          <span class="shrink-0 text-[10px] font-medium
                        {s.gender === 'MALE' ? 'text-blue-600 dark:text-blue-400' : 'text-pink-600 dark:text-pink-400'}">
            {s.gender ?? '—'}
          </span>
        </label>
      {/each}
    </div>

    <!-- Action bar -->
    {#if promoteErr}
      <p class="rounded-xl bg-red-50 px-4 py-2.5 text-sm text-red-600 dark:bg-red-950/30 dark:text-red-400">{promoteErr}</p>
    {/if}

    {#if !confirmOpen}
      <button onclick={handlePromote} disabled={selected.size === 0}
        class="w-full rounded-xl py-3 text-sm font-semibold text-white transition hover:opacity-90 disabled:opacity-40"
        style="background: var(--brand)">
        {ACTION_LABELS[actionType].label} {selected.size > 0 ? `${selected.size} student${selected.size > 1 ? 's' : ''}` : 'selected'} →
      </button>
    {:else}
      <div class="rounded-2xl border border-[var(--border)] bg-[var(--card)] p-5">
        <p class="text-sm font-semibold text-[var(--fg)]">Confirm {ACTION_LABELS[actionType].label.toLowerCase()}</p>
        <p class="mt-1 text-sm text-[var(--fg-muted)]">
          Move <strong>{selected.size}</strong> student{selected.size > 1 ? 's' : ''} from
          <strong>{fromClass?.display_name}</strong> →
          <strong>{classes.find(c => c.id === toClassId)?.display_name ?? '—'}</strong>
          ({years.find(y => y.id === toYearId)?.name ?? '—'})
          {#if alsoEnroll && firstTerm}, then register in <strong>{firstTerm.name}</strong>{/if}.
        </p>
        {#if actionType === 'demote'}
          <p class="mt-2 rounded-lg bg-amber-50 px-3 py-2 text-xs font-medium text-amber-700 dark:bg-amber-950/30 dark:text-amber-400">
            Demotion is uncommon. Double-check the target class before confirming.
          </p>
        {/if}
        <div class="mt-4 flex gap-2">
          <button onclick={() => $promoteMut.mutate()} disabled={$promoteMut.isPending}
            class="rounded-xl px-5 py-2 text-sm font-semibold text-white transition hover:opacity-90 disabled:opacity-50"
            style="background: {actionType === 'demote' ? '#dc2626' : 'var(--brand)'}">
            {$promoteMut.isPending ? 'Processing…' : `Confirm ${ACTION_LABELS[actionType].label}`}
          </button>
          <button onclick={() => { confirmOpen = false; promoteErr = ''; }}
            class="rounded-xl border border-[var(--border)] px-5 py-2 text-sm text-[var(--fg-muted)] hover:bg-[var(--hover)] transition">
            Cancel
          </button>
        </div>
      </div>
    {/if}
  {/if}
</div>

<style>
  @reference "tailwindcss";
  .lx  { @apply block text-xs font-medium text-[var(--fg-muted)]; }
  .sel { @apply w-full rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--fg)] focus:border-[var(--brand)] focus:outline-none transition; }
</style>
