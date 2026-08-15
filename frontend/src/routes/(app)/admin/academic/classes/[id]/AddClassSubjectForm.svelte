<script lang="ts">
  import { createMutation, useQueryClient } from '@tanstack/svelte-query';
  import { assignSubjects, type Subject } from '$lib/api/academic';
  import { apiError } from '$lib/utils';
  import { toast } from '$lib/stores/toast';

  interface Props {
    classId: string;
    unassignedSubjs: Subject[];
    onClose: () => void;
  }
  const { classId, unassignedSubjs, onClose }: Props = $props();

  const qc = useQueryClient();

  let newSubjectId = $state('');
  let addError     = $state('');

  const addMut = createMutation({
    mutationFn: () => assignSubjects(classId, [newSubjectId]),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['class-subjects', classId] });
      toast.success('Subject assigned.');
      onClose();
    },
    onError: (e) => { addError = apiError(e, 'Failed to assign subject.'); },
  });

  const sel = 'w-full rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--fg)] focus:border-[var(--brand)] focus:outline-none transition';
</script>

{#if unassignedSubjs.length === 0}
  <p class="rounded-xl border border-[var(--border)] bg-[var(--card)] px-4 py-3 text-sm text-[var(--fg-muted)]">
    All available subjects are already assigned to this class.
  </p>
{:else}
  <div class="rounded-2xl border border-[var(--border)] bg-[var(--card)] p-4 space-y-3">
    <p class="text-xs font-semibold text-[var(--fg)]">Add subject</p>
    <div>
      <label class="mb-1 block text-xs font-medium text-[var(--fg-muted)]">Subject *</label>
      <select bind:value={newSubjectId} class={sel}>
        <option value="">Select subject…</option>
        {#each unassignedSubjs as s (s.id)}<option value={s.id}>{s.name}</option>{/each}
      </select>
    </div>
    <p class="text-[11px] text-[var(--fg-subtle)]">
      Assign a teacher via "Manage teacher & students" on the subject row once it's added here.
    </p>
    {#if addError}<p class="text-xs text-red-500">{addError}</p>{/if}
    <div class="flex gap-2">
      <button onclick={() => $addMut.mutate()} disabled={$addMut.isPending || !newSubjectId}
        class="rounded-xl px-4 py-1.5 text-xs font-semibold text-white transition hover:opacity-90 disabled:opacity-50"
        style="background:var(--brand)">{$addMut.isPending ? 'Saving…' : 'Add'}</button>
      <button onclick={onClose}
        class="rounded-xl border border-[var(--border)] px-3 py-1.5 text-xs text-[var(--fg-muted)] transition hover:bg-[var(--hover)]">Cancel</button>
    </div>
  </div>
{/if}
