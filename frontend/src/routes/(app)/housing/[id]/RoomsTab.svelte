<script lang="ts">
  import { createMutation, useQueryClient } from '@tanstack/svelte-query';
  import { addRoom, updateRoom, type Room } from '$lib/api/housing';
  import { toast } from '$lib/stores/toast';

  interface Props { houseId: string; rooms: Room[]; canManage: boolean; }
  const { houseId, rooms, canManage }: Props = $props();

  const qc = useQueryClient();

  const ROOM_TYPES = ['DORMITORY', 'SICK_BAY', 'PREFECT', 'STAFF'];

  // ── Add room ──────────────────────────────────────────────────────────────────
  let showAdd = $state(false);
  let af = $state({ room_number: '', capacity: '', room_type: 'DORMITORY' });
  let addErr = $state('');

  const addMut = createMutation({
    mutationFn: () => addRoom(houseId, {
      room_number: af.room_number.trim(),
      capacity: af.capacity ? parseInt(af.capacity) : undefined,
      room_type: af.room_type,
    }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['house', houseId] });
      showAdd = false;
      af = { room_number: '', capacity: '', room_type: 'DORMITORY' };
      toast.success('Room added.');
    },
    onError: (e: unknown) => {
      addErr = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? 'Could not add room.';
    },
  });

  // ── Edit room ─────────────────────────────────────────────────────────────────
  let editId = $state<string | null>(null);
  let ef = $state({ room_number: '', capacity: '', room_type: 'DORMITORY' });

  function startEdit(r: Room) {
    editId = r.id;
    ef = { room_number: r.room_number, capacity: r.capacity?.toString() ?? '', room_type: r.room_type };
  }

  const editMut = createMutation({
    mutationFn: () => updateRoom(houseId, editId!, {
      room_number: ef.room_number.trim(),
      capacity: ef.capacity ? parseInt(ef.capacity) : undefined,
      room_type: ef.room_type,
    }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['house', houseId] });
      editId = null;
      toast.success('Room updated.');
    },
    onError: () => toast.error('Could not update room.'),
  });
</script>

<div>
  {#if canManage}
    <div class="mb-3 flex justify-end">
      <button onclick={() => { showAdd = !showAdd; addErr = ''; }}
        class="flex min-h-[44px] items-center gap-1.5 rounded-xl px-3 py-1.5 text-xs font-semibold text-white transition hover:opacity-90"
        style="background: var(--brand)">
        <svg class="h-3.5 w-3.5" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" d="M12 4v16m8-8H4"/>
        </svg>
        Add room
      </button>
    </div>

    {#if showAdd}
      <div class="mb-4 rounded-2xl border border-[var(--border)] bg-[var(--card)] p-4">
        <div class="grid gap-3 sm:grid-cols-3">
          <div>
            <label class="label">Room number <span class="text-red-500">*</span></label>
            <input bind:value={af.room_number} placeholder="e.g. A1" class="input" />
          </div>
          <div>
            <label class="label">Capacity</label>
            <input type="number" min="1" inputmode="numeric" bind:value={af.capacity} placeholder="e.g. 8" class="input" />
          </div>
          <div>
            <label class="label">Type</label>
            <select bind:value={af.room_type} class="input">
              {#each ROOM_TYPES as t}<option value={t}>{t.replace('_', ' ')}</option>{/each}
            </select>
          </div>
        </div>
        {#if addErr}<p class="mt-2 text-xs text-red-500">{addErr}</p>{/if}
        <div class="mt-3 flex gap-2">
          <button onclick={() => { addErr = ''; if (!af.room_number.trim()) { addErr = 'Room number required.'; return; } $addMut.mutate(); }}
            disabled={$addMut.isPending}
            class="min-h-[44px] rounded-xl px-3 py-1.5 text-sm font-semibold text-white transition hover:opacity-90 disabled:opacity-50"
            style="background: var(--brand)">
            {$addMut.isPending ? 'Adding…' : 'Add room'}
          </button>
          <button onclick={() => showAdd = false}
            class="min-h-[44px] rounded-xl border border-[var(--border)] px-3 py-1.5 text-sm text-[var(--fg-muted)] hover:bg-[var(--hover)] transition">
            Cancel
          </button>
        </div>
      </div>
    {/if}
  {/if}

  {#if rooms.length === 0}
    <div class="rounded-2xl border border-dashed border-[var(--border)] p-10 text-center">
      <p class="text-sm text-[var(--fg-muted)]">No rooms yet.{canManage ? ' Add one above.' : ''}</p>
    </div>
  {:else}
    <div class="overflow-hidden rounded-2xl border border-[var(--border)] bg-[var(--card)]">
      <table class="w-full text-sm">
        <thead><tr class="border-b border-[var(--border)] text-left text-[10px] font-semibold uppercase tracking-widest text-[var(--fg-subtle)]">
          <th class="px-4 py-3">Room</th>
          <th class="px-4 py-3">Type</th>
          <th class="px-4 py-3 text-right">Capacity</th>
          {#if canManage}<th class="px-4 py-3"></th>{/if}
        </tr></thead>
        <tbody>
          {#each rooms as r (r.id)}
            {#if editId === r.id}
              <tr class="border-b border-[var(--border)] bg-[var(--hover)]">
                <td class="px-3 py-2">
                  <input bind:value={ef.room_number} class="input w-28" />
                </td>
                <td class="px-3 py-2">
                  <select bind:value={ef.room_type} class="input">
                    {#each ROOM_TYPES as t}<option value={t}>{t.replace('_',' ')}</option>{/each}
                  </select>
                </td>
                <td class="px-3 py-2 text-right">
                  <input type="number" min="1" inputmode="numeric" bind:value={ef.capacity} class="input w-20 text-right" />
                </td>
                <td class="px-3 py-2">
                  <div class="flex gap-1">
                    <button onclick={() => $editMut.mutate()} disabled={$editMut.isPending}
                      class="min-h-[44px] rounded-lg px-2 py-1 text-xs font-semibold text-white disabled:opacity-50"
                      style="background:var(--brand)">Save</button>
                    <button onclick={() => editId = null}
                      class="min-h-[44px] rounded-lg border border-[var(--border)] px-2 py-1 text-xs text-[var(--fg-muted)] hover:bg-[var(--hover)]">
                      Cancel
                    </button>
                  </div>
                </td>
              </tr>
            {:else}
              <tr class="border-b border-[var(--border)] last:border-0 transition hover:bg-[var(--hover)]">
                <td class="px-4 py-3 font-medium text-[var(--fg)]">{r.room_number}</td>
                <td class="px-4 py-3 text-[var(--fg-muted)]">{r.room_type.replace('_', ' ')}</td>
                <td class="px-4 py-3 text-right text-[var(--fg-muted)]">{r.capacity ?? '—'}</td>
                {#if canManage}
                  <td class="px-4 py-3 text-right">
                    <button onclick={() => startEdit(r)}
                      class="inline-flex min-h-[44px] items-center px-2 text-xs text-[var(--fg-subtle)] hover:text-[var(--fg)] transition">Edit</button>
                  </td>
                {/if}
              </tr>
            {/if}
          {/each}
        </tbody>
      </table>
    </div>
  {/if}
</div>

<style>
  @reference "tailwindcss";
  .label { @apply block text-xs font-medium text-[var(--fg-muted)] mb-1; }
  .input  { @apply w-full rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm
                   text-[var(--fg)] placeholder:text-[var(--fg-subtle)] focus:border-[var(--brand)]
                   focus:outline-none transition; }
</style>
