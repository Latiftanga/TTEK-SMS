<script lang="ts">
  import { createMutation, useQueryClient } from '@tanstack/svelte-query';
  import { reactiveQuery } from '$lib/query.svelte';
  import { listCatalogue, createSubject, type CatalogueEntry, type Subject } from '$lib/api/academic';
  import { apiError } from '$lib/utils';

  interface Props {
    schoolType: string;
    existingSubjects: Subject[];
    onDone: () => void;
    onClose: () => void;
  }
  const { schoolType, existingSubjects, onDone, onClose }: Props = $props();

  const qc = useQueryClient();
  const level = $derived(schoolType === 'SHS' ? 'SHS' : 'BASIC');

  let mode = $state<'catalogue' | 'custom'>('catalogue');

  // ── Catalogue mode ────────────────────────────────────────────────────────────
  const catalogueQ = reactiveQuery(() => ({
    queryKey: ['subject-catalogue', level] as const,
    queryFn: () => listCatalogue(level as 'BASIC' | 'SHS'),
    staleTime: 10 * 60_000,
  }));

  const adoptedCatalogueIds = $derived(
    new Set(existingSubjects.map(s => s.catalogue_id).filter((id): id is string => !!id))
  );

  let search       = $state('');
  let typeFilter   = $state<'ALL' | 'CORE' | 'ELECTIVE'>('ALL');
  let selected     = $state<Set<string>>(new Set());

  const available = $derived(
    ($catalogueQ.data ?? [])
      .filter(c => c.is_active && !adoptedCatalogueIds.has(c.id))
      .filter(c => typeFilter === 'ALL' || c.subject_type === typeFilter)
      .filter(c => {
        const q = search.trim().toLowerCase();
        return !q || c.name.toLowerCase().includes(q) || c.code.toLowerCase().includes(q);
      })
      .sort((a, b) => a.name.localeCompare(b.name))
  );

  function toggle(id: string) {
    const next = new Set(selected);
    next.has(id) ? next.delete(id) : next.add(id);
    selected = next;
  }

  let addError = $state('');

  const adoptMut = createMutation({
    mutationFn: async (entries: CatalogueEntry[]) => {
      const results = await Promise.allSettled(
        entries.map(e => createSubject({ code: e.code, name: e.name, catalogue_id: e.id }))
      );
      const failed = results.filter((r): r is PromiseRejectedResult => r.status === 'rejected');
      return { addedCount: results.length - failed.length, failed };
    },
    onSuccess: ({ addedCount, failed }) => {
      qc.invalidateQueries({ queryKey: ['subjects'] });
      selected = new Set();
      if (failed.length === 0) {
        onDone();
      } else {
        addError = `Added ${addedCount} of ${addedCount + failed.length}. ` +
          `${failed.length} failed: ${apiError(failed[0].reason, 'unknown error')}`;
      }
    },
    onError: (e: unknown) => { addError = apiError(e, 'Failed to add subjects.'); },
  });

  function submitAdopt() {
    addError = '';
    const entries = available.filter(c => selected.has(c.id));
    if (entries.length === 0) { addError = 'Select at least one subject.'; return; }
    $adoptMut.mutate(entries);
  }

  // ── Custom mode ───────────────────────────────────────────────────────────────
  let customForm  = $state({ code: '', name: '' });
  let customError = $state('');

  const customMut = createMutation({
    mutationFn: createSubject,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['subjects'] });
      customForm = { code: '', name: '' };
      onDone();
    },
    onError: (e: unknown) => { customError = apiError(e, 'Failed to create subject.'); },
  });

  function submitCustom() {
    customError = '';
    if (!customForm.code.trim() || !customForm.name.trim()) { customError = 'Code and name are required.'; return; }
    $customMut.mutate({ code: customForm.code.toUpperCase(), name: customForm.name });
  }

  const PILL = (active: boolean) => `rounded-lg px-3 py-1.5 text-xs font-semibold transition ${active ? 'text-white' : 'border border-[var(--border)] text-[var(--fg-muted)] hover:bg-[var(--hover)]'}`;
</script>

