<script lang="ts">
  import { createQuery, createMutation, useQueryClient } from '@tanstack/svelte-query';
  import { listSubjects, listClassSubjects, assignSubjects, type Subject } from '$lib/api/academic';
  import { portal } from '$lib/actions/portal';

  const { classId, className, onclose } = $props<{
    classId: string;
    className: string;
    onclose: () => void;
  }>();

  const qc = useQueryClient();

  const subjectsQuery = createQuery({
    queryKey: ['subjects'],
    queryFn: listSubjects,
    staleTime: 5 * 60_000,
  });

  const classSubjectsQuery = createQuery({
    queryKey: ['class-subjects', classId],
    queryFn: () => listClassSubjects(classId),
    staleTime: 0,
  });

  let selectedIds = $state<Set<string>>(new Set());
  let assignError = $state('');

  $effect(() => {
    if ($classSubjectsQuery.data) {
      selectedIds = new Set($classSubjectsQuery.data.map((cs: { subject_id: string }) => cs.subject_id));
    }
  });

  const assignMut = createMutation({
    mutationFn: (ids: string[]) => assignSubjects(classId, ids),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['class-subjects', classId] });
      onclose();
    },
    onError: (e: unknown) => {
      assignError = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? 'Failed to assign subjects.';
    },
  });

  function toggle(id: string) {
    const next = new Set(selectedIds);
    if (next.has(id)) next.delete(id); else next.add(id);
    selectedIds = next;
  }
</script>

<div use:portal class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50"
     role="dialog" aria-modal="true"
     onclick={(e) => { if (e.target === e.currentTarget) onclose(); }}>
  <div class="w-full max-w-md rounded-xl border border-[var(--border)] bg-[var(--card)] p-6 shadow-2xl">
    <div class="mb-4 flex items-center justify-between">
      <div>
        <h2 class="font-semibold text-[var(--fg)]">Assign subjects</h2>
        <p class="text-xs text-[var(--fg-muted)]">{className}</p>
      </div>
      <button onclick={onclose}
        class="flex h-8 w-8 items-center justify-center rounded-full text-[var(--fg-muted)] transition hover:bg-[var(--bg)]">
        <svg class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12"/>
        </svg>
      </button>
    </div>

    {#if assignError}<p class="mb-3 text-xs text-red-500">{assignError}</p>{/if}

    <div class="mb-4 max-h-72 space-y-1.5 overflow-y-auto">
      {#if $classSubjectsQuery.isPending}
        {#each [1,2,3] as _}
          <div class="skeleton h-10"></div>
        {/each}
      {:else}
        {#each ($subjectsQuery.data ?? []).filter((s: Subject) => s.is_active) as subj (subj.id)}
          <button type="button" onclick={() => toggle(subj.id)}
            class="flex w-full items-center gap-3 rounded-xl border px-4 py-2.5 text-left text-sm transition
                   {selectedIds.has(subj.id)
                     ? 'border-[var(--brand)] bg-[var(--brand)]/5 text-[var(--fg)]'
                     : 'border-[var(--border)] text-[var(--fg-muted)] hover:text-[var(--fg)]'}">
            <div class="flex h-4 w-4 shrink-0 items-center justify-center rounded border
                        {selectedIds.has(subj.id) ? 'border-[var(--brand)]' : 'border-[var(--border)]'}"
                 style="{selectedIds.has(subj.id) ? 'background-color: var(--brand)' : ''}">
              {#if selectedIds.has(subj.id)}
                <svg class="h-2.5 w-2.5 text-white" fill="none" stroke="currentColor" stroke-width="3" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7"/>
                </svg>
              {/if}
            </div>
            <span class="w-12 shrink-0 font-mono text-xs text-[var(--fg-muted)]">{subj.code}</span>
            <span>{subj.name}</span>
          </button>
        {/each}
      {/if}
    </div>

    <div class="flex gap-2">
      <button
        onclick={() => $assignMut.mutate([...selectedIds])}
        disabled={selectedIds.size === 0 || $assignMut.isPending}
        class="flex-1 rounded-xl py-2.5 text-sm font-semibold text-white transition hover:opacity-90 disabled:opacity-40"
        style="background-color: var(--brand)">
        {$assignMut.isPending ? 'Assigning…' : `Assign ${selectedIds.size || ''} subject${selectedIds.size !== 1 ? 's' : ''}`}
      </button>
      <button onclick={onclose}
        class="rounded-xl border border-[var(--border)] px-4 py-2.5 text-sm font-medium text-[var(--fg-muted)] transition hover:bg-[var(--bg)]">
        Cancel
      </button>
    </div>
  </div>
</div>
