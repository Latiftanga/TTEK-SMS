<script lang="ts">
  import { createQuery, createMutation, useQueryClient } from '@tanstack/svelte-query';
  import { listSubjects, updateSubject, listYears, type Subject } from '$lib/api/academic';
  import { sortTermsDesc, resolveDefaultTerm } from '$lib/academicPeriod';
  import Pagination from '$lib/components/Pagination.svelte';
  import EmptyState from '$lib/components/EmptyState.svelte';
  import ConfirmModal from '$lib/components/ConfirmModal.svelte';
  import AddSubjectPanel from './AddSubjectPanel.svelte';
  import SubjectSummaryPanel from './SubjectSummaryPanel.svelte';

  interface Props { schoolType: string; }
  const { schoolType }: Props = $props();

  let expandedSummaryId = $state<string | null>(null);

  const qc = useQueryClient();

  const subjectsQuery = createQuery({ queryKey: ['subjects'], queryFn: listSubjects, staleTime: 5 * 60_000 });

  // ── Term selector — powers SubjectSummaryPanel's read-only per-class counts ──
  const yearsQ = createQuery({ queryKey: ['academic-years'], queryFn: listYears, staleTime: 5 * 60_000 });
  const allTerms = $derived(
    sortTermsDesc(($yearsQ.data ?? []).flatMap(y => y.terms.map(t => ({ ...t, yearName: y.name }))))
  );
  let termId = $state('');
  $effect(() => {
    if (termId || allTerms.length === 0) return;
    termId = resolveDefaultTerm(allTerms)?.id ?? '';
  });

  // ── Filters ───────────────────────────────────────────────────────────────────
  let search       = $state('');
  let statusFilter = $state('active');
  let page         = $state(1);

  const all = $derived<Subject[]>($subjectsQuery.data ?? []);

  const filtered = $derived(
    all.filter(s => {
      const q = search.trim().toLowerCase();
      if (q && !s.name.toLowerCase().includes(q) && !s.code.toLowerCase().includes(q)) return false;
      if (statusFilter === 'active'   && !s.is_active) return false;
      if (statusFilter === 'inactive' &&  s.is_active) return false;
      return true;
    }).sort((a, b) => a.name.localeCompare(b.name))
  );

  $effect(() => { search; statusFilter; page = 1; });

  const PAGE  = 20;
  const paged = $derived(filtered.slice((page - 1) * PAGE, page * PAGE));

  let confirmDeactivateSubj = $state<{ id: string; name: string } | null>(null);

  // ── Add subject (catalogue picker or custom) ──────────────────────────────────
  let showForm = $state(false);

  // ── Inline edit ───────────────────────────────────────────────────────────────
  let editingId = $state<string | null>(null);
  let editForm  = $state({ code: '', name: '' });
  let editError = $state('');

  const updateMut = createMutation({
    mutationFn: ({ id, req }: { id: string; req: { code?: string; name?: string; is_active?: boolean } }) => updateSubject(id, req),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['subjects'] }); editingId = null; editError = ''; },
    onError: (e: unknown) => { editError = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? 'Failed to update.'; },
  });

  function startEdit(s: Subject) { editingId = s.id; editForm = { code: s.code, name: s.name }; editError = ''; }

  function submitEdit() {
    editError = '';
    if (!editForm.code.trim() || !editForm.name.trim()) { editError = 'Code and name are required.'; return; }
    $updateMut.mutate({ id: editingId!, req: { code: editForm.code, name: editForm.name } });
  }

  const PILL = (active: boolean) => `rounded-md px-3 py-1 text-xs font-medium transition ${active ? 'bg-[var(--card)] text-[var(--fg)] shadow-sm' : 'text-[var(--fg-muted)] hover:text-[var(--fg)]'}`;
</script>

