<script lang="ts">
  import { createQuery, createMutation, useQueryClient } from '@tanstack/svelte-query';
  import { listProgrammeCatalogue, adoptProgramme, createProgramme, type Programme } from '$lib/api/academic';
  import { apiError } from '$lib/utils';

  interface Props {
    onDone: () => void;
    onClose: () => void;
  }
  const { onDone, onClose }: Props = $props();

  const qc = useQueryClient();
  let mode = $state<'catalogue' | 'custom'>('catalogue');

  // ── Catalogue mode ────────────────────────────────────────────────────────────
  const catalogueQ = createQuery({
    queryKey: ['programme-catalogue'],
    queryFn: listProgrammeCatalogue,
    staleTime: 10 * 60_000,
  });

  let search   = $state('');
  let selected = $state<Set<string>>(new Set());

  const available = $derived(
    ($catalogueQ.data ?? [])
      .filter(p => {
        const q = search.trim().toLowerCase();
        return !q || p.name.toLowerCase().includes(q) || p.code.toLowerCase().includes(q);
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
    mutationFn: async (entries: Programme[]) => {
      const results = await Promise.allSettled(entries.map(e => adoptProgramme(e.id)));
      const failed = results.filter((r): r is PromiseRejectedResult => r.status === 'rejected');
      return { addedCount: results.length - failed.length, failed };
    },
    onSuccess: ({ addedCount, failed }) => {
      qc.invalidateQueries({ queryKey: ['programmes'] });
      qc.invalidateQueries({ queryKey: ['programme-catalogue'] });
      selected = new Set();
      if (failed.length === 0) {
        onDone();
      } else {
        addError = `Added ${addedCount} of ${addedCount + failed.length}. ` +
          `${failed.length} failed: ${apiError(failed[0].reason, 'unknown error')}`;
      }
    },
    onError: (e: unknown) => { addError = apiError(e, 'Failed to add programmes.'); },
  });

  function submitAdopt() {
    addError = '';
    const entries = available.filter(p => selected.has(p.id));
    if (entries.length === 0) { addError = 'Select at least one programme.'; return; }
    $adoptMut.mutate(entries);
  }

  // ── Custom mode ───────────────────────────────────────────────────────────────
  let customForm  = $state({ code: '', name: '' });
  let customError = $state('');

  const customMut = createMutation({
    mutationFn: createProgramme,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['programmes'] });
      customForm = { code: '', name: '' };
      onDone();
    },
    onError: (e: unknown) => { customError = apiError(e, 'Failed to create programme.'); },
  });

  function submitCustom() {
    customError = '';
    if (!customForm.code.trim() || !customForm.name.trim()) { customError = 'Code and name are required.'; return; }
    $customMut.mutate({ code: customForm.code.trim().toUpperCase(), name: customForm.name.trim() });
  }

  const PILL = (active: boolean) => `rounded-lg px-3 py-1.5 text-xs font-semibold transition ${active ? 'text-white' : 'border border-[var(--border)] text-[var(--fg-muted)] hover:bg-[var(--hover)]'}`;
</script>

