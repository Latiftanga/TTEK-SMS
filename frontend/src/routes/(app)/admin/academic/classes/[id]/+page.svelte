<script lang="ts">
  import { createQuery, createMutation, useQueryClient } from '@tanstack/svelte-query';
  import { page } from '$app/stores';
  import { goto } from '$app/navigation';
  import { getClass, updateClass, listClassSubjects, listYears } from '$lib/api/academic';
  import { listStudents } from '$lib/api/students';
  import { reactiveQuery } from '$lib/query.svelte';
  import { toast } from '$lib/stores/toast';
  import { setPageTitle } from '$lib/stores/title';
  import StudentsTab from './StudentsTab.svelte';
  import SubjectsTab from './SubjectsTab.svelte';
  import PromoteSection from './PromoteSection.svelte';

  const qc      = useQueryClient();
  const classId = $derived($page.params.id!);

  const classQ = createQuery({ queryKey: ['class', classId], queryFn: () => getClass(classId), staleTime: 60_000 });

  // Shared cache with child tabs — fetches once, both page + tabs read from cache
  const studentsQ = createQuery({ queryKey: ['students', 'class', classId], queryFn: () => listStudents({ class_id: classId, active_only: true }), staleTime: 60_000 });
  const subjQ     = createQuery({ queryKey: ['class-subjects', classId],    queryFn: () => listClassSubjects(classId), staleTime: 2 * 60_000 });

  const studentCount = $derived($studentsQ.data?.length ?? null);
  const subjectCount = $derived($subjQ.data?.length ?? null);

  // Current-term registration status — powers the attention badge on the
  // Students tab (term registration is now folded into that tab, not its
  // own separate tab). Shares the ['academic-years'] cache key used
  // elsewhere (Promote tab, etc.).
  const yearsQ = createQuery({ queryKey: ['academic-years'], queryFn: listYears, staleTime: 5 * 60_000 });
  const currentTermId = $derived(($yearsQ.data ?? []).flatMap(y => y.terms).find(t => t.is_current)?.id ?? '');
  const termRosterQ = reactiveQuery(() => ({
    queryKey: ['students', 'class', classId, 'term', currentTermId] as const,
    queryFn:  () => listStudents({ class_id: classId, active_only: true, term_id: currentTermId }),
    enabled:  !!currentTermId,
    staleTime: 30_000,
  }));
  const notRegisteredCount = $derived(
    currentTermId && studentCount !== null && $termRosterQ.data !== undefined
      ? Math.max(0, studentCount - $termRosterQ.data.length)
      : null
  );

  // ── Edit ──────────────────────────────────────────────────────────────────────
  let editing      = $state(false);
  let editStream   = $state('');
  let editCapacity = $state('');
  let editActive   = $state(true);
  let editErr      = $state('');

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

  const LEVEL_COLOR: Record<string, string> = {
    SHS: '#7c3aed', JHS: '#2563eb', PRIMARY: '#0d9488',
    KINDERGARTEN: '#d97706', NURSERY: '#f59e0b',
  };
  function levelBg(level: string) { return LEVEL_COLOR[level] ?? '#6366f1'; }

  $effect(() => setPageTitle($classQ.data?.display_name ?? 'Class'));

  // ── Tab navigation ────────────────────────────────────────────────────────────
  type Tab = 'students' | 'subjects' | 'promote';
  const VALID_TABS: Tab[] = ['subjects', 'promote'];
  const initialTab = $page.url.searchParams.get('tab');
  let activeTab = $state<Tab>(VALID_TABS.includes(initialTab as Tab) ? (initialTab as Tab) : 'students');
</script>

<!-- Back link -->
<button onclick={() => goto('/admin/academic/classes')}
  class="mb-4 flex items-center gap-1.5 text-xs text-[var(--fg-muted)] transition hover:text-[var(--fg)]">
  <svg class="h-3.5 w-3.5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
    <path stroke-linecap="round" stroke-linejoin="round" d="M10.5 19.5L3 12m0 0l7.5-7.5M3 12h18"/>
  </svg>
  All classes
</button>

