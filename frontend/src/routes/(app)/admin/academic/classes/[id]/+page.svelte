<script lang="ts">
  import { createQuery, createMutation, useQueryClient } from '@tanstack/svelte-query';
  import { page } from '$app/stores';
  import { goto } from '$app/navigation';
  import { getClass, updateClass, listAllTerms, listYears } from '$lib/api/academic';
  import { toast } from '$lib/stores/toast';
  import StudentsTab from './StudentsTab.svelte';
  import SubjectsTab from './SubjectsTab.svelte';
  import TeachersTab from './TeachersTab.svelte';

  const qc      = useQueryClient();
  const classId = $derived($page.params.id);

  const classQ  = createQuery({ queryKey: ['class', classId], queryFn: () => getClass(classId), staleTime: 60_000 });
  const yearsQ  = createQuery({ queryKey: ['academic-years'], queryFn: listYears,    staleTime: 5 * 60_000 });
  const termsQ  = createQuery({ queryKey: ['all-terms'],      queryFn: listAllTerms, staleTime: 5 * 60_000 });

  const currentYearId = $derived(($termsQ.data ?? []).find(t => t.is_current)?.academic_year_id ?? '');
  const currentTermId = $derived(($termsQ.data ?? []).find(t => t.is_current)?.id ?? '');

  type Tab = 'students' | 'subjects' | 'teachers';
  let activeTab = $state<Tab>('students');

  // ── Edit ──────────────────────────────────────────────────────────────────────
  let editing  = $state(false);
  let editStream   = $state('');
  let editCapacity = $state('');
  let editActive   = $state(true);
  let editErr  = $state('');

  function startEdit() {
    const c = $classQ.data!;
    editStream   = c.stream ?? '';
    editCapacity = c.capacity != null ? String(c.capacity) : '';
    editActive   = c.is_active;
    editErr = ''; editing = true;
  }

  const editMut = createMutation({
    mutationFn: () => updateClass(classId, {
      stream:    editStream.trim() || null,
      capacity:  editCapacity ? parseInt(editCapacity) : null,
      is_active: editActive,
    }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['class', classId] });
      qc.invalidateQueries({ queryKey: ['classes'] });
      editing = false; toast.success('Class updated.');
    },
    onError: (e: unknown) => {
      editErr = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? 'Could not update.';
    },
  });
</script>

<svelte:head><title>{$classQ.data?.display_name ?? 'Class'}</title></svelte:head>

<!-- Back link -->
<button onclick={() => goto('/admin/academic/classes')}
  class="mb-3 flex items-center gap-1 text-xs text-[var(--fg-muted)] transition hover:text-[var(--fg)]">
  <svg class="h-3.5 w-3.5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
    <path stroke-linecap="round" stroke-linejoin="round" d="M10.5 19.5L3 12m0 0l7.5-7.5M3 12h18"/>
  </svg>
  All classes
</button>