<div class="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
  <div class="mb-4 flex items-center justify-between">
    <div class="flex gap-2">
      <button onclick={() => mode = 'catalogue'} class={PILL(mode === 'catalogue')} style={mode === 'catalogue' ? 'background-color: var(--brand)' : ''}>
        From catalogue
      </button>
      <button onclick={() => mode = 'custom'} class={PILL(mode === 'custom')} style={mode === 'custom' ? 'background-color: var(--brand)' : ''}>
        Custom subject
      </button>
    </div>
    <button onclick={onClose} class="text-xs text-[var(--fg-muted)] hover:text-[var(--fg)]">Cancel</button>
  </div>

  {#if mode === 'catalogue'}
    <div class="space-y-3">
      <div class="flex flex-wrap items-center gap-2">
        <div class="relative flex-1 min-w-[180px]">
          <svg class="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-[var(--fg-muted)]" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M21 21l-4.35-4.35M17 11A6 6 0 111 11a6 6 0 0116 0z"/></svg>
          <input bind:value={search} type="search" placeholder="Search the {level} catalogue…"
            class="h-9 w-full rounded-xl border border-[var(--border)] bg-[var(--bg)] pl-9 pr-3 text-sm text-[var(--fg)] placeholder:text-[var(--fg-muted)] focus:border-[var(--brand)] focus:outline-none" />
        </div>
        <div class="flex rounded-lg border border-[var(--border)] bg-[var(--bg)] p-0.5">
          {#each [['ALL','All'],['CORE','Core'],['ELECTIVE','Elective']] as [v, l]}
            <button onclick={() => typeFilter = v as 'ALL' | 'CORE' | 'ELECTIVE'}
              class="rounded-md px-3 py-1 text-xs font-medium transition {typeFilter === v ? 'bg-[var(--card)] text-[var(--fg)] shadow-sm' : 'text-[var(--fg-muted)] hover:text-[var(--fg)]'}">
              {l}
            </button>
          {/each}
        </div>
      </div>

      {#if $catalogueQ.isPending}
        <div class="space-y-1.5">{#each [1,2,3,4] as _}<div class="h-8 animate-pulse rounded-lg bg-[var(--bg)]"></div>{/each}</div>
      {:else if available.length === 0}
        <p class="rounded-xl border border-dashed border-[var(--border)] px-4 py-6 text-center text-sm text-[var(--fg-muted)]">
          {($catalogueQ.data ?? []).length === 0
            ? `No ${level} subjects in the catalogue yet.`
            : 'No matching subjects — everything else is already added, or try a different search.'}
        </p>
      {:else}
        <div class="max-h-72 overflow-y-auto rounded-xl border border-[var(--border)]">
          {#each available as c (c.id)}
            <label class="flex cursor-pointer items-center gap-3 border-b border-[var(--border)] px-3 py-2 last:border-0 hover:bg-[var(--hover)]">
              <input type="checkbox" checked={selected.has(c.id)} onchange={() => toggle(c.id)}
                class="h-4 w-4 rounded border-[var(--border)] accent-[var(--brand)]" />
              <span class="min-w-0 flex-1 truncate text-sm text-[var(--fg)]">{c.name}</span>
              <span class="font-mono text-[10px] text-[var(--fg-subtle)]">{c.code}</span>
              <span class="rounded-full px-2 py-0.5 text-[9px] font-bold uppercase tracking-wide {c.subject_type === 'CORE' ? 'bg-blue-50 text-blue-700 dark:bg-blue-950/30 dark:text-blue-400' : 'bg-amber-50 text-amber-700 dark:bg-amber-950/30 dark:text-amber-400'}">
                {c.subject_type}
              </span>
            </label>
          {/each}
        </div>
      {/if}

      {#if addError}<p class="text-xs text-red-500">{addError}</p>{/if}
      <div class="flex items-center gap-2">
        <button onclick={submitAdopt} disabled={$adoptMut.isPending || selected.size === 0}
          class="rounded-xl px-4 py-2 text-sm font-semibold text-white transition hover:opacity-90 disabled:opacity-50" style="background-color: var(--brand)">
          {$adoptMut.isPending ? 'Adding…' : selected.size > 0 ? `Add ${selected.size} subject${selected.size !== 1 ? 's' : ''}` : 'Add selected'}
        </button>
        {#if selected.size > 0}
          <span class="text-xs text-[var(--fg-muted)]">{selected.size} selected</span>
        {/if}
      </div>
    </div>
  {:else}
    <div class="space-y-3">
      <p class="text-xs text-[var(--fg-muted)]">Not in the {level} catalogue? Add it as a custom subject for this school.</p>
      <div class="grid gap-3 sm:grid-cols-2">
        <div>
          <label class="mb-1 block text-xs font-medium text-[var(--fg-muted)]">Code</label>
          <input bind:value={customForm.code} placeholder="e.g. MATH" class="w-full rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--fg)] placeholder:text-[var(--fg-muted)] focus:border-[var(--brand)] focus:outline-none" />
        </div>
        <div>
          <label class="mb-1 block text-xs font-medium text-[var(--fg-muted)]">Name</label>
          <input bind:value={customForm.name} placeholder="e.g. Mathematics" class="w-full rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--fg)] placeholder:text-[var(--fg-muted)] focus:border-[var(--brand)] focus:outline-none" />
        </div>
      </div>
      {#if customError}<p class="text-xs text-red-500">{customError}</p>{/if}
      <button onclick={submitCustom} disabled={$customMut.isPending}
        class="rounded-xl px-4 py-2 text-sm font-semibold text-white transition hover:opacity-90 disabled:opacity-50" style="background-color: var(--brand)">
        {$customMut.isPending ? 'Creating…' : 'Create subject'}
      </button>
    </div>
  {/if}
</div>
