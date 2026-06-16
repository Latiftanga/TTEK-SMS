<script lang="ts">
  import { createQuery, createMutation, useQueryClient } from '@tanstack/svelte-query';
  import { listSubjects, createSubject, updateSubject, type Subject } from '$lib/api/academic';

  const qc = useQueryClient();

  const subjectsQuery = createQuery({
    queryKey: ['subjects'],
    queryFn: listSubjects,
    staleTime: 5 * 60_000,
  });

  let showForm = $state(false);
  let form = $state({ code: '', name: '' });
  let formError = $state('');

  let editingId = $state<string | null>(null);
  let editForm = $state({ code: '', name: '' });
  let editError = $state('');

  const createMut = createMutation({
    mutationFn: createSubject,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['subjects'] });
      showForm = false;
      form = { code: '', name: '' };
      formError = '';
    },
    onError: (e: unknown) => {
      formError = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? 'Failed to create subject.';
    },
  });

  const updateMut = createMutation({
    mutationFn: ({ id, req }: { id: string; req: { code?: string; name?: string; is_active?: boolean } }) =>
      updateSubject(id, req),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['subjects'] });
      editingId = null;
      editError = '';
    },
    onError: (e: unknown) => {
      editError = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? 'Failed to update.';
    },
  });

  function startEdit(subj: Subject) {
    editingId = subj.id;
    editForm = { code: subj.code, name: subj.name };
    editError = '';
  }

  function submitCreate() {
    formError = '';
    if (!form.code.trim() || !form.name.trim()) { formError = 'Code and name are required.'; return; }
    $createMut.mutate({ code: form.code.toUpperCase(), name: form.name });
  }

  function submitEdit() {
    editError = '';
    if (!editForm.code.trim() || !editForm.name.trim()) { editError = 'Code and name are required.'; return; }
    $updateMut.mutate({ id: editingId!, req: { code: editForm.code, name: editForm.name } });
  }

  function deactivate(id: string) {
    $updateMut.mutate({ id, req: { is_active: false } });
  }
</script>

