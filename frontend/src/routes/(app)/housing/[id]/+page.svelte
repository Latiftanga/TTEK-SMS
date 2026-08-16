<script lang="ts">
  import { page } from '$app/stores';
  import { goto } from '$app/navigation';
  import { createQuery, createMutation, useQueryClient } from '@tanstack/svelte-query';
  import { getHouse, updateHouse, type HouseGender } from '$lib/api/housing';
  import { userRole, isHousemaster } from '$lib/stores/permissions';
  import { toast } from '$lib/stores/toast';
  import { setPageTitle } from '$lib/stores/title';
  import TabBar from '$lib/components/TabBar.svelte';
  import RoomsTab    from './RoomsTab.svelte';
  import StudentsTab from './StudentsTab.svelte';
  import RollCallTab from './RollCallTab.svelte';
  import ExeatsTab   from './ExeatsTab.svelte';

  const qc = useQueryClient();
  const houseId  = $derived($page.params.id!);
  const activeTab = $derived(($page.url.searchParams.get('tab') ?? 'exeats') as 'rooms' | 'students' | 'rollcall' | 'exeats');
  const canAdmin   = $derived($userRole === 'admin');
  const canOperate = $derived($userRole === 'admin' || $isHousemaster);

  const TABS = [
    { id: 'exeats',   label: 'Exeats',     icon: `<path stroke-linecap="round" stroke-linejoin="round" d="M15.75 9V5.25A2.25 2.25 0 0013.5 3h-6a2.25 2.25 0 00-2.25 2.25v13.5A2.25 2.25 0 007.5 21h6a2.25 2.25 0 002.25-2.25V15M12 9l-3 3m0 0l3 3m-3-3h12.75"/>` },
    { id: 'rooms',    label: 'Rooms',       icon: `<path stroke-linecap="round" stroke-linejoin="round" d="M15.75 5.25a3 3 0 013 3m3 0a6 6 0 01-7.029 5.912c-.563-.097-1.159.026-1.563.43L10.5 17.25H8.25v2.25H6v2.25H2.25v-2.818c0-.597.237-1.169.659-1.591l6.499-6.499c.404-.404.527-1 .43-1.563A6 6 0 1121.75 8.25z"/>` },
    { id: 'students', label: 'Students',    icon: `<path stroke-linecap="round" stroke-linejoin="round" d="M15 19.128a9.38 9.38 0 002.625.372 9.337 9.337 0 004.121-.952 4.125 4.125 0 00-7.533-2.493M15 19.128v-.003c0-1.113-.285-2.16-.786-3.07M15 19.128v.106A12.318 12.318 0 018.624 21c-2.331 0-4.512-.645-6.374-1.766l-.001-.109a6.375 6.375 0 0111.964-3.07M12 6.375a3.375 3.375 0 11-6.75 0 3.375 3.375 0 016.75 0zm8.25 2.25a2.625 2.625 0 11-5.25 0 2.625 2.625 0 015.25 0z"/>` },
    { id: 'rollcall', label: 'Roll Calls',  icon: `<path stroke-linecap="round" stroke-linejoin="round" d="M11.35 3.836c-.065.21-.1.433-.1.664 0 .414.336.75.75.75h4.5a.75.75 0 00.75-.75 2.25 2.25 0 00-.1-.664m-5.8 0A2.251 2.251 0 0113.5 2.25H15c1.012 0 1.867.668 2.15 1.586m-5.8 0c-.376.023-.75.05-1.124.08C9.095 4.01 8.25 4.973 8.25 6.108V8.25m8.9-4.414c.376.023.75.05 1.124.08 1.131.094 1.976 1.057 1.976 2.192V16.5A2.25 2.25 0 0118 18.75h-2.25m-7.5-10.5H4.875c-.621 0-1.125.504-1.125 1.125v11.25c0 .621.504 1.125 1.125 1.125h9.75c.621 0 1.125-.504 1.125-1.125V18.75m-7.5-10.5h6.375c.621 0 1.125.504 1.125 1.125v9.375m-8.25-3l1.5 1.5 3-3.75"/>` },
  ];

  function setTab(id: string) { goto(`?tab=${id}`, { replaceState: true, noScroll: true }); }

  const houseQ = createQuery({
    queryKey: ['house', houseId],
    queryFn: () => getHouse(houseId),
    staleTime: 2 * 60_000,
  });

  $effect(() => setPageTitle($houseQ.data?.name ?? 'House'));

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
      qc.invalidateQueries({ queryKey: ['houses-mine'] });
      editing = false;
      toast.success('House updated.');
    },
    onError: () => toast.error('Could not update house.'),
  });
</script>


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
        {#if canAdmin}
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
    <ExeatsTab {houseId} canManage={canOperate} />
  {:else if activeTab === 'rooms'}
    <RoomsTab {houseId} rooms={h.rooms} canManage={canAdmin} />
  {:else if activeTab === 'students'}
    <StudentsTab {houseId} canManage={canOperate} />
  {:else if activeTab === 'rollcall'}
    <RollCallTab {houseId} canManage={canOperate} />
  {/if}
{/if}

<style>
  @reference "tailwindcss";
  .label { @apply block text-xs font-medium text-[var(--fg-muted)] mb-1; }
  .input  { @apply w-full rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm
                   text-[var(--fg)] placeholder:text-[var(--fg-subtle)] focus:border-[var(--brand)]
                   focus:outline-none transition; }
</style>
