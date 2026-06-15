<script lang="ts">
  import { createQuery, createMutation, useQueryClient } from '@tanstack/svelte-query';
  import {
    listYears,
    createYear,
    setCurrentYear,
    createTerm,
    setCurrentTerm,
    type AcademicYear,
  } from '$lib/api/academic';

  const qc = useQueryClient();

  const yearsQuery = createQuery({
    queryKey: ['academic-years'],
    queryFn: listYears,
    staleTime: 5 * 60_000,
  });

  let expandedYearId = $state<string | null>(null);

  let showYearForm = $state(false);
  let yearForm = $state({ name: '', start_date: '', end_date: '' });
  let yearError = $state('');

  let showTermForm = $state<string | null>(null);
  let termForm = $state({ term_number: 1, name: '', start_date: '', end_date: '' });
  let termError = $state('');

  const createYearMut = createMutation({
    mutationFn: createYear,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['academic-years'] });
      showYearForm = false;
      yearForm = { name: '', start_date: '', end_date: '' };
      yearError = '';
    },
    onError: (e: unknown) => {
      yearError = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? 'Failed to create year.';
    },
  });

  const setCurrentYearMut = createMutation({
    mutationFn: setCurrentYear,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['academic-years'] }),
  });

  const createTermMut = createMutation({
    mutationFn: ({ yearId, req }: { yearId: string; req: typeof termForm }) =>
      createTerm(yearId, req),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['academic-years'] });
      showTermForm = null;
      termForm = { term_number: 1, name: '', start_date: '', end_date: '' };
      termError = '';
    },
    onError: (e: unknown) => {
      termError = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? 'Failed to create term.';
    },
  });

  const setCurrentTermMut = createMutation({
    mutationFn: setCurrentTerm,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['academic-years'] }),
  });

  function toggle(yearId: string) {
    expandedYearId = expandedYearId === yearId ? null : yearId;
  }

  function fmtDate(d: string) {
    return new Date(d).toLocaleDateString('en-GH', { day: 'numeric', month: 'short', year: 'numeric' });
  }

  function submitYear() {
    yearError = '';
    if (!yearForm.name || !yearForm.start_date || !yearForm.end_date) {
      yearError = 'All fields are required.';
      return;
    }
    $createYearMut.mutate(yearForm);
  }

  function submitTerm(yearId: string) {
    termError = '';
    if (!termForm.name.trim() || !termForm.start_date || !termForm.end_date) {
      termError = 'Name, start date, and end date are required.';
      return;
    }
    $createTermMut.mutate({ yearId, req: termForm });
  }
</script>

