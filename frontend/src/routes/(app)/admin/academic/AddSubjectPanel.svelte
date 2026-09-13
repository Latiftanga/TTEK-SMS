<script lang="ts">
  import { createMutation, useQueryClient } from '@tanstack/svelte-query';
  import { createSubject } from '$lib/api/academic';
  import { apiError } from '$lib/utils';

  interface Props {
    onDone: () => void;
    onClose: () => void;
  }
  const { onDone, onClose }: Props = $props();

  const qc = useQueryClient();

  let form  = $state({ code: '', name: '' });
  let error = $state('');

  const createMut = createMutation({
    mutationFn: createSubject,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['subjects'] });
      form = { code: '', name: '' };
      onDone();
    },
    onError: (e: unknown) => { error = apiError(e, 'Failed to create subject.'); },
  });

  function submit() {
    error = '';
    if (!form.code.trim() || !form.name.trim()) { error = 'Code and name are required.'; return; }
    $createMut.mutate({ code: form.code.toUpperCase(), name: form.name });
  }
</script>

<div class="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
  <div class="mb-4 flex items-center justify-between">
    <p class="text-sm font-semibold text-[var(--fg)]">Add subject</p>
    <button onclick={onClose} class="text-xs text-[var(--fg-muted)] hover:text-[var(--fg)]">Cancel</button>
  </div>

  <div class="space-y-3">
    <div class="grid gap-3 sm:grid-cols-2">
      <div>
        <label class="mb-1 block text-xs font-medium text-[var(--fg-muted)]">Code</label>
        <input bind:value={form.code} placeholder="e.g. MATH" class="w-full rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--fg)] placeholder:text-[var(--fg-muted)] focus:border-[var(--brand)] focus:outline-none" />
      </div>
      <div>
        <label class="mb-1 block text-xs font-medium text-[var(--fg-muted)]">Name</label>
        <input bind:value={form.name} placeholder="e.g. Mathematics" class="w-full rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--fg)] placeholder:text-[var(--fg-muted)] focus:border-[var(--brand)] focus:outline-none" />
      </div>
    </div>
    {#if error}<p class="text-xs text-red-500">{error}</p>{/if}
    <button onclick={submit} disabled={$createMut.isPending}
      class="rounded-xl px-4 py-2 text-sm font-semibold text-white transition hover:opacity-90 disabled:opacity-50" style="background-color: var(--brand)">
      {$createMut.isPending ? 'Creating…' : 'Create subject'}
    </button>
  </div>
</div>
