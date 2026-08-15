<script lang="ts">
  import { createQuery, useQueryClient } from '@tanstack/svelte-query';
  import { writable } from 'svelte/store';
  import { listStudents, assignStudentToClass } from '$lib/api/students';
  import { listYears } from '$lib/api/academic';
  import { findCurrentYear } from '$lib/academicPeriod';
  import { toast } from '$lib/stores/toast';

  interface Props {
    classId: string;
    assignedIds: Set<string>;
    onClose: () => void;
  }
  const { classId, assignedIds, onClose }: Props = $props();

  const qc = useQueryClient();

  let assignYearId = $state('');
  let search       = $state('');
  let selected     = $state(new Set<string>());
  let assigning    = $state(false);
  let assignError  = $state('');

  const yearsQ = createQuery({ queryKey: ['academic-years'], queryFn: listYears, staleTime: 5 * 60_000 });

  const searchOpts = writable({
    queryKey: ['students', 'search', search] as const,
    queryFn: () => listStudents({ active_only: true, search, limit: 50 }),
    enabled: false,
    staleTime: 30_000,
  });
  $effect(() => {
    const s = search; const active = s.trim().length >= 2;
    searchOpts.set({ queryKey: ['students', 'search', s] as const, queryFn: () => listStudents({ active_only: true, search: s, limit: 50 }), enabled: active, staleTime: 30_000 });
  });
  const searchQ = createQuery(searchOpts);
  const results = $derived(($searchQ.data ?? []).filter(s => !assignedIds.has(s.id)));

  $effect(() => {
    if (assignYearId) return;
    const cur = findCurrentYear($yearsQ.data ?? []);
    if (cur) assignYearId = cur.id;
  });

  $effect(() => {
    const visible = new Set(results.map(s => s.id));
    const pruned = new Set([...selected].filter(id => visible.has(id)));
    if (pruned.size !== selected.size) selected = pruned;
  });

  function toggle(id: string) {
    const next = new Set(selected);
    next.has(id) ? next.delete(id) : next.add(id);
    selected = next;
  }
  function toggleAll() {
    selected = selected.size === results.length ? new Set() : new Set(results.map(s => s.id));
  }

  const COLORS = ['#3b82f6','#8b5cf6','#10b981','#f59e0b','#ef4444','#ec4899','#14b8a6','#f97316'];
  function avatarBg(name: string): string {
    let h = 0; for (const c of name) h = (h * 31 + c.charCodeAt(0)) & 0xff;
    return COLORS[h % COLORS.length];
  }
  function initials(name: string): string {
    const p = name.trim().split(/\s+/);
    return (p[0][0] + (p[1]?.[0] ?? '')).toUpperCase();
  }

  async function submit() {
    if (!assignYearId) { assignError = 'Select an academic year.'; return; }
    if (selected.size === 0) { assignError = 'Select at least one student.'; return; }
    assigning = true; assignError = '';

    const ids = [...selected];
    const settled = await Promise.allSettled(
      ids.map(student_id => assignStudentToClass({ student_id, class_id: classId, academic_year_id: assignYearId }))
    );

    let okCount = 0;
    const failedNames: string[] = [];
    settled.forEach((r, i) => {
      if (r.status === 'fulfilled') { okCount++; }
      else {
        const name = ($searchQ.data ?? []).find(s => s.id === ids[i])?.display_name ?? ids[i];
        const detail = (r.reason as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? 'failed';
        failedNames.push(`${name}: ${detail}`);
      }
    });

    assigning = false;
    if (okCount > 0) {
      await qc.invalidateQueries({ queryKey: ['students', 'class', classId] });
      toast.success(`${okCount} student${okCount !== 1 ? 's' : ''} assigned.`);
    }
    if (failedNames.length > 0) { assignError = failedNames.join(' · '); }
    else { onClose(); }
  }

  const inp = 'w-full rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--fg)] focus:border-[var(--brand)] focus:outline-none transition';
</script>

<div class="rounded-2xl border border-[var(--border)] bg-[var(--card)] p-4 space-y-3">
  <!-- Header -->
  <div class="flex items-center justify-between">
    <p class="text-xs font-semibold text-[var(--fg)]">
      Assign students
      {#if selected.size > 0}
        <span class="ml-1.5 rounded-full px-2 py-0.5 text-[10px] font-bold text-white" style="background:var(--brand)">{selected.size} selected</span>
      {/if}
    </p>
    <button onclick={onClose} class="text-xs text-[var(--fg-muted)] transition hover:text-[var(--fg)]">Cancel</button>
  </div>

  <!-- Academic year -->
  <div>
    <label class="mb-1 block text-xs font-medium text-[var(--fg-muted)]">Academic year *</label>
    <select bind:value={assignYearId} class={inp}>
      <option value="">Select year…</option>
      {#each $yearsQ.data ?? [] as y (y.id)}<option value={y.id}>{y.name}{y.is_current ? ' (current)' : ''}</option>{/each}
    </select>
  </div>

  <!-- Search -->
  <div>
    <label class="mb-1 block text-xs font-medium text-[var(--fg-muted)]">Search students</label>
    <input bind:value={search} placeholder="Type at least 2 characters…" class={inp} />
  </div>

  <!-- Checklist -->
  {#if search.trim().length >= 2}
    {#if $searchQ.isPending}
      <p class="text-xs text-[var(--fg-subtle)]">Searching…</p>
    {:else if results.length === 0}
      <p class="text-xs text-[var(--fg-subtle)]">No students found matching "{search}".</p>
    {:else}
      <div class="overflow-hidden rounded-xl border border-[var(--border)]">
        <label class="flex cursor-pointer items-center gap-3 border-b border-[var(--border)] bg-[var(--hover)]/40 px-3 py-2 text-xs font-semibold text-[var(--fg-muted)] hover:bg-[var(--hover)]">
          <input type="checkbox"
            checked={selected.size === results.length}
            indeterminate={selected.size > 0 && selected.size < results.length}
            onchange={toggleAll}
            class="h-3.5 w-3.5 rounded accent-[var(--brand)]" />
          {selected.size === results.length ? 'Deselect all' : `Select all (${results.length})`}
        </label>
        <div class="max-h-56 divide-y divide-[var(--border)] overflow-y-auto">
          {#each results as s (s.id)}
            <label class="flex cursor-pointer items-center gap-3 px-3 py-2.5 hover:bg-[var(--hover)]">
              <input type="checkbox" checked={selected.has(s.id)} onchange={() => toggle(s.id)}
                class="h-3.5 w-3.5 shrink-0 rounded accent-[var(--brand)]" />
              <div class="flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-[10px] font-bold text-white"
                   style="background:{avatarBg(s.display_name)}">{initials(s.display_name)}</div>
              <div class="min-w-0 flex-1">
                <p class="truncate text-sm font-medium text-[var(--fg)]">{s.display_name}</p>
                <p class="font-mono text-[10px] text-[var(--fg-muted)]">{s.admission_number}{s.current_class_name ? ` · ${s.current_class_name}` : ''}</p>
              </div>
            </label>
          {/each}
        </div>
      </div>
    {/if}
  {/if}

  {#if assignError}
    <p class="rounded-lg bg-red-50 px-3 py-2 text-xs text-red-600 dark:bg-red-950/30 dark:text-red-400">{assignError}</p>
  {/if}

  <div class="flex gap-2">
    <button onclick={submit} disabled={assigning || selected.size === 0}
      class="rounded-xl px-4 py-1.5 text-xs font-semibold text-white transition hover:opacity-90 disabled:opacity-50"
      style="background:var(--brand)">
      {assigning ? 'Assigning…' : selected.size > 0 ? `Assign ${selected.size} student${selected.size !== 1 ? 's' : ''}` : 'Assign'}
    </button>
    <button onclick={onClose}
      class="rounded-xl border border-[var(--border)] px-3 py-1.5 text-xs text-[var(--fg-muted)] transition hover:bg-[var(--hover)]">
      Cancel
    </button>
  </div>
</div>
