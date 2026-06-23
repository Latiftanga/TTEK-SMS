<script lang="ts">
  import { createMutation, createQuery, useQueryClient } from '@tanstack/svelte-query';
  import { updateStaff, listPositions, type StaffDetail } from '$lib/api/staff';
  import { toast } from '$lib/stores/toast';
  import { apiError } from '$lib/utils';

  interface Props { staff: StaffDetail; staffId: string; }
  const { staff, staffId }: Props = $props();

  const qc = useQueryClient();
  const posQuery = createQuery({ queryKey: ['positions'], queryFn: listPositions, staleTime: 10 * 60_000 });

  let editing  = $state(false);
  let selected = $state<string[]>([]);

  function open()  { selected = [...staff.position_ids]; editing = true; }
  function close() { editing = false; }
  function toggle(id: string) {
    selected = selected.includes(id) ? selected.filter(x => x !== id) : [...selected, id];
  }

  const saveMut = createMutation({
    mutationFn: () => updateStaff(staffId, { position_ids: selected }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['staff', staffId] });
      editing = false;
      toast.success('Positions updated.');
    },
    onError: (e) => toast.error(apiError(e, 'Failed to update positions.')),
  });
</script>

<div class="rounded-xl border border-[var(--border)] bg-[var(--card)] p-5">
  <div class="mb-3 flex items-center justify-between">
    <h2 class="text-xs font-semibold uppercase tracking-widest text-[var(--fg-muted)]">Authority positions</h2>
    {#if !editing}
      <button onclick={open}
        class="text-xs font-semibold transition hover:underline" style="color: var(--brand)">
        {staff.position_names.length ? 'Edit' : '+ Add'}
      </button>
    {/if}
  </div>

  {#if editing}
    <div class="flex flex-wrap gap-2">
      {#each $posQuery.data ?? [] as p (p.id)}
        <label class="flex cursor-pointer items-center gap-2 rounded-xl border px-3 py-2 text-sm transition
                      {selected.includes(p.id)
                        ? 'border-[var(--brand)] bg-[var(--brand-dim)] text-[var(--brand)]'
                        : 'border-[var(--border)] text-[var(--fg-muted)] hover:bg-[var(--hover)]'}">
          <input type="checkbox" class="accent-[var(--brand)]"
            checked={selected.includes(p.id)}
            onchange={() => toggle(p.id)} />
          {p.name}
        </label>
      {/each}
    </div>
    <div class="mt-4 flex gap-2">
      <button onclick={() => $saveMut.mutate()} disabled={$saveMut.isPending}
        class="rounded-xl px-4 py-2 text-sm font-semibold text-white transition hover:opacity-90 disabled:opacity-50"
        style="background-color: var(--brand)">
        {$saveMut.isPending ? 'Saving…' : 'Save'}
      </button>
      <button onclick={close}
        class="rounded-xl border border-[var(--border)] px-4 py-2 text-sm font-medium text-[var(--fg-muted)] transition hover:bg-[var(--hover)]">
        Cancel
      </button>
    </div>
  {:else if staff.position_names.length}
    <div class="flex flex-wrap gap-2">
      {#each staff.position_names as name}
        <span class="rounded-xl border border-[var(--brand)] bg-[var(--brand-dim)] px-3 py-1.5 text-sm font-medium text-[var(--brand)]">
          {name}
        </span>
      {/each}
    </div>
  {:else}
    <p class="text-sm text-[var(--fg-muted)]">No positions assigned yet.</p>
  {/if}
</div>
