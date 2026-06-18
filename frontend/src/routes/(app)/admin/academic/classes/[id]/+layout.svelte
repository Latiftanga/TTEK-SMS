<script lang="ts">
  import { page } from '$app/stores';
  import { get } from 'svelte/store';
  import { setContext } from 'svelte';
  import { createQuery } from '@tanstack/svelte-query';
  import { getClass, listAllTerms, listClassSubjects, type AcademicTerm } from '$lib/api/academic';
  import Badge from '$lib/components/Badge.svelte';

  const { children } = $props();

  const id = get(page).params.id;

  const classQuery = createQuery({ queryKey: ['class', id], queryFn: () => getClass(id), staleTime: 5 * 60_000 });
  const termsQuery = createQuery({ queryKey: ['all-terms'], queryFn: listAllTerms, staleTime: 5 * 60_000 });
  const subjQuery  = createQuery({ queryKey: ['class-subjects', id], queryFn: () => listClassSubjects(id), staleTime: 2 * 60_000 });

  const cls          = $derived($classQuery.data);
  const terms        = $derived<AcademicTerm[]>($termsQuery.data ?? []);
  const subjectCount = $derived(($subjQuery.data ?? []).length);

  let selectedTermId = $state('');
  $effect(() => {
    if (!selectedTermId && terms.length)
      selectedTermId = terms.find(t => t.is_current)?.id ?? terms[0]?.id ?? '';
  });

  setContext('classTerm', {
    get termId()       { return selectedTermId; },
    get terms()        { return terms; },
    get subjectCount() { return subjectCount; },
  });
</script>

<a href="/admin/academic/classes"
   class="mb-4 inline-flex items-center gap-1.5 text-xs text-[var(--fg-muted)] transition-colors hover:text-[var(--fg)]">
  <svg class="h-3.5 w-3.5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
    <path stroke-linecap="round" stroke-linejoin="round" d="M15 19l-7-7 7-7"/>
  </svg>
  All Classes
</a>

<!-- Class card -->
<div class="mb-5 overflow-hidden rounded-xl border border-[var(--border)] bg-[var(--card)]">

  <!-- Top: monogram + name + status -->
  <div class="flex items-start gap-4 px-5 py-4">
    <div class="flex h-12 w-12 shrink-0 select-none items-center justify-center rounded-lg
                bg-[color-mix(in_srgb,var(--brand)_10%,transparent)] text-base font-bold tracking-tight text-[var(--brand)]">
      {#if cls}{cls.level[0].toUpperCase()}{cls.year_group}{:else}…{/if}
    </div>

    <div class="min-w-0 flex-1">
      <h1 class="text-xl font-bold tracking-tight text-[var(--fg)]">{cls?.display_name ?? '…'}</h1>
    </div>

    {#if cls}
      <span class="mt-0.5 shrink-0">
        <Badge label={cls.is_active ? 'Active' : 'Inactive'} color={cls.is_active ? 'green' : 'gray'} variant="dot" />
      </span>
    {/if}
  </div>

  <!-- Stats footer + term picker -->
  <div class="flex items-center border-t border-[var(--border)]">
    <!-- Stats -->
    <div class="flex min-w-0 flex-1 divide-x divide-[var(--border)]">
      {#if cls?.capacity}
        <div class="min-w-0 px-4 py-3">
          <p class="text-[11px] font-medium uppercase tracking-wide text-[var(--fg-muted)]">Capacity</p>
          <p class="mt-0.5 text-sm font-semibold text-[var(--fg)]">{cls.capacity} seats</p>
        </div>
      {/if}
      <div class="min-w-0 px-4 py-3">
        <p class="text-[11px] font-medium uppercase tracking-wide text-[var(--fg-muted)]">Level</p>
        <p class="mt-0.5 text-sm font-semibold text-[var(--fg)]">{cls?.level ?? '—'}</p>
      </div>
      <div class="min-w-0 px-4 py-3">
        <p class="text-[11px] font-medium uppercase tracking-wide text-[var(--fg-muted)]">Year Group</p>
        <p class="mt-0.5 text-sm font-semibold text-[var(--fg)]">Year {cls?.year_group ?? '—'}</p>
      </div>
      {#if cls?.programme_name}
        <div class="min-w-0 px-4 py-3">
          <p class="text-[11px] font-medium uppercase tracking-wide text-[var(--fg-muted)]">Programme</p>
          <p class="mt-0.5 truncate text-sm font-semibold text-[var(--fg)]">{cls.programme_name}</p>
        </div>
      {/if}
    </div>

    <!-- Term picker -->
    <div class="flex shrink-0 items-center gap-2 border-l border-[var(--border)] px-4 py-3">
      <span class="text-[11px] font-medium uppercase tracking-wide text-[var(--fg-muted)]">Term</span>
      <select
        bind:value={selectedTermId}
        class="h-7 rounded-md border border-[var(--border)] bg-[var(--bg)] px-2 text-xs text-[var(--fg)] focus:outline-none focus:ring-2 focus:ring-[var(--brand)]"
      >
        <option value="">— Select —</option>
        {#each terms as t}
          <option value={t.id}>{t.name}{t.is_current ? ' ✓' : ''}</option>
        {/each}
      </select>
    </div>
  </div>
</div>

{@render children()}
