<script lang="ts">
  import { page } from '$app/stores';
  import { goto } from '$app/navigation';
  import { createQuery, createMutation, useQueryClient } from '@tanstack/svelte-query';
  import { getHouse, updateHouse, type HouseGender } from '$lib/api/housing';
  import { userRole } from '$lib/stores/permissions';
  import { toast } from '$lib/stores/toast';
  import TabBar from '$lib/components/TabBar.svelte';
  import RoomsTab    from './RoomsTab.svelte';
  import StudentsTab from './StudentsTab.svelte';
  import RollCallTab from './RollCallTab.svelte';
  import ExeatsTab   from './ExeatsTab.svelte';

  const qc = useQueryClient();
  const houseId  = $derived($page.params.id);
  const activeTab = $derived(($page.url.searchParams.get('tab') ?? 'exeats') as 'rooms' | 'students' | 'rollcall' | 'exeats');
  const canManage = $derived($userRole === 'admin');

  const TABS = [
    { id: 'exeats',   label: 'Exeats'     },
    { id: 'rooms',    label: 'Rooms'       },
    { id: 'students', label: 'Students'    },
    { id: 'rollcall', label: 'Roll Calls'  },
  ];

  function setTab(id: string) { goto(`?tab=${id}`, { replaceState: true, noScroll: true }); }

  const houseQ = createQuery({
    queryKey: ['house', houseId],
    queryFn: () => getHouse(houseId),
    staleTime: 2 * 60_000,
  });

  const GENDER_LABEL: Record<HouseGender, string> = { MALE: 'Boys', FEMALE: 'Girls', MIXED: 'Mixed' };
  const GENDER_COLOR: Record<HouseGender, string> = {
    MALE: 'bg-blue-50 text-blue-700 dark:bg-blue-950/40 dark:text-blue-400',
    FEMALE: 'bg-pink-50 text-pink-700 dark:bg-pink-950/40 dark:text-pink-400',
    MIXED: 'bg-purple-50 text-purple-700 dark:bg-purple-950/40 dark:text-purple-400',
  };

  // ── Edit ─────────────────────────────────────────────────────────────────────
  let editing = $state(false);
  let ef = $state({ name: '', capacity: '', color: '' });

  $effect(() => {
    const h = $houseQ.data;
    if (h && !editing) ef = { name: h.name, capacity: h.capacity?.toString() ?? '', color: h.color ?? '' };
  });

  const editMut = createMutation({
    mutationFn: () => updateHouse(houseId, {
      name: ef.name.trim(),
      capacity: ef.capacity ? parseInt(ef.capacity) : undefined,
      color: ef.color || undefined,
    }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['house', houseId] });
      qc.invalidateQueries({ queryKey: ['houses'] });
      editing = false;
      toast.success('House updated.');
    },
    onError: () => toast.error('Could not update house.'),
  });
</script>

<svelte:head><title>{$houseQ.data?.name ?? 'House'}</title></svelte:head>

<!-- Back -->
<div class="mb-3">
  <button onclick={() => goto('/housing')}
    class="flex items-center gap-1 text-xs text-[var(--fg-muted)] hover:text-[var(--fg)] transition">
    <svg class="h-3.5 w-3.5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
      <path stroke-linecap="round" stroke-linejoin="round" d="M10.5 19.5L3 12m0 0l7.5-7.5M3 12h18"/>
    </svg>
    All houses
  </button>
</div>

{#if $houseQ.isPending}
  <div class="h-20 animate-pulse rounded-2xl bg-[var(--card)]"></div>
{:else if $houseQ.data}
  {@const h = $houseQ.data}

  <!-- House header -->
  <div class="mb-5 rounded-2xl border border-[var(--border)] bg-[var(--card)] p-5">
    {#if !editing}
      <div class="flex items-start justify-between">
        <div class="flex items-center gap-3">
          {#if h.color}
            <span class="h-4 w-4 shrink-0 rounded-full" style="background:{h.color}"></span>
          {/if}
          <div>
            <h1 class="text-lg font-bold text-[var(--fg)]">{h.name}</h1>
            <div class="mt-1 flex items-center gap-3 text-xs text-[var(--fg-muted)]">
              <span class="font-mono">{h.code}</span>
              <span class="rounded-full px-2 py-0.5 text-[10px] font-bold {GENDER_COLOR[h.gender]}">{GENDER_LABEL[h.gender]}</span>
              {#if h.capacity}<span>Capacity: {h.capacity}</span>{/if}
              {#if !h.is_active}<span class="text-amber-500">Inactive</span>{/if}
            </div>
          </div>
        </div>
        {#if canManage}
          <button onclick={() => editing = true}
            class="rounded-xl border border-[var(--border)] px-3 py-1.5 text-xs font-semibold
                   text-[var(--fg-muted)] hover:bg-[var(--hover)] transition">Edit</button>
        {/if}
      </div>
    {:else}
      <div class="grid gap-3 sm:grid-cols-3">
        <div>
          <label class="label">Name</label>
          <input bind:value={ef.name} class="input" />
        </div>
        <div>
          <label class="label">Capacity</label>
          <input type="number" min="1" bind:value={ef.capacity} class="input" />
        </div>
        <div>
          <label class="label">Colour (hex)</label>
          <input bind:value={ef.color} placeholder="#3b82f6" class="input" />
        </div>
      </div>
      <div class="mt-3 flex gap-2">
        <button onclick={() => $editMut.mutate()} disabled={$editMut.isPending}
          class="rounded-xl px-4 py-2 text-sm font-semibold text-white transition hover:opacity-90 disabled:opacity-50"
          style="background: var(--brand)">
          {$editMut.isPending ? 'Saving…' : 'Save'}
        </button>
        <button onclick={() => editing = false}
          class="rounded-xl border border-[var(--border)] px-4 py-2 text-sm text-[var(--fg-muted)] hover:bg-[var(--hover)] transition">
          Cancel
        </button>
      </div>
    {/if}
  </div>

  <div class="mb-5">
    <TabBar tabs={TABS} active={activeTab} onchange={setTab} />
  </div>

  {#if activeTab === 'exeats'}
    <ExeatsTab {houseId} {canManage} />
  {:else if activeTab === 'rooms'}
    <RoomsTab {houseId} rooms={h.rooms} {canManage} />
  {:else if activeTab === 'students'}
    <StudentsTab {houseId} {canManage} />
  {:else if activeTab === 'rollcall'}
    <RollCallTab {houseId} {canManage} />
  {/if}
{/if}

<style>
  @reference "tailwindcss";
  .label { @apply block text-xs font-medium text-[var(--fg-muted)] mb-1; }
  .input  { @apply w-full rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm
                   text-[var(--fg)] placeholder:text-[var(--fg-subtle)] focus:border-[var(--brand)]
                   focus:outline-none transition; }
</style>
