<script lang="ts">
  import { createMutation, useQueryClient } from '@tanstack/svelte-query';
  import { createTerm, updateTerm, setCurrentTerm, type AcademicYear } from '$lib/api/academic';

  const { year } = $props<{ year: AcademicYear }>();

  const qc = useQueryClient();

  let showTermForm = $state(false);
  let termForm = $state({ term_number: 1, name: '', start_date: '', end_date: '' });
  let termError = $state('');

  let editingTermId = $state<string | null>(null);
  let editTermForm = $state({ name: '', start_date: '', end_date: '' });
  let editTermError = $state('');

  const createTermMut = createMutation({
    mutationFn: (req: typeof termForm) => createTerm(year.id, req),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['academic-years'] });
      showTermForm = false;
      termForm = { term_number: 1, name: '', start_date: '', end_date: '' };
      termError = '';
    },
    onError: (e: unknown) => {
      termError = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? 'Failed to create term.';
    },
  });

  const updateTermMut = createMutation({
    mutationFn: ({ id, req }: { id: string; req: { name?: string; start_date?: string; end_date?: string } }) =>
      updateTerm(id, req),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['academic-years'] });
      editingTermId = null;
      editTermError = '';
    },
    onError: (e: unknown) => {
      editTermError = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? 'Failed to update.';
    },
  });

  const setCurrentTermMut = createMutation({
    mutationFn: setCurrentTerm,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['academic-years'] }),
  });

  function fmtDate(d: string) {
    return new Date(d).toLocaleDateString('en-GH', { day: 'numeric', month: 'short', year: 'numeric' });
  }

  function submitTerm() {
    termError = '';
    if (!termForm.name.trim() || !termForm.start_date || !termForm.end_date) {
      termError = 'Name, start date, and end date are required.';
      return;
    }
    $createTermMut.mutate(termForm);
  }
</script>