{#if $classQ.isPending}
  <div class="h-32 animate-pulse rounded-2xl bg-[var(--card)]"></div>
{:else if $classQ.data}
  {@const c = $classQ.data}

  <!-- Header card -->
  <div class="mb-8 overflow-hidden rounded-2xl border border-[var(--border)] bg-[var(--card)]">
    {#if editing}
      <!-- Edit form -->
      <div class="border-b border-[var(--border)] bg-[var(--hover)]/30 px-5 py-3">
        <p class="text-[10px] font-bold uppercase tracking-widest text-[var(--fg-subtle)]">Editing {c.display_name}</p>
      </div>
      <div class="p-5 space-y-3">
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
            class="rounded-xl border border-[var(--border)] px-4 py-2 text-sm text-[var(--fg-muted)] transition hover:bg-[var(--hover)]">Cancel</button>
        </div>
      </div>
    {:else}
      <!-- Class identity -->
      <div class="flex items-start gap-4 p-5">
        <!-- Level avatar -->
        <div class="flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl text-lg font-black text-white shadow-sm"
             style="background: {levelBg(c.level)}">
          {c.level.toUpperCase() === 'CRECHE' ? c.level[0] : c.year_group}
        </div>
        <div class="min-w-0 flex-1">
          <div class="flex items-start justify-between gap-3">
            <div>
              <h1 class="text-xl font-bold leading-tight text-[var(--fg)]">{c.display_name}</h1>
              <div class="mt-2 flex flex-wrap items-center gap-1.5">
                <span class="badge {c.is_active ? 'badge-success' : 'badge-neutral'}">{c.is_active ? 'Active' : 'Inactive'}</span>
                <span class="chip">{c.level}</span>
                {#if c.programme_name}<span class="chip">{c.programme_name}</span>{/if}
                {#if c.stream}<span class="chip">Stream: {c.stream}</span>{/if}
                {#if c.capacity != null}<span class="chip">Capacity: {c.capacity}</span>{/if}
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
        </div>
      </div>
      <!-- Quick stats footer -->
      {#if studentCount !== null || subjectCount !== null}
        <div class="flex gap-6 border-t border-[var(--border)] px-5 py-3">
          {#if studentCount !== null}
            <div class="flex items-center gap-2 text-xs">
              <svg class="h-3.5 w-3.5 text-[var(--fg-subtle)]" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" d="M15 19.128a9.38 9.38 0 002.625.372 9.337 9.337 0 004.121-.952 4.125 4.125 0 00-7.533-2.493M15 19.128v-.003c0-1.113-.285-2.16-.786-3.07M15 19.128v.106A12.318 12.318 0 018.624 21c-2.331 0-4.512-.645-6.374-1.766l-.001-.109a6.375 6.375 0 0111.964-3.07M12 6.375a3.375 3.375 0 11-6.75 0 3.375 3.375 0 016.75 0zm8.25 2.25a2.625 2.625 0 11-5.25 0 2.625 2.625 0 015.25 0z"/>
              </svg>
              <span class="text-[var(--fg-muted)]"><strong class="font-semibold text-[var(--fg)]">{studentCount}</strong> student{studentCount !== 1 ? 's' : ''}{c.capacity ? ` / ${c.capacity}` : ''}</span>
            </div>
          {/if}
          {#if subjectCount !== null}
            <div class="flex items-center gap-2 text-xs">
              <svg class="h-3.5 w-3.5 text-[var(--fg-subtle)]" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" d="M12 6.042A8.967 8.967 0 006 3.75c-1.052 0-2.062.18-3 .512v14.25A8.987 8.987 0 016 18c2.305 0 4.408.867 6 2.292m0-14.25a8.966 8.966 0 016-2.292c1.052 0 2.062.18 3 .512v14.25A8.987 8.987 0 0018 18a8.967 8.967 0 00-6 2.292m0-14.25v14.25"/>
              </svg>
              <span class="text-[var(--fg-muted)]"><strong class="font-semibold text-[var(--fg)]">{subjectCount}</strong> subject{subjectCount !== 1 ? 's' : ''}</span>
            </div>
          {/if}
        </div>
      {/if}
    {/if}
  </div>

  <!-- Tab bar -->
  <!-- overflow-y-hidden is deliberate — see TabBar.svelte's comment: plain
       overflow-x-auto lets the browser compute overflow-y as auto too,
       which can show an unwanted vertical scrollbar on hover. -->
  <div class="mb-6 flex gap-1 overflow-x-auto overflow-y-hidden border-b border-[var(--border)] [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
    <button onclick={() => activeTab = 'students'} title="Students"
      class="tab {activeTab === 'students' ? 'tab-active' : ''}">
      <svg class="h-4 w-4 shrink-0" fill="none" stroke="currentColor" stroke-width="1.75" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" d="M15 19.128a9.38 9.38 0 002.625.372 9.337 9.337 0 004.121-.952 4.125 4.125 0 00-7.533-2.493M15 19.128v-.003c0-1.113-.285-2.16-.786-3.07M15 19.128v.106A12.318 12.318 0 018.624 21c-2.331 0-4.512-.645-6.374-1.766l-.001-.109a6.375 6.375 0 0111.964-3.07M12 6.375a3.375 3.375 0 11-6.75 0 3.375 3.375 0 016.75 0zm8.25 2.25a2.625 2.625 0 11-5.25 0 2.625 2.625 0 015.25 0z"/>
      </svg>
      <span class="hidden sm:inline">Students</span>
      {#if notRegisteredCount}
        <span class="tab-badge tab-badge-attention {activeTab === 'students' ? 'tab-badge-active' : ''}">{notRegisteredCount}</span>
      {:else if studentCount !== null}
        <span class="tab-badge {activeTab === 'students' ? 'tab-badge-active' : ''}">{studentCount}</span>
      {/if}
    </button>
    <button onclick={() => activeTab = 'subjects'} title="Subjects & Teachers"
      class="tab {activeTab === 'subjects' ? 'tab-active' : ''}">
      <svg class="h-4 w-4 shrink-0" fill="none" stroke="currentColor" stroke-width="1.75" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" d="M12 6.042A8.967 8.967 0 006 3.75c-1.052 0-2.062.18-3 .512v14.25A8.987 8.987 0 016 18c2.305 0 4.408.867 6 2.292m0-14.25a8.966 8.966 0 016-2.292c1.052 0 2.062.18 3 .512v14.25A8.987 8.987 0 0018 18a8.967 8.967 0 00-6 2.292m0-14.25v14.25"/>
      </svg>
      <span class="hidden sm:inline">Subjects & Teachers</span>
      {#if subjectCount !== null}
        <span class="tab-badge {activeTab === 'subjects' ? 'tab-badge-active' : ''}">{subjectCount}</span>
      {/if}
    </button>
    <button onclick={() => activeTab = 'promote'} title="Promote / Transfer"
      class="tab {activeTab === 'promote' ? 'tab-active' : ''}">
      <svg class="h-4 w-4 shrink-0" fill="none" stroke="currentColor" stroke-width="1.75" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" d="M4.5 10.5L12 3m0 0l7.5 7.5M12 3v18"/>
      </svg>
      <span class="hidden sm:inline">Promote / Transfer</span>
    </button>
  </div>

  <!-- Tab panels -->
  {#if activeTab === 'students'}
    <StudentsTab {classId} capacity={c.capacity} classActive={c.is_active} />
  {:else if activeTab === 'subjects'}
    <SubjectsTab {classId} classActive={c.is_active} />
  {:else}
    <PromoteSection {classId} classData={c} />
  {/if}
{/if}

<style>
  @reference "tailwindcss";
  .lx  { @apply block text-xs font-medium text-[var(--fg-muted)]; }
  .inp { @apply w-full rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--fg)] placeholder:text-[var(--fg-subtle)] focus:border-[var(--brand)] focus:outline-none transition; }
  .chip         { @apply inline-flex items-center rounded-full bg-[var(--hover)] px-2.5 py-0.5 text-[10px] font-semibold text-[var(--fg-muted)] ring-1 ring-inset ring-[var(--border)]; }

  .tab {
    @apply -mb-px flex min-h-[44px] shrink-0 items-center gap-1.5 whitespace-nowrap border-b-2 border-transparent px-4 text-sm font-medium text-[var(--fg-muted)] transition hover:text-[var(--fg)];
  }
  .tab-active {
    @apply border-[var(--brand)] text-[var(--brand)];
  }
  .tab-badge {
    @apply rounded-full bg-[var(--hover)] px-1.5 py-0.5 text-[10px] font-bold text-[var(--fg-subtle)];
  }
  .tab-badge-attention {
    @apply bg-amber-500/15 text-amber-600 dark:text-amber-400;
  }
  .tab-badge-active {
    @apply bg-[var(--brand)]/12 text-[var(--brand)];
  }
</style>
