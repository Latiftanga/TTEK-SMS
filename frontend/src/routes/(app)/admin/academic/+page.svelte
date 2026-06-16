<script lang="ts">
  import { page } from '$app/stores';
  import { goto } from '$app/navigation';
  import { createQuery } from '@tanstack/svelte-query';
  import { listYears, type AcademicYear } from '$lib/api/academic';
  import { school } from '$lib/stores/school';
  import { fade } from 'svelte/transition';
  import YearsTab      from './YearsTab.svelte';
  import ClassesTab    from './ClassesTab.svelte';
  import SubjectsTab   from './SubjectsTab.svelte';
  import ProgrammesTab from './ProgrammesTab.svelte';

  type Tab = 'years' | 'classes' | 'subjects' | 'programmes';
  interface TabDef { id: Tab; label: string; icon: string }

  // SVG stroke paths (Heroicons outline)
  const ICONS: Record<string, string> = {
    calendar:   'M6.75 3v2.25M17.25 3v2.25M3 18.75V7.5a2.25 2.25 0 012.25-2.25h13.5A2.25 2.25 0 0121 7.5v11.25m-18 0A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75m-18 0v-7.5A2.25 2.25 0 015.25 9h13.5A2.25 2.25 0 0121 11.25v7.5',
    graduation: 'M4.26 10.147a60.436 60.436 0 00-.491 6.347A48.627 48.627 0 0112 20.904a48.627 48.627 0 018.232-4.41 60.46 60.46 0 00-.491-6.347m-15.482 0a50.57 50.57 0 00-2.658-.813A59.905 59.905 0 0112 3.493a59.902 59.902 0 0110.399 5.84c-.896.248-1.783.52-2.658.814m-15.482 0A50.697 50.697 0 0112 13.489a50.702 50.702 0 017.74-3.342M6.75 15a.75.75 0 100-1.5.75.75 0 000 1.5zm0 0v-3.675A55.378 55.378 0 0112 8.443m-7.007 11.55A5.981 5.981 0 006.75 15.75v-1.5',
    building:   'M2.25 21h19.5m-18-18v18m10.5-18v18m6-13.5V21M6.75 6.75h.75m-.75 3h.75m-.75 3h.75m3-6h.75m-.75 3h.75m-.75 3h.75M6.75 21v-3.375c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125V21M3 3h12m-.75 4.5H21m-3.75 3.75h.008v.008h-.008v-.008zm0 3h.008v.008h-.008v-.008zm0 3h.008v.008h-.008v-.008z',
    book:       'M12 6.042A8.967 8.967 0 006 3.75c-1.052 0-2.062.18-3 .512v14.25A8.987 8.987 0 016 18c2.305 0 4.408.867 6 2.292m0-14.25a8.966 8.966 0 016-2.292c1.052 0 2.062.18 3 .512v14.25A8.987 8.987 0 0018 18a8.967 8.967 0 00-6 2.292m0-14.25v14.25',
  };

  const schoolType = $derived($school?.schoolType ?? 'BASIC');

  const tabs = $derived<TabDef[]>(
    schoolType === 'SHS'
      ? [
          { id: 'years',      label: 'Years & Terms', icon: ICONS.calendar   },
          { id: 'programmes', label: 'Programmes',    icon: ICONS.graduation },
          { id: 'classes',    label: 'Classes',       icon: ICONS.building   },
          { id: 'subjects',   label: 'Subjects',      icon: ICONS.book       },
        ]
      : [
          { id: 'years',    label: 'Years & Terms', icon: ICONS.calendar },
          { id: 'classes',  label: 'Classes',       icon: ICONS.building },
          { id: 'subjects', label: 'Subjects',      icon: ICONS.book     },
        ]
  );

  // Plain-value derived — no () needed in the template
  const rawTab    = $derived($page.url.searchParams.get('tab') as Tab | null);
  const activeTab = $derived(rawTab && tabs.some(t => t.id === rawTab) ? rawTab : 'years' as Tab);

  function setTab(id: Tab) {
    goto(`?tab=${id}`, { replaceState: true, noScroll: true });
  }

  // Year selector — shared by the Classes tab
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

  // Shared condition used in two places (tab bar + below-border mobile row)
  const showYearPicker = $derived(activeTab === 'classes' && ($yearsQuery.data?.length ?? 0) > 0);
</script>

<div>
  <!-- Page header -->
  <div class="mb-6">
    <h1 class="text-2xl font-bold tracking-tight text-[var(--fg)]">Academic</h1>
    <p class="mt-0.5 text-sm text-[var(--fg-muted)]">
      Years, terms, classes{schoolType === 'SHS' ? ', programmes' : ''} and subjects
    </p>
  </div>

  <!-- Tab bar -->
  <div class="mb-7">
    <div class="flex items-end justify-between border-b border-[var(--border)]">

      <!-- Tabs: scroll horizontally on very small screens as a safety net.
           Labels are hidden on mobile so 4 icons comfortably fit on 375px. -->
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
            <!-- Label hidden on mobile — icon alone is enough; title attr provides tooltip -->
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

      <!-- Year filter — desktop only (sm+) in the tab bar row -->
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

    <!-- Year filter — mobile only (< sm), sits below the tab border -->
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
      {#if activeTab === 'years'}
        <YearsTab />
      {:else if activeTab === 'classes'}
        <ClassesTab {selectedYearId} {schoolType} />
      {:else if activeTab === 'subjects'}
        <SubjectsTab />
      {:else if activeTab === 'programmes'}
        <ProgrammesTab />
      {/if}
    </div>
  {/key}
</div>
