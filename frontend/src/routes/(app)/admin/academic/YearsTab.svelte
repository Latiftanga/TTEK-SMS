<script lang="ts">
  import { createQuery, createMutation, useQueryClient } from '@tanstack/svelte-query';
  import { listYears, createYear, updateYear, setCurrentYear, type AcademicYear } from '$lib/api/academic';
  import TermsSection from './TermsSection.svelte';

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

  let editingYearId = $state<string | null>(null);
  let editYearForm = $state({ name: '', start_date: '', end_date: '' });
  let editYearError = $state('');

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

  const updateYearMut = createMutation({
    mutationFn: ({ id, req }: { id: string; req: { name?: string; start_date?: string; end_date?: string } }) =>
      updateYear(id, req),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['academic-years'] });
      editingYearId = null;
      editYearError = '';
    },
    onError: (e: unknown) => {
      editYearError = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? 'Failed to update.';
    },
  });

  const setCurrentYearMut = createMutation({
    mutationFn: setCurrentYear,
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
</script>

<div class="space-y-5">
  <div class="flex justify-end">
    <button
      onclick={() => { showYearForm = !showYearForm; yearError = ''; }}
      class="flex items-center gap-2 rounded-xl px-4 py-2 text-sm font-semibold text-white shadow-sm transition hover:opacity-90 active:scale-[0.98]"
      style="background-color: var(--brand)"
    >
      <svg class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" d="M12 4v16m8-8H4"/>
      </svg>
      New year
    </button>
  </div>

  {#if showYearForm}
    <div class="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
      <h2 class="mb-4 text-sm font-semibold text-[var(--fg)]">New Academic Year</h2>
      <div class="grid gap-4 sm:grid-cols-3">
        <div>
          <label class="mb-1 block text-xs font-medium text-[var(--fg-muted)]">Year name</label>
          <input bind:value={yearForm.name} placeholder="e.g. 2024/2025"
            class="w-full rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--fg)] placeholder:text-[var(--fg-muted)] focus:border-[var(--brand)] focus:outline-none focus:ring-2 focus:ring-[var(--brand)]/20" />
        </div>
        <div>
          <label class="mb-1 block text-xs font-medium text-[var(--fg-muted)]">Start date</label>
          <input type="date" bind:value={yearForm.start_date}
            class="w-full rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--fg)] focus:border-[var(--brand)] focus:outline-none focus:ring-2 focus:ring-[var(--brand)]/20" />
        </div>
        <div>
          <label class="mb-1 block text-xs font-medium text-[var(--fg-muted)]">End date</label>
          <input type="date" bind:value={yearForm.end_date}
            class="w-full rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--fg)] focus:border-[var(--brand)] focus:outline-none focus:ring-2 focus:ring-[var(--brand)]/20" />
        </div>
      </div>
      {#if yearError}<p class="mt-2 text-xs text-red-500">{yearError}</p>{/if}
      <div class="mt-4 flex gap-2">
        <button onclick={submitYear} disabled={$createYearMut.isPending}
          class="rounded-xl px-4 py-2 text-sm font-semibold text-white transition hover:opacity-90 disabled:opacity-50"
          style="background-color: var(--brand)">
          {$createYearMut.isPending ? 'Creating…' : 'Create year'}
        </button>
        <button onclick={() => { showYearForm = false; yearError = ''; }}
          class="rounded-xl border border-[var(--border)] px-4 py-2 text-sm font-medium text-[var(--fg-muted)] transition hover:bg-[var(--bg)]">
          Cancel
        </button>
      </div>
    </div>
  {/if}

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
    <div class="rounded-xl border border-dashed border-[var(--border)] p-10 text-center">
      <p class="text-sm font-medium text-[var(--fg-muted)]">No academic years yet.</p>
      <p class="mt-1 text-xs text-[var(--fg-muted)]">Create your first one above.</p>
    </div>
  {:else}
    <div class="space-y-3">
      {#each ($yearsQuery.data ?? []) as year (year.id)}
        <div class="overflow-hidden rounded-xl border border-[var(--border)] bg-[var(--card)]">
          <!-- Year header — div, not button, because it contains action buttons -->
          <div class="flex w-full cursor-pointer items-center gap-3 px-4 py-3 text-left transition hover:bg-[var(--bg)]"
               onclick={() => toggle(year.id)}
               role="button" tabindex="0"
               onkeydown={(e) => { if (e.key === 'Enter' || e.key === ' ') toggle(year.id); }}>
            <div class="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl text-xs font-bold text-white"
                 style="background-color: var(--brand); opacity: {year.is_current ? 1 : 0.5}">
              {year.name.slice(0, 2)}
            </div>
            <div class="flex-1 min-w-0">
              <div class="flex items-center gap-2">
                <span class="font-semibold text-[var(--fg)]">{year.name}</span>
                {#if year.is_current}
                  <span class="badge badge-success">Current</span>
                {/if}
              </div>
              <p class="text-xs text-[var(--fg-muted)]">
                {fmtDate(year.start_date)} – {fmtDate(year.end_date)} · {year.terms.length} term{year.terms.length !== 1 ? 's' : ''}
              </p>
            </div>
            <div class="flex shrink-0 items-center gap-2" onclick={(e) => e.stopPropagation()}>
              {#if !year.is_current}
                <button type="button"
                  onclick={() => $setCurrentYearMut.mutate(year.id)}
                  class="inline-flex items-center gap-1 rounded-lg px-2 py-1.5 text-xs font-medium text-[var(--fg-muted)] transition hover:bg-[var(--bg)] hover:text-[var(--fg)]">
                  <svg class="h-3.5 w-3.5 shrink-0" fill="none" stroke="currentColor" stroke-width="1.75" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M11.48 3.499a.562.562 0 011.04 0l2.125 5.111a.563.563 0 00.475.345l5.518.442c.499.04.701.663.321.988l-4.204 3.602a.563.563 0 00-.182.557l1.285 5.385a.562.562 0 01-.84.61l-4.725-2.885a.563.563 0 00-.586 0L6.982 20.54a.562.562 0 01-.84-.61l1.285-5.386a.562.562 0 00-.182-.557l-4.204-3.602a.562.562 0 01.321-.988l5.518-.442a.563.563 0 00.475-.345L11.48 3.5z"/></svg>
                  Set current
                </button>
              {/if}
              <button type="button"
                onclick={() => {
                  editingYearId = year.id;
                  editYearForm = { name: year.name, start_date: year.start_date, end_date: year.end_date };
                  editYearError = '';
                }}
                class="inline-flex items-center gap-1 rounded-lg px-2 py-1.5 text-xs font-medium text-[var(--fg-muted)] transition hover:bg-[var(--bg)] hover:text-[var(--fg)]">
                <svg class="h-3.5 w-3.5 shrink-0" fill="none" stroke="currentColor" stroke-width="1.75" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M16.862 4.487l1.687-1.688a1.875 1.875 0 112.652 2.652L10.582 16.07a4.5 4.5 0 01-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 011.13-1.897l8.932-8.931zm0 0L19.5 7.125M18 14v4.75A2.25 2.25 0 0115.75 21H5.25A2.25 2.25 0 013 18.75V8.25A2.25 2.25 0 015.25 6H10"/></svg>
                Edit
              </button>
              <svg class="h-4 w-4 text-[var(--fg-muted)] transition-transform duration-200 {expandedYearId === year.id ? 'rotate-180' : ''}"
                   fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" d="M19 9l-7 7-7-7"/>
              </svg>
            </div>
          </div>

          <!-- Inline year edit form -->
          {#if editingYearId === year.id}
            <div class="border-t border-[var(--border)] bg-[var(--bg)] px-4 py-3">
              <div class="grid gap-3 sm:grid-cols-3">
                <div>
                  <label class="mb-1 block text-xs font-medium text-[var(--fg-muted)]">Year name</label>
                  <input bind:value={editYearForm.name}
                    class="w-full rounded-lg border border-[var(--border)] bg-[var(--card)] px-3 py-1.5 text-sm text-[var(--fg)] focus:border-[var(--brand)] focus:outline-none" />
                </div>
                <div>
                  <label class="mb-1 block text-xs font-medium text-[var(--fg-muted)]">Start date</label>
                  <input type="date" bind:value={editYearForm.start_date}
                    class="w-full rounded-lg border border-[var(--border)] bg-[var(--card)] px-3 py-1.5 text-sm text-[var(--fg)] focus:border-[var(--brand)] focus:outline-none" />
                </div>
                <div>
                  <label class="mb-1 block text-xs font-medium text-[var(--fg-muted)]">End date</label>
                  <input type="date" bind:value={editYearForm.end_date}
                    class="w-full rounded-lg border border-[var(--border)] bg-[var(--card)] px-3 py-1.5 text-sm text-[var(--fg)] focus:border-[var(--brand)] focus:outline-none" />
                </div>
              </div>
              {#if editYearError}<p class="mt-2 text-xs text-red-500">{editYearError}</p>{/if}
              <div class="mt-3 flex gap-2">
                <button onclick={() => $updateYearMut.mutate({ id: year.id, req: editYearForm })}
                  disabled={$updateYearMut.isPending}
                  class="rounded-lg px-3 py-1.5 text-xs font-semibold text-white hover:opacity-90 disabled:opacity-50"
                  style="background-color: var(--brand)">
                  {$updateYearMut.isPending ? 'Saving…' : 'Save changes'}
                </button>
                <button onclick={() => { editingYearId = null; editYearError = ''; }}
                  class="rounded-lg border border-[var(--border)] px-3 py-1.5 text-xs font-medium text-[var(--fg-muted)] hover:bg-[var(--card)]">
                  Cancel
                </button>
              </div>
            </div>
          {/if}

          <!-- Expanded: terms -->
          {#if expandedYearId === year.id}
            <TermsSection {year} />
          {/if}
        </div>
      {/each}
    </div>
  {/if}
</div>