<div class="space-y-4">
  <div class="flex justify-end">
    <button
      onclick={() => { showForm = !showForm; formError = ''; }}
      class="flex items-center gap-2 rounded-xl px-4 py-2 text-sm font-semibold text-white transition hover:opacity-90"
      style="background-color: var(--brand)"
    >
      <svg class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" d="M12 4v16m8-8H4"/>
      </svg>
      Add subject
    </button>
  </div>

  {#if showForm}
    <div class="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
      <h2 class="mb-4 text-sm font-semibold text-[var(--fg)]">New Subject</h2>
      <div class="grid gap-4 sm:grid-cols-2">
        <div>
          <label class="mb-1 block text-xs font-medium text-[var(--fg-muted)]">Code</label>
          <input bind:value={form.code} placeholder="e.g. MATH"
            class="w-full rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--fg)] placeholder:text-[var(--fg-muted)] focus:border-[var(--brand)] focus:outline-none" />
        </div>
        <div>
          <label class="mb-1 block text-xs font-medium text-[var(--fg-muted)]">Name</label>
          <input bind:value={form.name} placeholder="e.g. Mathematics"
            class="w-full rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--fg)] placeholder:text-[var(--fg-muted)] focus:border-[var(--brand)] focus:outline-none" />
        </div>
      </div>
      {#if formError}<p class="mt-2 text-xs text-red-500">{formError}</p>{/if}
      <div class="mt-4 flex gap-2">
        <button onclick={submitCreate} disabled={$createMut.isPending}
          class="rounded-xl px-4 py-2 text-sm font-semibold text-white transition hover:opacity-90 disabled:opacity-50"
          style="background-color: var(--brand)">
          {$createMut.isPending ? 'Creating…' : 'Create subject'}
        </button>
        <button onclick={() => { showForm = false; formError = ''; }}
          class="rounded-xl border border-[var(--border)] px-4 py-2 text-sm font-medium text-[var(--fg-muted)] transition hover:bg-[var(--bg)]">
          Cancel
        </button>
      </div>
    </div>
  {/if}

  {#if $subjectsQuery.isPending}
    <div class="space-y-2">
      {#each [1,2,3,4,5] as _}
        <div class="h-12 animate-pulse rounded-xl bg-[var(--card)]"></div>
      {/each}
    </div>
  {:else if ($subjectsQuery.data ?? []).length === 0}
    <div class="rounded-xl border border-dashed border-[var(--border)] p-7 text-center">
      <p class="text-sm text-[var(--fg-muted)]">No subjects yet.</p>
    </div>
  {:else}
    <div class="overflow-hidden rounded-xl border border-[var(--border)] bg-[var(--card)]">
      <table class="w-full text-sm">
        <thead>
          <tr class="border-b border-[var(--border)] text-left">
            <th class="px-4 py-2.5 text-xs font-semibold uppercase tracking-widest text-[var(--fg-muted)]">Code</th>
            <th class="px-4 py-2.5 text-xs font-semibold uppercase tracking-widest text-[var(--fg-muted)]">Name</th>
            <th class="px-4 py-2.5"></th>
          </tr>
        </thead>
        <tbody class="divide-y divide-[var(--border)]">
          {#each ($subjectsQuery.data ?? []).sort((a: Subject, b: Subject) => a.name.localeCompare(b.name)) as subj (subj.id)}
            {#if editingId === subj.id}
              <tr class="bg-[var(--bg)]">
                <td class="px-3 py-2">
                  <input bind:value={editForm.code}
                    class="w-20 rounded-lg border border-[var(--border)] bg-[var(--card)] px-2 py-1 font-mono text-xs uppercase text-[var(--fg)] focus:border-[var(--brand)] focus:outline-none" />
                </td>
                <td class="px-3 py-2">
                  <input bind:value={editForm.name}
                    class="w-full rounded-lg border border-[var(--border)] bg-[var(--card)] px-2 py-1 text-sm text-[var(--fg)] focus:border-[var(--brand)] focus:outline-none" />
                  {#if editError}<p class="mt-1 text-[10px] text-red-500">{editError}</p>{/if}
                </td>
                <td class="px-3 py-2 text-right">
                  <div class="flex items-center justify-end gap-1.5">
                    <button onclick={submitEdit} disabled={$updateMut.isPending}
                      class="rounded-lg px-3 py-1.5 text-xs font-semibold text-white transition hover:opacity-90 disabled:opacity-50"
                      style="background-color: var(--brand)">
                      {$updateMut.isPending ? '…' : 'Save'}
                    </button>
                    <button onclick={() => { editingId = null; editError = ''; }}
                      class="rounded-lg border border-[var(--border)] px-3 py-1.5 text-xs font-medium text-[var(--fg-muted)] transition hover:bg-[var(--card)]">
                      Cancel
                    </button>
                  </div>
                </td>
              </tr>
            {:else}
              <tr class="group transition hover:bg-[var(--bg)]">
                <td class="px-4 py-2.5 font-mono text-xs text-[var(--fg-muted)]">{subj.code}</td>
                <td class="px-4 py-2.5 font-medium text-[var(--fg)]">{subj.name}</td>
                <td class="px-4 py-2.5 text-right">
                  <div class="flex items-center justify-end gap-1 opacity-0 transition group-hover:opacity-100">
                    <button onclick={() => startEdit(subj)}
                      class="inline-flex items-center gap-1 rounded-lg px-2 py-1 text-xs font-medium text-[var(--fg-muted)] hover:bg-[var(--bg)] hover:text-[var(--fg)]">
                      <svg class="h-3.5 w-3.5 shrink-0" fill="none" stroke="currentColor" stroke-width="1.75" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M16.862 4.487l1.687-1.688a1.875 1.875 0 112.652 2.652L10.582 16.07a4.5 4.5 0 01-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 011.13-1.897l8.932-8.931zm0 0L19.5 7.125M18 14v4.75A2.25 2.25 0 0115.75 21H5.25A2.25 2.25 0 013 18.75V8.25A2.25 2.25 0 015.25 6H10"/></svg>
                      Edit
                    </button>
                    <button onclick={() => deactivate(subj.id)} disabled={$updateMut.isPending}
                      class="inline-flex items-center gap-1 rounded-lg px-2 py-1 text-xs font-medium text-red-500 hover:bg-red-50 hover:text-red-600 dark:hover:bg-red-950/40 disabled:opacity-40">
                      <svg class="h-3.5 w-3.5 shrink-0" fill="none" stroke="currentColor" stroke-width="1.75" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M14.74 9l-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 01-2.244 2.077H8.084a2.25 2.25 0 01-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 00-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 013.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 00-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 00-7.5 0"/></svg>
                      Remove
                    </button>
                  </div>
                </td>
              </tr>
            {/if}
          {/each}
        </tbody>
      </table>
    </div>
  {/if}
</div>
