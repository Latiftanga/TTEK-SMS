<script lang="ts">
  import { page } from '$app/stores';
  import { goto } from '$app/navigation';
  import { createQuery } from '@tanstack/svelte-query';
  import { fade } from 'svelte/transition';
  import { listYears, type AcademicYear } from '$lib/api/academic';
  import { school } from '$lib/stores/school';
  import ClassesTab  from '../academic/ClassesTab.svelte';
  import SubjectsTab from '../academic/SubjectsTab.svelte';

  const schoolType = $derived($school?.schoolType ?? 'BASIC');

  type Tab = 'classes' | 'subjects';
  interface TabDef { id: Tab; label: string; icon: string }

  const ICONS = {
    building: 'M2.25 21h19.5m-18-18v18m10.5-18v18m6-13.5V21M6.75 6.75h.75m-.75 3h.75m-.75 3h.75m3-6h.75m-.75 3h.75m-.75 3h.75M6.75 21v-3.375c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125V21M3 3h12m-.75 4.5H21m-3.75 3.75h.008v.008h-.008v-.008zm0 3h.008v.008h-.008v-.008zm0 3h.008v.008h-.008v-.008z',
    book:     'M12 6.042A8.967 8.967 0 006 3.75c-1.052 0-2.062.18-3 .512v14.25A8.987 8.987 0 016 18c2.305 0 4.408.867 6 2.292m0-14.25a8.966 8.966 0 016-2.292c1.052 0 2.062.18 3 .512v14.25A8.987 8.987 0 0018 18a8.967 8.967 0 00-6 2.292m0-14.25v14.25',
  };

  const tabs: TabDef[] = [
    { id: 'classes',  label: 'Classes',  icon: ICONS.building },
    { id: 'subjects', label: 'Subjects', icon: ICONS.book     },
  ];

  const rawTab    = $derived($page.url.searchParams.get('tab') as Tab | null);
  const activeTab = $derived(rawTab === 'subjects' ? 'subjects' : 'classes' as Tab);

  function setTab(id: Tab) {
    goto(`?tab=${id}`, { replaceState: true, noScroll: true });
  }

  // Year selector — used only by the Classes tab
  const yearsQuery = createQuery({
    queryKey: ['academic-years'],
    queryFn: listYears,
    staleTime: 5 * 60_000,
  });

  let selectedYearId = $state<string | null>(null);

  const currentYear = $derived(
    ($yearsQuery.data ?? []).find((y: AcademicYear) => y.is_current) ??
    ($yearsQuery.data ?? [])[0] ??
    null
  );

  $effect(() => {
    if (!selectedYearId && currentYear) selectedYearId = currentYear.id;
  });

  const showYearPicker = $derived(activeTab === 'classes' && ($yearsQuery.data?.length ?? 0) > 0);
</script>

<div>
  <div class="mb-6">
    <h1 class="text-2xl font-bold tracking-tight text-[var(--fg)]">Classes & Subjects</h1>
    <p class="mt-0.5 text-sm text-[var(--fg-muted)]">
      Define your school's classes and the subjects taught in them
    </p>
  </div>

  <!-- Tab bar -->
  <div class="mb-7">
    <div class="flex items-end justify-between border-b border-[var(--border)]">

      <div class="flex overflow-x-auto [scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
           role="tablist">
        {#each tabs as t}
          <button
            role="tab"
            aria-selected={activeTab === t.id}
            onclick={() => setTab(t.id)}
            title={t.label}
            class="group relative flex shrink-0 items-center gap-1.5 px-3 pb-3 pt-0.5
                   text-sm font-medium transition-colors duration-150 sm:px-4
                   {activeTab === t.id
                     ? 'text-[var(--brand)]'
                     : 'text-[var(--fg-muted)] hover:text-[var(--fg)]'}"
          >
            <svg class="h-4 w-4 shrink-0" fill="none" stroke="currentColor"
                 stroke-width="1.75" viewBox="0 0 24 24" aria-hidden="true">
              <path stroke-linecap="round" stroke-linejoin="round" d={t.icon} />
            </svg>
            <span class="hidden sm:inline">{t.label}</span>
            <span class="pointer-events-none absolute bottom-0 left-0 right-0 h-0.5 rounded-t-sm
                         transition-colors duration-150
                         {activeTab === t.id
                           ? 'bg-[var(--brand)]'
                           : 'bg-transparent group-hover:bg-[var(--border)]'}">
            </span>
          </button>
        {/each}
      </div>

      <!-- Year filter — desktop only (sm+) -->
      {#if showYearPicker}
        <div class="mb-2 hidden shrink-0 items-center gap-2 sm:flex">
          <span class="text-xs font-medium text-[var(--fg-muted)]">Year</span>
          <select bind:value={selectedYearId}
            class="rounded-lg border border-[var(--border)] bg-[var(--card)] px-2.5 py-1 text-xs
                   text-[var(--fg)] shadow-sm focus:border-[var(--brand)] focus:outline-none
                   focus:ring-2 focus:ring-[var(--brand)]/20">
            {#each ($yearsQuery.data ?? []) as y (y.id)}
              <option value={y.id}>{y.name}{y.is_current ? ' · current' : ''}</option>
            {/each}
          </select>
        </div>
      {/if}

    </div>

    <!-- Year filter — mobile only, below the tab border -->
    {#if showYearPicker}
      <div class="flex items-center gap-2 pt-3 sm:hidden">
        <span class="text-xs font-medium text-[var(--fg-muted)]">Year</span>
        <select bind:value={selectedYearId}
          class="rounded-lg border border-[var(--border)] bg-[var(--card)] px-2.5 py-1 text-xs
                 text-[var(--fg)] shadow-sm focus:border-[var(--brand)] focus:outline-none
                 focus:ring-2 focus:ring-[var(--brand)]/20">
          {#each ($yearsQuery.data ?? []) as y (y.id)}
            <option value={y.id}>{y.name}{y.is_current ? ' · current' : ''}</option>
          {/each}
        </select>
      </div>
    {/if}
  </div>

  <!-- Tab panels -->
  {#key activeTab}
    <div in:fade={{ duration: 120 }}>
      {#if activeTab === 'classes'}
        <ClassesTab {selectedYearId} {schoolType} />
      {:else}
        <SubjectsTab />
      {/if}
    </div>
  {/key}
</div>
