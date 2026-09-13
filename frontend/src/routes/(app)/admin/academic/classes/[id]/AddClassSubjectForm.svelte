<script lang="ts">
  import { createMutation, useQueryClient } from '@tanstack/svelte-query';
  import { assignSubjects, type Subject } from '$lib/api/academic';
  import { apiError } from '$lib/utils';

  interface Props {
    classId: string;
    unassignedSubjs: Subject[];
    onClose: () => void;
  }
  const { classId, unassignedSubjs, onClose }: Props = $props();

  const qc = useQueryClient();

  let search   = $state('');
  let selected = $state<Set<string>>(new Set());
  let addError = $state('');

  const available = $derived(
    unassignedSubjs
      .filter(s => {
        const q = search.trim().toLowerCase();
        return !q || s.name.toLowerCase().includes(q) || s.code.toLowerCase().includes(q);
      })
      .sort((a, b) => a.name.localeCompare(b.name))
  );

  function toggle(id: string) {
    const next = new Set(selected);
    next.has(id) ? next.delete(id) : next.add(id);
    selected = next;
  }

  const addMut = createMutation({
    mutationFn: (subjectIds: string[]) => assignSubjects(classId, subjectIds),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['class-subjects', classId] });
      onClose();
    },
    onError: (e) => { addError = apiError(e, 'Failed to assign subjects.'); },
  });

  function submit() {
    addError = '';
    if (selected.size === 0) { addError = 'Select at least one subject.'; return; }
    $addMut.mutate([...selected]);
  }
</script>

{#if unassignedSubjs.length === 0}
  <p class="rounded-xl border border-[var(--border)] bg-[var(--card)] px-4 py-3 text-sm text-[var(--fg-muted)]">
    All available subjects are already assigned to this class.
  </p>
{:else}
  <div class="rounded-2xl border border-[var(--border)] bg-[var(--card)] p-4 space-y-3">
    <p class="text-xs font-semibold text-[var(--fg)]">Add subjects</p>
    <div class="relative">
      <svg class="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-[var(--fg-muted)]" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M21 21l-4.35-4.35M17 11A6 6 0 111 11a6 6 0 0116 0z"/></svg>
      <input bind:value={search} type="search" placeholder="Search subjects…"
        class="h-9 w-full rounded-xl border border-[var(--border)] bg-[var(--bg)] pl-9 pr-3 text-sm text-[var(--fg)] placeholder:text-[var(--fg-muted)] focus:border-[var(--brand)] focus:outline-none" />
    </div>

    {#if available.length === 0}
      <p class="rounded-xl border border-dashed border-[var(--border)] px-4 py-6 text-center text-sm text-[var(--fg-muted)]">
        No matching subjects.
      </p>
    {:else}
      <div class="max-h-60 overflow-y-auto rounded-xl border border-[var(--border)]">
        {#each available as s (s.id)}
          <label class="flex cursor-pointer items-center gap-3 border-b border-[var(--border)] px-3 py-2 last:border-0 hover:bg-[var(--hover)]">
            <input type="checkbox" checked={selected.has(s.id)} onchange={() => toggle(s.id)}
              class="h-4 w-4 rounded border-[var(--border)] accent-[var(--brand)]" />
            <span class="min-w-0 flex-1 truncate text-sm text-[var(--fg)]">{s.name}</span>
            <span class="font-mono text-[10px] text-[var(--fg-subtle)]">{s.code}</span>
          </label>
        {/each}
      </div>
    {/if}

    <p class="text-[11px] text-[var(--fg-subtle)]">
      Assign a teacher for each subject from the Timetable tab once it's added here.
    </p>
    {#if addError}<p class="text-xs text-red-500">{addError}</p>{/if}
    <div class="flex items-center gap-2">
      <button onclick={submit} disabled={$addMut.isPending || selected.size === 0}
        class="rounded-xl px-4 py-1.5 text-xs font-semibold text-white transition hover:opacity-90 disabled:opacity-50"
        style="background:var(--brand)">
        {$addMut.isPending ? 'Adding…' : selected.size > 0 ? `Add ${selected.size} subject${selected.size !== 1 ? 's' : ''}` : 'Add selected'}
      </button>
      <button onclick={onClose}
        class="rounded-xl border border-[var(--border)] px-3 py-1.5 text-xs text-[var(--fg-muted)] transition hover:bg-[var(--hover)]">Cancel</button>
    </div>
  </div>
{/if}