<div class="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
  <div class="mb-4 flex items-center justify-between">
    <div class="flex gap-2">
      <button onclick={() => mode = 'catalogue'} class={PILL(mode === 'catalogue')} style={mode === 'catalogue' ? 'background-color: var(--brand)' : ''}>
        System programmes
      </button>
      <button onclick={() => mode = 'custom'} class={PILL(mode === 'custom')} style={mode === 'custom' ? 'background-color: var(--brand)' : ''}>
        Custom programme
      </button>
    </div>
    <button onclick={onClose} class="text-xs text-[var(--fg-muted)] hover:text-[var(--fg)]">Cancel</button>
  </div>

  {#if mode === 'catalogue'}
    <div class="space-y-3">
      <p class="text-xs text-[var(--fg-muted)]">
        Which programmes this school runs depends on its own resources — nothing is offered until you adopt it here.
      </p>
      <div class="relative">
        <svg class="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-[var(--fg-muted)]" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M21 21l-4.35-4.35M17 11A6 6 0 111 11a6 6 0 0116 0z"/></svg>
        <input bind:value={search} type="search" placeholder="Search system programmes…"
          class="h-9 w-full rounded-xl border border-[var(--border)] bg-[var(--bg)] pl-9 pr-3 text-sm text-[var(--fg)] placeholder:text-[var(--fg-muted)] focus:border-[var(--brand)] focus:outline-none" />
      </div>

      {#if $catalogueQ.isPending}
        <div class="space-y-1.5">{#each [1,2,3] as _}<div class="h-8 animate-pulse rounded-lg bg-[var(--bg)]"></div>{/each}</div>
      {:else if available.length === 0}
        <p class="rounded-xl border border-dashed border-[var(--border)] px-4 py-6 text-center text-sm text-[var(--fg-muted)]">
          {($catalogueQ.data ?? []).length === 0
            ? 'This school already offers every system programme.'
            : 'No matching programmes.'}
        </p>
      {:else}
        <div class="max-h-60 overflow-y-auto rounded-xl border border-[var(--border)]">
          {#each available as p (p.id)}
            <label class="flex cursor-pointer items-center gap-3 border-b border-[var(--border)] px-3 py-2 last:border-0 hover:bg-[var(--hover)]">
              <input type="checkbox" checked={selected.has(p.id)} onchange={() => toggle(p.id)}
                class="h-4 w-4 rounded border-[var(--border)] accent-[var(--brand)]" />
              <span class="min-w-0 flex-1 truncate text-sm text-[var(--fg)]">{p.name}</span>
              <span class="font-mono text-[10px] text-[var(--fg-subtle)]">{p.code}</span>
            </label>
          {/each}
        </div>
      {/if}

      {#if addError}<p class="text-xs text-red-500">{addError}</p>{/if}
      <div class="flex items-center gap-2">
        <button onclick={submitAdopt} disabled={$adoptMut.isPending || selected.size === 0}
          class="rounded-xl px-4 py-2 text-sm font-semibold text-white transition hover:opacity-90 disabled:opacity-50" style="background-color: var(--brand)">
          {$adoptMut.isPending ? 'Adding…' : selected.size > 0 ? `Offer ${selected.size} programme${selected.size !== 1 ? 's' : ''}` : 'Offer selected'}
        </button>
        {#if selected.size > 0}
          <span class="text-xs text-[var(--fg-muted)]">{selected.size} selected</span>
        {/if}
      </div>
    </div>
  {:else}
    <div class="space-y-3">
      <p class="text-xs text-[var(--fg-muted)]">Not one of the system programmes? Add a custom one for this school.</p>
      <div class="grid gap-3 sm:grid-cols-2">
        <div>
          <label class="mb-1 block text-xs font-medium text-[var(--fg-muted)]">Code</label>
          <input bind:value={customForm.code} placeholder="e.g. SCI" class="w-full rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--fg)] placeholder:text-[var(--fg-muted)] focus:border-[var(--brand)] focus:outline-none" />
        </div>
        <div>
          <label class="mb-1 block text-xs font-medium text-[var(--fg-muted)]">Name</label>
          <input bind:value={customForm.name} placeholder="e.g. General Science" class="w-full rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--fg)] placeholder:text-[var(--fg-muted)] focus:border-[var(--brand)] focus:outline-none" />
        </div>
      </div>
      {#if customError}<p class="text-xs text-red-500">{customError}</p>{/if}
      <button onclick={submitCustom} disabled={$customMut.isPending}
        class="rounded-xl px-4 py-2 text-sm font-semibold text-white transition hover:opacity-90 disabled:opacity-50" style="background-color: var(--brand)">
        {$customMut.isPending ? 'Creating…' : 'Create programme'}
      </button>
    </div>
  {/if}
</div>