{#if $classQ.isPending}
  <div class="h-28 animate-pulse rounded-2xl bg-[var(--card)]"></div>
{:else if $classQ.data}
  {@const c = $classQ.data}

  <!-- Header card -->
  <div class="mb-5 rounded-2xl border border-[var(--border)] bg-[var(--card)] p-5">
    {#if editing}
      <div class="space-y-3">
        <div class="grid gap-3 sm:grid-cols-3">
          <div>
            <label class="lx">Stream / section</label>
            <input bind:value={editStream} placeholder="e.g. Gold" class="inp mt-1" />
          </div>
          <div>
            <label class="lx">Capacity</label>
            <input type="number" min="1" bind:value={editCapacity} placeholder="e.g. 40" class="inp mt-1" />
          </div>
          <div class="flex items-end pb-1">
            <label class="flex cursor-pointer items-center gap-2 text-sm text-[var(--fg)]">
              <input type="checkbox" bind:checked={editActive} class="h-4 w-4 rounded accent-[var(--brand)]" />
              Active
            </label>
          </div>
        </div>
        {#if editErr}<p class="text-xs text-red-500">{editErr}</p>{/if}
        <div class="flex gap-2">
          <button onclick={() => $editMut.mutate()} disabled={$editMut.isPending}
            class="rounded-xl px-4 py-2 text-sm font-semibold text-white transition hover:opacity-90 disabled:opacity-50"
            style="background:var(--brand)">{$editMut.isPending ? 'Saving…' : 'Save changes'}</button>
          <button onclick={() => { editing = false; editErr = ''; }}
            class="rounded-xl border border-[var(--border)] px-4 py-2 text-sm text-[var(--fg-muted)] hover:bg-[var(--hover)] transition">Cancel</button>
        </div>
      </div>
    {:else}
      <div class="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <div class="flex flex-wrap items-center gap-2">
            <h1 class="text-xl font-bold text-[var(--fg)]">{c.display_name}</h1>
            <span class="rounded-full px-2.5 py-0.5 text-[10px] font-bold ring-1 ring-inset
              {c.is_active
                ? 'bg-green-50 text-green-700 ring-green-600/20 dark:bg-green-950/30 dark:text-green-400'
                : 'bg-[var(--hover)] text-[var(--fg-muted)] ring-[var(--border)]'}">
              {c.is_active ? 'Active' : 'Inactive'}
            </span>
          </div>
          <div class="mt-1.5 flex flex-wrap gap-x-4 gap-y-0.5 text-xs text-[var(--fg-muted)]">
            <span><span class="font-medium text-[var(--fg-subtle)]">Level</span> {c.level}</span>
            <span><span class="font-medium text-[var(--fg-subtle)]">Year</span> {c.year_group}</span>
            {#if c.programme_name}<span><span class="font-medium text-[var(--fg-subtle)]">Programme</span> {c.programme_name}</span>{/if}
            {#if c.stream}<span><span class="font-medium text-[var(--fg-subtle)]">Stream</span> {c.stream}</span>{/if}
            {#if c.capacity != null}<span><span class="font-medium text-[var(--fg-subtle)]">Capacity</span> {c.capacity}</span>{/if}
          </div>
        </div>
        <button onclick={startEdit}
          class="flex shrink-0 items-center gap-1.5 self-start rounded-xl border border-[var(--border)] px-3 py-1.5 text-xs font-medium text-[var(--fg-muted)] transition hover:bg-[var(--hover)] hover:text-[var(--fg)]">
          <svg class="h-3.5 w-3.5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" d="M15.232 5.232l3.536 3.536M9 13l6.586-6.586a2 2 0 012.828 2.828L11.828 15.828a2 2 0 01-1.414.586H9v-2a2 2 0 01.586-1.414z"/>
          </svg>
          Edit
        </button>
      </div>
    {/if}
  </div>

  <!-- Tab nav -->
  <div class="mb-5 border-b border-[var(--border)]">
    <nav class="-mb-px flex gap-1">
      {#each ([['students','Students'],['subjects','Subjects'],['teachers','Teachers']] as const) as [key, label]}
        <button onclick={() => activeTab = key}
          class="relative px-4 pb-3 pt-1 text-sm font-medium transition
                 {activeTab === key ? 'text-[var(--brand)]' : 'text-[var(--fg-muted)] hover:text-[var(--fg)]'}">
          {label}
          {#if activeTab === key}
            <span class="absolute bottom-0 left-0 right-0 h-0.5 rounded-t-sm bg-[var(--brand)]"></span>
          {/if}
        </button>
      {/each}
    </nav>
  </div>

  <!-- Tab content -->
  {#if activeTab === 'students'}
    <StudentsTab {classId} capacity={c.capacity} />
  {:else if activeTab === 'subjects'}
    <SubjectsTab {classId} />
  {:else}
    <TeachersTab {classId} {currentYearId} {currentTermId} years={$yearsQ.data ?? []} terms={$termsQ.data ?? []} />
  {/if}
{/if}

<style>
  @reference "tailwindcss";
  .lx  { @apply block text-xs font-medium text-[var(--fg-muted)]; }
  .inp { @apply w-full rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--fg)] placeholder:text-[var(--fg-subtle)] focus:border-[var(--brand)] focus:outline-none transition; }
</style>