<div class="space-y-4">
  <!-- Toolbar -->
  <div class="flex flex-wrap items-center justify-between gap-3">
    <div class="flex flex-wrap items-center gap-2">
      <div class="relative">
        <svg class="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-[var(--fg-muted)]" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M21 21l-4.35-4.35M17 11A6 6 0 111 11a6 6 0 0116 0z"/></svg>
        <input bind:value={search} type="search" placeholder="Search subjects…"
          class="h-9 w-48 rounded-xl border border-[var(--border)] bg-[var(--card)] pl-9 pr-3 text-sm text-[var(--fg)] placeholder:text-[var(--fg-muted)] focus:border-[var(--brand)] focus:outline-none focus:ring-2 focus:ring-[var(--brand)]/20 sm:w-60" />
      </div>
      <div class="flex rounded-lg border border-[var(--border)] bg-[var(--bg)] p-0.5">
        {#each [['all','All'],['active','Active'],['inactive','Inactive']] as [v, l]}
          <button onclick={() => { statusFilter = v; page = 1; }} class={PILL(statusFilter === v)}>{l}</button>
        {/each}
      </div>
      <select bind:value={termId} class="h-9 rounded-xl border border-[var(--border)] bg-[var(--card)] px-2.5 text-xs text-[var(--fg)] focus:border-[var(--brand)] focus:outline-none">
        {#each allTerms as t (t.id)}
          <option value={t.id}>{t.yearName} — {t.name}{t.is_current ? ' (current)' : ''}</option>
        {/each}
      </select>
    </div>
    <button onclick={() => { showForm = !showForm; }}
      class="flex items-center gap-2 rounded-xl px-4 py-2 text-sm font-semibold text-white transition hover:opacity-90" style="background-color: var(--brand)">
      <svg class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M12 4v16m8-8H4"/></svg>
      Add subject
    </button>
  </div>

  {#if showForm}
    <AddSubjectPanel
      {schoolType}
      existingSubjects={all}
      onDone={() => { showForm = false; }}
      onClose={() => { showForm = false; }}
    />
  {/if}

  {#if $subjectsQuery.isPending}
    <div class="space-y-2">{#each [1,2,3,4,5] as _}<div class="skeleton h-12"></div>{/each}</div>
  {:else if all.length === 0}
    <EmptyState
      iconPath="M12 6.042A8.967 8.967 0 006 3.75c-1.052 0-2.062.18-3 .512v14.25A8.987 8.987 0 016 18c2.305 0 4.408.867 6 2.292m0-14.25a8.966 8.966 0 016-2.292c1.052 0 2.062.18 3 .512v14.25A8.987 8.987 0 0118 18a8.967 8.967 0 00-6 2.292m0-14.25v14.25"
      title="No subjects yet."
      description="Add your first subject to start assigning them to classes."
    />
  {:else if filtered.length === 0}
    <EmptyState
      iconPath="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z"
      title="No subjects match these filters."
      action={() => { search = ''; statusFilter = 'all'; }}
      actionLabel="Clear filters"
    />
  {:else}
    <div class="overflow-hidden rounded-xl border border-[var(--border)] bg-[var(--card)]">
      <table class="w-full text-sm">
        <thead>
          <tr class="border-b border-[var(--border)] text-left">
            <th class="px-4 py-2.5 text-xs font-semibold uppercase tracking-widest text-[var(--fg-muted)]">Code</th>
            <th class="px-4 py-2.5 text-xs font-semibold uppercase tracking-widest text-[var(--fg-muted)]">Name</th>
            <th class="hidden px-4 py-2.5 text-xs font-semibold uppercase tracking-widest text-[var(--fg-muted)] sm:table-cell">Status</th>
            <th class="px-4 py-2.5"></th>
          </tr>
        </thead>
        <tbody class="divide-y divide-[var(--border)]">
          {#each paged as subj (subj.id)}
            {#if editingId === subj.id}
              <tr class="bg-[var(--bg)]">
                <td class="px-3 py-2"><input bind:value={editForm.code} class="w-20 rounded-lg border border-[var(--border)] bg-[var(--card)] px-2 py-1 font-mono text-xs uppercase text-[var(--fg)] focus:border-[var(--brand)] focus:outline-none" /></td>
                <td class="px-3 py-2">
                  <input bind:value={editForm.name} class="w-full rounded-lg border border-[var(--border)] bg-[var(--card)] px-2 py-1 text-sm text-[var(--fg)] focus:border-[var(--brand)] focus:outline-none" />
                  {#if editError}<p class="mt-1 text-[11px] text-red-500">{editError}</p>{/if}
                </td>
                <td class="hidden px-4 py-2 sm:table-cell"></td>
                <td class="px-3 py-2 text-right">
                  <div class="flex items-center justify-end gap-1.5">
                    <button onclick={submitEdit} disabled={$updateMut.isPending} class="rounded-lg px-3 py-1.5 text-xs font-semibold text-white hover:opacity-90 disabled:opacity-50" style="background-color: var(--brand)">{$updateMut.isPending ? '…' : 'Save'}</button>
                    <button onclick={() => { editingId = null; editError = ''; }} class="rounded-lg border border-[var(--border)] px-3 py-1.5 text-xs font-medium text-[var(--fg-muted)] hover:bg-[var(--card)]">Cancel</button>
                  </div>
                </td>
              </tr>
            {:else}
              <tr class="transition hover:bg-[var(--bg)]">
                <td class="px-4 py-2.5 font-mono text-xs text-[var(--fg-muted)]">{subj.code}</td>
                <td class="px-4 py-2.5 font-medium text-[var(--fg)]">{subj.name}</td>
                <td class="hidden px-4 py-2.5 sm:table-cell"><span class="badge {subj.is_active ? 'badge-success' : 'badge-neutral'}">{subj.is_active ? 'Active' : 'Inactive'}</span></td>
                <td class="px-4 py-2.5 text-right">
                  <div class="flex items-center justify-end gap-1">
                    <button onclick={() => expandedSummaryId = expandedSummaryId === subj.id ? null : subj.id}
                      aria-label="Summary for {subj.name}"
                      class="inline-flex min-h-[44px] items-center gap-1 rounded-lg px-2 py-1 text-xs font-medium text-[var(--fg-muted)] hover:bg-[var(--bg)] hover:text-[var(--fg)]">
                      <svg class="h-3.5 w-3.5 shrink-0" fill="none" stroke="currentColor" stroke-width="1.75" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 013 19.875v-6.75zM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V8.625zM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V4.125z"/></svg>
                      Summary
                    </button>
                    <button onclick={() => startEdit(subj)} aria-label="Edit {subj.name}"
                      class="inline-flex min-h-[44px] items-center gap-1 rounded-lg px-2 py-1 text-xs font-medium text-[var(--fg-muted)] hover:bg-[var(--bg)] hover:text-[var(--fg)]">
                      <svg class="h-3.5 w-3.5 shrink-0" fill="none" stroke="currentColor" stroke-width="1.75" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M16.862 4.487l1.687-1.688a1.875 1.875 0 112.652 2.652L10.582 16.07a4.5 4.5 0 01-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 011.13-1.897l8.932-8.931zm0 0L19.5 7.125M18 14v4.75A2.25 2.25 0 0115.75 21H5.25A2.25 2.25 0 013 18.75V8.25A2.25 2.25 0 015.25 6H10"/></svg>
                      Edit
                    </button>
                    <button onclick={() => subj.is_active ? (confirmDeactivateSubj = { id: subj.id, name: subj.name }) : $updateMut.mutate({ id: subj.id, req: { is_active: true } })} disabled={$updateMut.isPending}
                      aria-label="{subj.is_active ? 'Deactivate' : 'Activate'} {subj.name}"
                      class="inline-flex min-h-[44px] items-center gap-1 rounded-lg px-2 py-1 text-xs font-medium disabled:opacity-40 {subj.is_active ? 'text-red-400 hover:bg-red-50 hover:text-red-500 dark:hover:bg-red-950/30' : 'text-green-500 hover:bg-green-50 hover:text-green-600 dark:hover:bg-green-950/30'}">
                      {#if subj.is_active}
                        <svg class="h-3.5 w-3.5 shrink-0" fill="none" stroke="currentColor" stroke-width="1.75" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M9.75 9.75l4.5 4.5m0-4.5l-4.5 4.5M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>
                        Deactivate
                      {:else}
                        <svg class="h-3.5 w-3.5 shrink-0" fill="none" stroke="currentColor" stroke-width="1.75" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>
                        Activate
                      {/if}
                    </button>
                  </div>
                </td>
              </tr>
              {#if expandedSummaryId === subj.id}
                <tr>
                  <td colspan="4" class="p-0">
                    <SubjectSummaryPanel subjectId={subj.id} {termId} />
                  </td>
                </tr>
              {/if}
            {/if}
          {/each}
        </tbody>
      </table>
    </div>
    <Pagination total={filtered.length} pageSize={PAGE} {page} label="subjects" onPageChange={(p) => page = p} />
  {/if}
</div>

<ConfirmModal
  open={!!confirmDeactivateSubj}
  title="Deactivate {confirmDeactivateSubj?.name ?? 'subject'}?"
  message="This subject will be hidden from new class assignments. You can reactivate it at any time."
  confirmLabel="Deactivate"
  variant="warning"
  isPending={$updateMut.isPending}
  onConfirm={() => { $updateMut.mutate({ id: confirmDeactivateSubj!.id, req: { is_active: false } }); confirmDeactivateSubj = null; }}
  onCancel={() => confirmDeactivateSubj = null}
/>
