<script lang="ts">
  import { createMutation, useQueryClient } from '@tanstack/svelte-query';
  import { updateClass, type SchoolClass } from '$lib/api/academic';
  import { portal } from '$lib/actions/portal';
  import { toast } from '$lib/stores/toast';

  interface Props { cls: SchoolClass; onClose: () => void; }
  const { cls, onClose }: Props = $props();

  const qc = useQueryClient();

  let stream   = $state(cls.stream   ?? '');
  let capacity = $state(cls.capacity?.toString() ?? '');
  let error    = $state('');

  const saveMut = createMutation({
    mutationFn: () => updateClass(cls.id, {
      stream:   stream.trim()  || null,
      capacity: capacity       ? Number(capacity) : null,
    }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['classes'] });
      toast.success('Class updated.');
      onClose();
    },
    onError: (e: unknown) => {
      error = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? 'Failed to update class.';
    },
  });
</script>

<div use:portal class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
  <div class="w-full max-w-sm rounded-2xl border border-[var(--border)] bg-[var(--card)] shadow-2xl">

    <div class="flex items-center justify-between border-b border-[var(--border)] px-6 py-4">
      <div>
        <h2 class="text-base font-semibold text-[var(--fg)]">Edit Class</h2>
        <p class="text-xs text-[var(--fg-muted)]">{cls.display_name}</p>
      </div>
      <button onclick={onClose} aria-label="Close" class="flex h-11 w-11 items-center justify-center rounded-lg text-[var(--fg-muted)] transition hover:bg-[var(--hover)] hover:text-[var(--fg)]">
        <svg class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12"/></svg>
      </button>
    </div>

    <div class="space-y-4 p-6">
      <label class="block">
        <span class="mb-1 block text-xs font-medium text-[var(--fg-muted)]">Stream</span>
        <input bind:value={stream} placeholder="e.g. A, B, Gold…"
          class="w-full rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--fg)] transition focus:border-[var(--brand)] focus:outline-none" />
      </label>
      <label class="block">
        <span class="mb-1 block text-xs font-medium text-[var(--fg-muted)]">Capacity</span>
        <input bind:value={capacity} type="number" inputmode="numeric" min="1" max="999" placeholder="e.g. 40"
          class="w-full rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--fg)] transition focus:border-[var(--brand)] focus:outline-none" />
      </label>
      {#if error}<p class="text-xs text-red-500">{error}</p>{/if}
    </div>

    <div class="flex justify-end gap-3 border-t border-[var(--border)] px-6 py-4">
      <button onclick={onClose} class="btn-ghost">Cancel</button>
      <button onclick={() => $saveMut.mutate()} disabled={$saveMut.isPending} class="btn-primary">
        {$saveMut.isPending ? 'Saving…' : 'Save'}
      </button>
    </div>

  </div>
</div>