<div class="space-y-6">
  <!-- Header -->
  <div class="flex items-center justify-between">
    <div>
      <h1 class="text-2xl font-bold text-[var(--fg)]">Academic Setup</h1>
      <p class="mt-0.5 text-sm text-[var(--fg-muted)]">Manage academic years and terms</p>
    </div>
    <button
      onclick={() => { showYearForm = !showYearForm; yearError = ''; }}
      class="flex items-center gap-2 rounded-xl px-4 py-2 text-sm font-semibold text-white shadow-sm transition hover:opacity-90 active:scale-[0.98]"
      style="background-color: var(--brand)"
    >
      <svg class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" d="M12 4v16m8-8H4"/>
      </svg>
      New Year
    </button>
  </div>

  <!-- New year form -->
  {#if showYearForm}
    <div class="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
      <h2 class="mb-4 text-sm font-semibold text-[var(--fg)]">New Academic Year</h2>
      <div class="grid gap-4 sm:grid-cols-3">
        <div>
          <label class="mb-1 block text-xs font-medium text-[var(--fg-muted)]">Year name</label>
          <input
            bind:value={yearForm.name}
            placeholder="e.g. 2024/2025"
            class="w-full rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--fg)] placeholder:text-[var(--fg-muted)] focus:border-[var(--brand)] focus:outline-none focus:ring-2 focus:ring-[var(--brand)]/20"
          />
        </div>
        <div>
          <label class="mb-1 block text-xs font-medium text-[var(--fg-muted)]">Start date</label>
          <input
            type="date"
            bind:value={yearForm.start_date}
            class="w-full rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--fg)] focus:border-[var(--brand)] focus:outline-none focus:ring-2 focus:ring-[var(--brand)]/20"
          />
        </div>
        <div>
          <label class="mb-1 block text-xs font-medium text-[var(--fg-muted)]">End date</label>
          <input
            type="date"
            bind:value={yearForm.end_date}
            class="w-full rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--fg)] focus:border-[var(--brand)] focus:outline-none focus:ring-2 focus:ring-[var(--brand)]/20"
          />
        </div>
      </div>
      {#if yearError}
        <p class="mt-2 text-xs text-red-500">{yearError}</p>
      {/if}
      <div class="mt-4 flex gap-2">
        <button
          onclick={submitYear}
          disabled={$createYearMut.isPending}
          class="rounded-xl px-4 py-2 text-sm font-semibold text-white transition hover:opacity-90 disabled:opacity-50"
          style="background-color: var(--brand)"
        >
          {$createYearMut.isPending ? 'Creating…' : 'Create year'}
        </button>
        <button
          onclick={() => { showYearForm = false; yearError = ''; }}
          class="rounded-xl border border-[var(--border)] px-4 py-2 text-sm font-medium text-[var(--fg-muted)] transition hover:bg-[var(--bg)]"
        >
          Cancel
        </button>
      </div>
    </div>
  {/if}

  <!-- Years list -->
  {#if $yearsQuery.isPending}
    <div class="space-y-3">
      {#each [1, 2] as _}
        <div class="h-16 animate-pulse rounded-xl bg-[var(--card)]"></div>
      {/each}
    </div>
  {:else if $yearsQuery.isError}
    <div class="rounded-xl border border-red-100 dark:border-red-900 bg-red-50 dark:bg-red-950/40 p-4 text-sm text-red-600 dark:text-red-400">
      Could not load academic years.
      <button onclick={() => $yearsQuery.refetch()} class="ml-2 underline">Retry</button>
    </div>
  {:else if $yearsQuery.data?.length === 0}
    <div class="rounded-xl border border-dashed border-[var(--border)] p-7 text-center">
      <p class="text-sm text-[var(--fg-muted)]">No academic years yet. Create your first one above.</p>
    </div>
  {:else}
    <div class="space-y-3">
      {#each ($yearsQuery.data ?? []) as year (year.id)}
        <div class="overflow-hidden rounded-xl border border-[var(--border)] bg-[var(--card)]">
          <!-- Year header row -->
          <button
            type="button"
            onclick={() => toggle(year.id)}
            class="flex w-full items-center gap-3 px-4 py-3 text-left transition hover:bg-[var(--bg)]"
          >
            <div class="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl text-xs font-bold text-white"
                 style="background-color: var(--brand); opacity: {year.is_current ? 1 : 0.5}">
              {year.name.slice(0, 2)}
            </div>
            <div class="flex-1 min-w-0">
              <div class="flex items-center gap-2">
                <span class="font-semibold text-[var(--fg)]">{year.name}</span>
                {#if year.is_current}
                  <span class="rounded-full bg-green-100 dark:bg-green-950/50 px-2 py-0.5 text-[10px] font-semibold text-green-700 dark:text-green-400">
                    Current
                  </span>
                {/if}
              </div>
              <p class="text-xs text-[var(--fg-muted)]">
                {fmtDate(year.start_date)} – {fmtDate(year.end_date)} · {year.terms.length} term{year.terms.length !== 1 ? 's' : ''}
              </p>
            </div>
            <div class="flex shrink-0 items-center gap-2">
              {#if !year.is_current}
                <button
                  type="button"
                  onclick={(e) => { e.stopPropagation(); $setCurrentYearMut.mutate(year.id); }}
                  class="rounded-lg border border-[var(--border)] px-3 py-1.5 text-xs font-medium text-[var(--fg-muted)] transition hover:bg-[var(--bg)] hover:text-[var(--fg)]"
                >
                  Set current
                </button>
              {/if}
              <svg class="h-4 w-4 text-[var(--fg-muted)] transition-transform duration-200 {expandedYearId === year.id ? 'rotate-180' : ''}"
                   fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" d="M19 9l-7 7-7-7"/>
              </svg>
            </div>
          </button>

          <!-- Expanded terms -->
          {#if expandedYearId === year.id}
            <div class="border-t border-[var(--border)] px-4 py-3 space-y-3">
              {#each year.terms.slice().sort((a: { term_number: number }, b: { term_number: number }) => a.term_number - b.term_number) as term (term.id)}
                <div class="flex items-center gap-4 rounded-xl border border-[var(--border)] bg-[var(--bg)] px-4 py-3">
                  <div class="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-xs font-bold text-white"
                       style="background-color: var(--brand); opacity: {term.is_current ? 1 : 0.45}">
                    T{term.term_number}
                  </div>
                  <div class="flex-1 min-w-0">
                    <div class="flex items-center gap-2">
                      <span class="text-sm font-medium text-[var(--fg)]">{term.name}</span>
                      {#if term.is_current}
                        <span class="rounded-full bg-green-100 dark:bg-green-950/50 px-2 py-0.5 text-[10px] font-semibold text-green-700 dark:text-green-400">
                          Current
                        </span>
                      {/if}
                    </div>
                    <p class="text-xs text-[var(--fg-muted)]">
                      {fmtDate(term.start_date)} – {fmtDate(term.end_date)}
                    </p>
                  </div>
                  {#if !term.is_current}
                    <button
                      onclick={() => $setCurrentTermMut.mutate(term.id)}
                      class="shrink-0 rounded-lg border border-[var(--border)] px-3 py-1 text-xs font-medium text-[var(--fg-muted)] transition hover:bg-[var(--card)] hover:text-[var(--fg)]"
                    >
                      Set current
                    </button>
                  {/if}
                </div>
              {/each}

              <!-- Add term -->
              {#if showTermForm === year.id}
                <div class="rounded-xl border border-[var(--border)] bg-[var(--bg)] p-4 space-y-3">
                  <h3 class="text-xs font-semibold text-[var(--fg)]">Add term to {year.name}</h3>
                  <div class="grid gap-3 sm:grid-cols-2">
                    <div>
                      <label class="mb-1 block text-xs font-medium text-[var(--fg-muted)]">Session</label>
                      <select
                        bind:value={termForm.term_number}
                        class="w-full rounded-xl border border-[var(--border)] bg-[var(--card)] px-3 py-2 text-sm text-[var(--fg)] focus:border-[var(--brand)] focus:outline-none"
                      >
                        <option value={1}>1</option>
                        <option value={2}>2</option>
                        <option value={3}>3</option>
                      </select>
                    </div>
                    <div>
                      <label class="mb-1 block text-xs font-medium text-[var(--fg-muted)]">Name</label>
                      <input
                        bind:value={termForm.name}
                        placeholder="e.g. First Term, Semester 1"
                        class="w-full rounded-xl border border-[var(--border)] bg-[var(--card)] px-3 py-2 text-sm text-[var(--fg)] placeholder:text-[var(--fg-subtle)] focus:border-[var(--brand)] focus:outline-none"
                      />
                    </div>
                    <div>
                      <label class="mb-1 block text-xs font-medium text-[var(--fg-muted)]">Start date</label>
                      <input
                        type="date"
                        bind:value={termForm.start_date}
                        class="w-full rounded-xl border border-[var(--border)] bg-[var(--card)] px-3 py-2 text-sm text-[var(--fg)] focus:border-[var(--brand)] focus:outline-none"
                      />
                    </div>
                    <div>
                      <label class="mb-1 block text-xs font-medium text-[var(--fg-muted)]">End date</label>
                      <input
                        type="date"
                        bind:value={termForm.end_date}
                        class="w-full rounded-xl border border-[var(--border)] bg-[var(--card)] px-3 py-2 text-sm text-[var(--fg)] focus:border-[var(--brand)] focus:outline-none"
                      />
                    </div>
                  </div>
                  {#if termError}
                    <p class="text-xs text-red-500">{termError}</p>
                  {/if}
                  <div class="flex gap-2">
                    <button
                      onclick={() => submitTerm(year.id)}
                      disabled={$createTermMut.isPending}
                      class="rounded-xl px-4 py-2 text-xs font-semibold text-white transition hover:opacity-90 disabled:opacity-50"
                      style="background-color: var(--brand)"
                    >
                      {$createTermMut.isPending ? 'Adding…' : 'Add term'}
                    </button>
                    <button
                      onclick={() => { showTermForm = null; termError = ''; }}
                      class="rounded-xl border border-[var(--border)] px-4 py-2 text-xs font-medium text-[var(--fg-muted)] transition hover:bg-[var(--card)]"
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              {:else}
                <button
                  onclick={() => { showTermForm = year.id; termError = ''; }}
                  class="flex w-full items-center gap-2 rounded-xl border border-dashed border-[var(--border)] px-4 py-2.5 text-xs font-medium text-[var(--fg-muted)] transition hover:border-[var(--brand)] hover:text-[var(--brand)]"
                >
                  <svg class="h-3.5 w-3.5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M12 4v16m8-8H4"/>
                  </svg>
                  Add term
                </button>
              {/if}
            </div>
          {/if}
        </div>
      {/each}
    </div>
  {/if}
</div>