<div class="border-t border-[var(--border)] px-4 py-3 space-y-3">
  {#each year.terms.slice().sort((a, b) => a.term_number - b.term_number) as term (term.id)}
    {#if editingTermId === term.id}
      <div class="rounded-xl border border-[var(--brand)]/30 bg-[var(--bg)] px-4 py-3 space-y-3">
        <div class="grid gap-3 sm:grid-cols-3">
          <div>
            <label class="mb-1 block text-xs font-medium text-[var(--fg-muted)]">Name</label>
            <input bind:value={editTermForm.name}
              class="w-full rounded-lg border border-[var(--border)] bg-[var(--card)] px-2 py-1.5 text-sm text-[var(--fg)] focus:border-[var(--brand)] focus:outline-none" />
          </div>
          <div>
            <label class="mb-1 block text-xs font-medium text-[var(--fg-muted)]">Start date</label>
            <input type="date" bind:value={editTermForm.start_date}
              class="w-full rounded-lg border border-[var(--border)] bg-[var(--card)] px-2 py-1.5 text-sm text-[var(--fg)] focus:border-[var(--brand)] focus:outline-none" />
          </div>
          <div>
            <label class="mb-1 block text-xs font-medium text-[var(--fg-muted)]">End date</label>
            <input type="date" bind:value={editTermForm.end_date}
              class="w-full rounded-lg border border-[var(--border)] bg-[var(--card)] px-2 py-1.5 text-sm text-[var(--fg)] focus:border-[var(--brand)] focus:outline-none" />
          </div>
        </div>
        {#if editTermError}<p class="text-xs text-red-500">{editTermError}</p>{/if}
        <div class="flex gap-2">
          <button onclick={() => $updateTermMut.mutate({ id: term.id, req: editTermForm })}
            disabled={$updateTermMut.isPending}
            class="rounded-lg px-3 py-1.5 text-xs font-semibold text-white hover:opacity-90 disabled:opacity-50"
            style="background-color: var(--brand)">
            {$updateTermMut.isPending ? 'Saving…' : 'Save'}
          </button>
          <button onclick={() => { editingTermId = null; editTermError = ''; }}
            class="rounded-lg border border-[var(--border)] px-3 py-1.5 text-xs font-medium text-[var(--fg-muted)] hover:bg-[var(--card)]">
            Cancel
          </button>
        </div>
      </div>
    {:else}
      <div class="group flex items-center gap-4 rounded-xl border border-[var(--border)] bg-[var(--bg)] px-4 py-3">
        <div class="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-xs font-bold text-white"
             style="background-color: var(--brand); opacity: {term.is_current ? 1 : 0.45}">
          T{term.term_number}
        </div>
        <div class="flex-1 min-w-0">
          <div class="flex items-center gap-2">
            <span class="text-sm font-medium text-[var(--fg)]">{term.name}</span>
            {#if term.is_current}
              <span class="badge badge-success">Current</span>
            {/if}
          </div>
          <p class="text-xs text-[var(--fg-muted)]">{fmtDate(term.start_date)} – {fmtDate(term.end_date)}</p>
        </div>
        <div class="flex shrink-0 items-center gap-2">
          {#if !term.is_current}
            <button onclick={() => $setCurrentTermMut.mutate(term.id)}
              class="inline-flex items-center gap-1 rounded-lg px-2 py-1 text-xs font-medium text-[var(--fg-muted)] transition hover:bg-[var(--card)] hover:text-[var(--fg)]">
              <svg class="h-3.5 w-3.5 shrink-0" fill="none" stroke="currentColor" stroke-width="1.75" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M11.48 3.499a.562.562 0 011.04 0l2.125 5.111a.563.563 0 00.475.345l5.518.442c.499.04.701.663.321.988l-4.204 3.602a.563.563 0 00-.182.557l1.285 5.385a.562.562 0 01-.84.61l-4.725-2.885a.563.563 0 00-.586 0L6.982 20.54a.562.562 0 01-.84-.61l1.285-5.386a.562.562 0 00-.182-.557l-4.204-3.602a.562.562 0 01.321-.988l5.518-.442a.563.563 0 00.475-.345L11.48 3.5z"/></svg>
              Set current
            </button>
          {/if}
          <button
            onclick={() => { editingTermId = term.id; editTermForm = { name: term.name, start_date: term.start_date, end_date: term.end_date }; editTermError = ''; }}
            class="inline-flex items-center gap-1 rounded-lg px-2 py-1 text-xs font-medium text-[var(--fg-muted)] opacity-0 transition group-hover:opacity-100 hover:bg-[var(--card)] hover:text-[var(--fg)]">
            <svg class="h-3.5 w-3.5 shrink-0" fill="none" stroke="currentColor" stroke-width="1.75" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M16.862 4.487l1.687-1.688a1.875 1.875 0 112.652 2.652L10.582 16.07a4.5 4.5 0 01-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 011.13-1.897l8.932-8.931zm0 0L19.5 7.125M18 14v4.75A2.25 2.25 0 0115.75 21H5.25A2.25 2.25 0 013 18.75V8.25A2.25 2.25 0 015.25 6H10"/></svg>
            Edit
          </button>
        </div>
      </div>
    {/if}
  {/each}

  {#if showTermForm}
    <div class="rounded-xl border border-[var(--border)] bg-[var(--bg)] p-4 space-y-3">
      <h3 class="text-xs font-semibold text-[var(--fg)]">Add term to {year.name}</h3>
      <div class="grid gap-3 sm:grid-cols-2">
        <div>
          <label class="mb-1 block text-xs font-medium text-[var(--fg-muted)]">Session</label>
          <select bind:value={termForm.term_number}
            class="w-full rounded-xl border border-[var(--border)] bg-[var(--card)] px-3 py-2 text-sm text-[var(--fg)] focus:border-[var(--brand)] focus:outline-none">
            <option value={1}>1</option>
            <option value={2}>2</option>
            <option value={3}>3</option>
          </select>
        </div>
        <div>
          <label class="mb-1 block text-xs font-medium text-[var(--fg-muted)]">Name</label>
          <input bind:value={termForm.name} placeholder="e.g. First Term, Semester 1"
            class="w-full rounded-xl border border-[var(--border)] bg-[var(--card)] px-3 py-2 text-sm text-[var(--fg)] placeholder:text-[var(--fg-subtle)] focus:border-[var(--brand)] focus:outline-none" />
        </div>
        <div>
          <label class="mb-1 block text-xs font-medium text-[var(--fg-muted)]">Start date</label>
          <input type="date" bind:value={termForm.start_date}
            class="w-full rounded-xl border border-[var(--border)] bg-[var(--card)] px-3 py-2 text-sm text-[var(--fg)] focus:border-[var(--brand)] focus:outline-none" />
        </div>
        <div>
          <label class="mb-1 block text-xs font-medium text-[var(--fg-muted)]">End date</label>
          <input type="date" bind:value={termForm.end_date}
            class="w-full rounded-xl border border-[var(--border)] bg-[var(--card)] px-3 py-2 text-sm text-[var(--fg)] focus:border-[var(--brand)] focus:outline-none" />
        </div>
      </div>
      {#if termError}<p class="text-xs text-red-500">{termError}</p>{/if}
      <div class="flex gap-2">
        <button onclick={submitTerm} disabled={$createTermMut.isPending}
          class="rounded-xl px-4 py-2 text-xs font-semibold text-white transition hover:opacity-90 disabled:opacity-50"
          style="background-color: var(--brand)">
          {$createTermMut.isPending ? 'Adding…' : 'Add term'}
        </button>
        <button onclick={() => { showTermForm = false; termError = ''; }}
          class="rounded-xl border border-[var(--border)] px-4 py-2 text-xs font-medium text-[var(--fg-muted)] transition hover:bg-[var(--card)]">
          Cancel
        </button>
      </div>
    </div>
  {:else}
    <button onclick={() => { showTermForm = true; termError = ''; }}
      class="flex w-full items-center gap-2 rounded-xl border border-dashed border-[var(--border)] px-4 py-2.5 text-xs font-medium text-[var(--fg-muted)] transition hover:border-[var(--brand)] hover:text-[var(--brand)]">
      <svg class="h-3.5 w-3.5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" d="M12 4v16m8-8H4"/>
      </svg>
      Add term
    </button>
  {/if}
</div>
