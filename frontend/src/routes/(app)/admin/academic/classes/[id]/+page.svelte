<script lang="ts">
  import { page } from '$app/stores';
  import { goto } from '$app/navigation';
  import { getContext } from 'svelte';
  import { createQuery } from '@tanstack/svelte-query';
  import { listClasses, type AcademicTerm, type SchoolClass } from '$lib/api/academic';
  import StudentsSection from './StudentsSection.svelte';
  import SubjectsTab     from './SubjectsTab.svelte';
  import TeachersTab     from './TeachersTab.svelte';

  type Tab = 'students' | 'subjects' | 'teachers';

  const classId = $derived($page.params.id);
  const termCtx = getContext<{ termId: string; terms: AcademicTerm[]; subjectCount: number }>('classTerm');
  const selectedTermId = $derived(termCtx.termId);
  const terms          = $derived(termCtx.terms);
  const subjectCount   = $derived(termCtx.subjectCount);

  const activeTab = $derived(($page.url.searchParams.get('tab') as Tab) ?? 'students');
  function setTab(t: Tab) { goto(`?tab=${t}`, { replaceState: true, noScroll: true }); }

  const classesQuery = createQuery({ queryKey: ['classes'], queryFn: listClasses, staleTime: 5 * 60_000 });
  const classes = $derived<SchoolClass[]>($classesQuery.data ?? []);

  const TABS: { key: Tab; label: string; count?: number }[] = [
    { key: 'students', label: 'Students' },
    { key: 'subjects', label: 'Subjects' },
    { key: 'teachers', label: 'Teachers' },
  ];
</script>

<!-- Tab nav -->
<div class="mb-6 border-b border-[var(--border)]">
  <nav class="-mb-px flex" aria-label="Class sections">
    {#each TABS as tab}
      {@const active = activeTab === tab.key}
      <button
        onclick={() => setTab(tab.key)}
        class="group relative flex items-center gap-1.5 px-4 pb-3 pt-1 text-sm font-medium transition-colors
               {active ? 'text-[var(--brand)]' : 'text-[var(--fg-muted)] hover:text-[var(--fg)]'}"
      >
        {tab.label}
        {#if tab.key === 'subjects' && subjectCount > 0}
          <span class="rounded-full px-1.5 py-0.5 text-[11px] font-semibold leading-none
                       {active ? 'bg-[color-mix(in_srgb,var(--brand)_12%,transparent)] text-[var(--brand)]'
                               : 'bg-[var(--hover)] text-[var(--fg-muted)]'}">
            {subjectCount}
          </span>
        {/if}
        <span class="pointer-events-none absolute bottom-0 left-0 right-0 h-0.5 rounded-t-sm transition-colors
                     {active ? 'bg-[var(--brand)]' : 'bg-transparent group-hover:bg-[var(--border)]'}">
        </span>
      </button>
    {/each}
  </nav>
</div>

{#key selectedTermId}
  {#if activeTab === 'students'}
    <StudentsSection {classId} {terms} {selectedTermId} {classes} />
  {:else if activeTab === 'subjects'}
    <SubjectsTab {classId} {selectedTermId} />
  {:else if activeTab === 'teachers'}
    <TeachersTab {classId} {selectedTermId} />
  {/if}
{/key}
