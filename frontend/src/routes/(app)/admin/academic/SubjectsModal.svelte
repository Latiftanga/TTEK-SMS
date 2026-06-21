<script lang="ts">
  import { createQuery, createMutation, useQueryClient } from '@tanstack/svelte-query';
  import {
    listClassSubjects, listSubjects, assignSubjects, removeClassSubject,
    type Subject,
  } from '$lib/api/academic';
  import { portal } from '$lib/actions/portal';
  import { toast } from '$lib/stores/toast';

  interface Props { classId: string; className: string; onClose: () => void; }
  const { classId, className, onClose }: Props = $props();

  const qc = useQueryClient();

  const clsSubjQ = createQuery({ queryKey: ['class-subjects', classId], queryFn: () => listClassSubjects(classId), staleTime: 2 * 60_000 });
  const allSubjQ = createQuery({ queryKey: ['subjects'],               queryFn: listSubjects,                    staleTime: 5 * 60_000 });

  const classSubjects = $derived($clsSubjQ.data ?? []);
  const allSubjects   = $derived<Subject[]>($allSubjQ.data ?? []);
  const subjectMap    = $derived(new Map(allSubjects.map(s => [s.id, s])));
  const assignedIds   = $derived(new Set(classSubjects.map(cs => cs.subject_id)));
  const unassigned    = $derived(allSubjects.filter(s => s.is_active && !assignedIds.has(s.id)));

  let addSearch = $state('');
  let toAdd     = $state(new Set<string>());

  const filtered = $derived(unassigned.filter(s =>
    !addSearch.trim() || s.name.toLowerCase().includes(addSearch.toLowerCase()) || s.code.toLowerCase().includes(addSearch.toLowerCase())
  ));

  function toggleAdd(id: string) { const n = new Set(toAdd); n.has(id) ? n.delete(id) : n.add(id); toAdd = n; }

  const addMut = createMutation({
    mutationFn: () => assignSubjects(classId, [...toAdd]),
    onSuccess: (added) => {
      qc.invalidateQueries({ queryKey: ['class-subjects', classId] });
      toAdd = new Set(); addSearch = '';
      toast.success(`${added.length} subject${added.length !== 1 ? 's' : ''} added.`);
    },
    onError: (e: unknown) => toast.error((e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? 'Failed to add subjects.'),
  });

  const removeMut = createMutation({
    mutationFn: (subjectId: string) => removeClassSubject(classId, subjectId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['class-subjects', classId] }),
    onError: (e: unknown) => toast.error((e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? 'Failed to remove subject.'),
  });
</script>

<div use:portal class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
  <div class="flex w-full max-w-md flex-col rounded-2xl border border-[var(--border)] bg-[var(--card)] shadow-2xl">

    <!-- Header -->
    <div class="flex items-center justify-between border-b border-[var(--border)] px-6 py-4">
      <div>
        <h2 class="text-base font-semibold text-[var(--fg)]">Subjects</h2>
        <p class="text-xs text-[var(--fg-muted)]">{className}</p>
      </div>
      <button onclick={onClose} class="rounded-lg p-1.5 text-[var(--fg-muted)] transition hover:bg-[var(--hover)] hover:text-[var(--fg)]">
        <svg class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12"/></svg>
      </button>
    </div>

    <div class="flex-1 overflow-y-auto p-6 space-y-5" style="max-height: 70vh">

      <!-- Assigned list -->
      {#if $clsSubjQ.isPending}
        <div class="space-y-2">{#each [1,2,3] as _}<div class="h-9 animate-pulse rounded-xl bg-[var(--hover)]"></div>{/each}</div>
      {:else if classSubjects.length === 0}
        <p class="text-sm text-[var(--fg-muted)]">No subjects assigned yet.</p>
      {:else}
        <div>
          <p class="mb-2 text-xs font-medium text-[var(--fg-muted)]">Assigned · {classSubjects.length}</p>
          <div class="divide-y divide-[var(--border)] rounded-xl border border-[var(--border)]">
            {#each classSubjects as cs (cs.subject_id)}
              {@const s = subjectMap.get(cs.subject_id)}
              <div class="flex items-center gap-3 px-4 py-2.5">
                <span class="flex-1 text-sm text-[var(--fg)]">{s?.name ?? '—'}</span>
                <span class="text-xs text-[var(--fg-subtle)]">{s?.code ?? ''}</span>
                <button onclick={() => $removeMut.mutate(cs.subject_id)} disabled={$removeMut.isPending}
                  class="ml-2 text-xs text-red-500 transition hover:text-red-700 disabled:opacity-40">Remove</button>
              </div>
            {/each}
          </div>
        </div>
      {/if}

      <!-- Add subjects -->
      <div>
        <p class="mb-2 text-xs font-medium text-[var(--fg-muted)]">Add subjects</p>
        <input bind:value={addSearch} placeholder="Search subjects…"
          class="mb-2 w-full rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--fg)] focus:border-[var(--brand)] focus:outline-none transition" />
        <div class="max-h-44 overflow-y-auto divide-y divide-[var(--border)] rounded-xl border border-[var(--border)]">
          {#if filtered.length === 0}
            <p class="px-4 py-4 text-center text-sm text-[var(--fg-muted)]">
              {unassigned.length === 0 ? 'All subjects already assigned.' : 'No matches.'}
            </p>
          {:else}
            {#each filtered as s (s.id)}
              <label class="flex cursor-pointer items-center gap-3 px-4 py-2.5 transition hover:bg-[var(--hover)]">
                <input type="checkbox" checked={toAdd.has(s.id)} onchange={() => toggleAdd(s.id)} class="rounded accent-[var(--brand)]" />
                <span class="flex-1 text-sm text-[var(--fg)]">{s.name}</span>
                <span class="text-xs text-[var(--fg-subtle)]">{s.code}</span>
              </label>
            {/each}
          {/if}
        </div>
      </div>
    </div>

    <!-- Footer -->
    <div class="flex items-center justify-between border-t border-[var(--border)] px-6 py-3">
      <span class="text-xs text-[var(--fg-muted)]">{toAdd.size > 0 ? `${toAdd.size} selected` : ''}</span>
      <div class="flex gap-3">
        <button onclick={onClose} class="rounded-xl border border-[var(--border)] px-4 py-2 text-sm text-[var(--fg-muted)] transition hover:bg-[var(--hover)]">Close</button>
        <button onclick={() => $addMut.mutate()} disabled={toAdd.size === 0 || $addMut.isPending}
          class="rounded-xl px-4 py-2 text-sm font-semibold text-white disabled:opacity-40 transition hover:opacity-90" style="background: var(--brand)">
          {$addMut.isPending ? 'Adding…' : `Add ${toAdd.size || ''}`}
        </button>
      </div>
    </div>
  </div>
</div>
