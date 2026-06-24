<script lang="ts">
  import { createQuery, createMutation, useQueryClient } from '@tanstack/svelte-query';
  import {
    listClassSubjects, listSubjects, assignSubjects, removeClassSubject,
    type Subject,
  } from '$lib/api/academic';
  import { toast } from '$lib/stores/toast';

  interface Props { classId: string; }
  const { classId }: Props = $props();

  const qc = useQueryClient();

  const clsSubjQ = createQuery({ queryKey: ['class-subjects', classId], queryFn: () => listClassSubjects(classId), staleTime: 2 * 60_000 });
  const allSubjQ = createQuery({ queryKey: ['subjects'],               queryFn: listSubjects,                    staleTime: 5 * 60_000 });

  const classSubjects = $derived($clsSubjQ.data ?? []);
  const allSubjects   = $derived<Subject[]>($allSubjQ.data ?? []);
  const subjectMap    = $derived(new Map(allSubjects.map(s => [s.id, s])));
  const assignedIds   = $derived(new Set(classSubjects.map(cs => cs.subject_id)));
  const unassigned    = $derived(allSubjects.filter(s => s.is_active && !assignedIds.has(s.id)));

  let showAdd   = $state(false);
  let addSearch = $state('');
  let toAdd     = $state(new Set<string>());

  const filtered = $derived(unassigned.filter(s =>
    !addSearch.trim()
    || s.name.toLowerCase().includes(addSearch.toLowerCase())
    || s.code.toLowerCase().includes(addSearch.toLowerCase())
  ));

  function toggleAdd(id: string) { const n = new Set(toAdd); n.has(id) ? n.delete(id) : n.add(id); toAdd = n; }

  const addMut = createMutation({
    mutationFn: () => assignSubjects(classId, [...toAdd]),
    onSuccess: (added) => {
      qc.invalidateQueries({ queryKey: ['class-subjects', classId] });
      toAdd = new Set(); addSearch = ''; showAdd = false;
      toast.success(`${added.length} subject${added.length !== 1 ? 's' : ''} added.`);
    },
    onError: (e: unknown) => toast.error(
      (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? 'Failed to add subjects.'
    ),
  });

  const removeMut = createMutation({
    mutationFn: (subjectId: string) => removeClassSubject(classId, subjectId),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['class-subjects', classId] }); toast.success('Subject removed.'); },
    onError: (e: unknown) => toast.error(
      (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? 'Failed to remove subject.'
    ),
  });
</script>

<div class="space-y-4">
  <!-- Assigned subjects -->
  {#if $clsSubjQ.isPending}
    <div class="space-y-2">{#each [1,2,3] as _}<div class="h-12 animate-pulse rounded-xl bg-[var(--card)]"></div>{/each}</div>
  {:else if classSubjects.length === 0}
    <div class="rounded-2xl border border-dashed border-[var(--border)] px-6 py-12 text-center">
      <p class="text-sm font-medium text-[var(--fg-muted)]">No subjects assigned yet.</p>
      <button onclick={() => showAdd = true}
        class="mt-3 rounded-xl px-4 py-2 text-sm font-semibold text-white transition hover:opacity-90"
        style="background: var(--brand)">Assign subjects</button>
    </div>
  {:else}
    <div class="overflow-hidden rounded-2xl border border-[var(--border)] bg-[var(--card)]">
      <div class="flex items-center justify-between border-b border-[var(--border)] px-4 py-2.5">
        <p class="text-[10px] font-bold uppercase tracking-widest text-[var(--fg-subtle)]">{classSubjects.length} subject{classSubjects.length !== 1 ? 's' : ''} assigned</p>
        <button onclick={() => { showAdd = !showAdd; addSearch = ''; toAdd = new Set(); }}
          class="flex items-center gap-1 text-xs font-semibold transition hover:opacity-70" style="color:var(--brand)">
          <svg class="h-3.5 w-3.5" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" d="M12 4v16m8-8H4"/>
          </svg>
          Add
        </button>
      </div>
      {#each classSubjects as cs (cs.subject_id)}
        {@const s = subjectMap.get(cs.subject_id)}
        <div class="flex items-center gap-3 border-b border-[var(--border)] px-4 py-3 last:border-0">
          <div class="flex-1 min-w-0">
            <p class="text-sm font-medium text-[var(--fg)]">{s?.name ?? '—'}</p>
            <p class="font-mono text-[10px] text-[var(--fg-subtle)]">{s?.code ?? ''}</p>
          </div>
          <button onclick={() => $removeMut.mutate(cs.subject_id)}
            disabled={$removeMut.isPending && $removeMut.variables === cs.subject_id}
            class="rounded-lg border border-[var(--border)] px-2.5 py-1 text-xs text-red-500 transition hover:border-red-300 hover:bg-red-50 disabled:opacity-40 dark:hover:bg-red-950/20">
            Remove
          </button>
        </div>
      {/each}
    </div>
  {/if}

  <!-- Add panel (inline, not modal) -->
  {#if showAdd && unassigned.length > 0}
    <div class="rounded-2xl border border-[var(--border)] bg-[var(--card)] p-4">
      <p class="mb-3 text-xs font-semibold text-[var(--fg)]">Add subjects</p>
      <input bind:value={addSearch} placeholder="Search subjects…"
        class="mb-2 w-full rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--fg)] focus:border-[var(--brand)] focus:outline-none transition" />
      <div class="max-h-52 overflow-y-auto divide-y divide-[var(--border)] rounded-xl border border-[var(--border)]">
        {#if filtered.length === 0}
          <p class="px-4 py-4 text-center text-sm text-[var(--fg-muted)]">No matches.</p>
        {:else}
          {#each filtered as s (s.id)}
            <label class="flex cursor-pointer items-center gap-3 px-4 py-2.5 transition hover:bg-[var(--hover)]">
              <input type="checkbox" checked={toAdd.has(s.id)} onchange={() => toggleAdd(s.id)} class="h-4 w-4 rounded accent-[var(--brand)]" />
              <span class="flex-1 text-sm text-[var(--fg)]">{s.name}</span>
              <span class="font-mono text-[10px] text-[var(--fg-subtle)]">{s.code}</span>
            </label>
          {/each}
        {/if}
      </div>
      <div class="mt-3 flex items-center justify-between">
        <span class="text-xs text-[var(--fg-muted)]">{toAdd.size > 0 ? `${toAdd.size} selected` : ''}</span>
        <div class="flex gap-2">
          <button onclick={() => { showAdd = false; toAdd = new Set(); addSearch = ''; }}
            class="rounded-xl border border-[var(--border)] px-3 py-1.5 text-xs text-[var(--fg-muted)] hover:bg-[var(--hover)] transition">Cancel</button>
          <button onclick={() => $addMut.mutate()} disabled={toAdd.size === 0 || $addMut.isPending}
            class="rounded-xl px-4 py-1.5 text-xs font-semibold text-white transition hover:opacity-90 disabled:opacity-40"
            style="background: var(--brand)">
            {$addMut.isPending ? 'Adding…' : `Add ${toAdd.size || ''}`}
          </button>
        </div>
      </div>
    </div>
  {:else if showAdd && unassigned.length === 0}
    <p class="rounded-xl border border-[var(--border)] bg-[var(--card)] px-4 py-3 text-sm text-[var(--fg-muted)]">All available subjects are already assigned.</p>
  {/if}
</div>
