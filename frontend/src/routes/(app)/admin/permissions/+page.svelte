<script lang="ts">
  import { createQuery, createMutation, useQueryClient } from '@tanstack/svelte-query';
  import {
    listPositionsWithPerms, updatePositionPermissions, grantedSet,
    PERMISSION_MATRIX, MODULE_LABELS, ACTION_LABELS,
    type PositionWithPerms,
  } from '$lib/api/permissions';
  import { toast } from '$lib/stores/toast';
  import PageHeader from '$lib/components/PageHeader.svelte';
  import { setPageTitle } from '$lib/stores/title';
  setPageTitle('Roles & Permissions');

  const qc = useQueryClient();
  const posQ = createQuery({ queryKey: ['positions-perms'], queryFn: listPositionsWithPerms, staleTime: 60_000 });
  const positions = $derived<PositionWithPerms[]>($posQ.data ?? []);

  let dirty = $state<Map<string, Set<string>>>(new Map());
  let saving = $state(false);
  let selectedId = $state<string | null>(null);

  const selected = $derived(positions.find(p => p.id === selectedId) ?? positions[0] ?? null);

  $effect(() => {
    if ($posQ.data) {
      const m = new Map<string, Set<string>>();
      for (const pos of $posQ.data) m.set(pos.id, grantedSet(pos));
      dirty = m;
      if (!selectedId && $posQ.data.length) selectedId = $posQ.data[0].id;
    }
  });

  function toggle(posId: string, module: string, action: string) {
    const set = dirty.get(posId);
    if (!set) return;
    const key = `${module}.${action}`;
    if (set.has(key)) set.delete(key); else set.add(key);
    dirty = new Map(dirty);
  }

  function isGranted(posId: string, module: string, action: string) {
    return dirty.get(posId)?.has(`${module}.${action}`) ?? false;
  }

  function hasChanges(pos: PositionWithPerms): boolean {
    const original = grantedSet(pos);
    const current = dirty.get(pos.id) ?? new Set();
    if (original.size !== current.size) return true;
    for (const k of original) if (!current.has(k)) return true;
    return false;
  }

  function grantCount(pos: PositionWithPerms) {
    return dirty.get(pos.id)?.size ?? 0;
  }

  const saveMut = createMutation({
    mutationFn: ({ posId, perms }: { posId: string; perms: { module: string; action: string; is_allowed: boolean }[] }) =>
      updatePositionPermissions(posId, perms),
    onSuccess: (updated) => {
      qc.setQueryData(['positions-perms'], (old: PositionWithPerms[] | undefined) =>
        old?.map(p => p.id === updated.id ? updated : p) ?? [updated]
      );
      toast.success('Permissions saved.');
      saving = false;
    },
    onError: (e: unknown) => {
      toast.error((e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? 'Save failed.');
      saving = false;
    },
  });

  function save() {
    if (!selected) return;
    saving = true;
    const granted = dirty.get(selected.id) ?? new Set();
    const perms = Object.entries(PERMISSION_MATRIX).flatMap(([module, actions]) =>
      actions.map(action => ({ module, action, is_allowed: granted.has(`${module}.${action}`) }))
    );
    $saveMut.mutate({ posId: selected.id, perms });
  }
</script>

<PageHeader title="Roles & Permissions" description="Default permissions granted by each role. A staff member's own Permissions tab can still override these for that one person." />

{#if $posQ.isPending}
  <div class="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
    {#each [0,1,2,3,4,5] as _}
      <div class="h-14 animate-pulse rounded-xl bg-[var(--hover)]"></div>
    {/each}
  </div>

{:else if $posQ.isError}
  <div class="rounded-2xl border border-red-200 bg-red-50 p-6 text-center text-sm text-red-600
              dark:border-red-900 dark:bg-red-950/30 dark:text-red-400">
    Failed to load permissions.
  </div>

{:else if selected}
  <div class="flex flex-col gap-4 lg:flex-row lg:items-start">

    <!-- Position selector -->
    <div class="lg:w-56 lg:shrink-0">
      <!-- Mobile: native select -->
      <div class="lg:hidden">
        <select bind:value={selectedId}
          class="w-full rounded-xl border border-[var(--border)] bg-[var(--card)] px-3 py-2.5
                 text-sm font-medium text-[var(--fg)] focus:border-[var(--brand)] focus:outline-none transition">
          {#each positions as pos}
            <option value={pos.id}>
              {pos.name}{hasChanges(pos) ? ' ●' : ''}{pos.is_template ? ' (Platform)' : ''}
            </option>
          {/each}
        </select>
        {#if hasChanges(selected)}
          <p class="mt-1.5 text-xs text-amber-600 dark:text-amber-400">Unsaved changes.</p>
        {/if}
      </div>

      <!-- Desktop: vertical list -->
      <div class="hidden lg:flex lg:flex-col lg:gap-1">
        {#each positions as pos}
          <button onclick={() => selectedId = pos.id}
            class="flex w-full items-center justify-between rounded-xl border px-3 py-2.5
                   text-left text-sm font-medium transition
                   {selectedId === pos.id
                     ? 'border-[var(--brand)] bg-[color-mix(in_oklab,var(--brand)_8%,transparent)] text-[var(--brand)]'
                     : 'border-transparent bg-[var(--card)] text-[var(--fg-muted)] hover:bg-[var(--hover)] hover:text-[var(--fg)]'}">
            <div class="min-w-0">
              <p class="truncate leading-snug">{pos.name}</p>
              {#if pos.is_template}
                <p class="text-[10px] font-normal text-[var(--fg-subtle)]">Platform</p>
              {/if}
            </div>
            <div class="ml-2 flex shrink-0 items-center gap-1.5">
              {#if hasChanges(pos)}<span class="h-1.5 w-1.5 rounded-full bg-amber-400"></span>{/if}
              <span class="text-[10px] text-[var(--fg-subtle)]">{grantCount(pos)}</span>
            </div>
          </button>
        {/each}
      </div>
    </div>

    <!-- Permission panel -->
    <div class="min-w-0 flex-1">
      <div class="rounded-2xl border border-[var(--border)] bg-[var(--card)]">
        <!-- Header -->
        <div class="flex items-center justify-between border-b border-[var(--border)] px-5 py-4">
          <div>
            <h3 class="font-semibold text-[var(--fg)]">{selected.name}</h3>
            <p class="text-xs text-[var(--fg-muted)]">
              {grantCount(selected)} permission{grantCount(selected) === 1 ? '' : 's'} granted
              {#if selected.is_template}· Platform role{/if}
            </p>
          </div>
          <button onclick={save} disabled={!hasChanges(selected) || saving}
            class="rounded-xl px-4 py-2 text-sm font-semibold transition
                   {hasChanges(selected)
                     ? 'bg-[var(--brand)] text-white hover:opacity-90'
                     : 'bg-[var(--hover)] text-[var(--fg-subtle)] cursor-not-allowed'}
                   disabled:opacity-60">
            {saving ? 'Saving…' : 'Save changes'}
          </button>
        </div>

        <!-- Module groups -->
        <div class="divide-y divide-[var(--border)]">
          {#each Object.entries(PERMISSION_MATRIX) as [module, actions]}
            <div class="px-5 py-4">
              <p class="mb-3 text-[11px] font-bold uppercase tracking-widest text-[var(--fg-subtle)]">
                {MODULE_LABELS[module]}
              </p>
              <div class="grid grid-cols-1 gap-2 md:grid-cols-2 xl:grid-cols-3">
                {#each actions as action}
                  {@const granted = isGranted(selected.id, module, action)}
                  <label class="flex cursor-pointer items-center gap-3 rounded-xl border px-3 py-2.5
                                transition select-none
                                {granted
                                  ? 'border-[var(--brand)]/30 bg-[color-mix(in_oklab,var(--brand)_5%,transparent)]'
                                  : 'border-[var(--border)] hover:bg-[var(--hover)]'}">
                    <button role="switch" aria-checked={granted}
                      onclick={() => toggle(selected.id, module, action)}
                      class="relative h-5 w-9 shrink-0 rounded-full transition-colors duration-200
                             {granted ? 'bg-[var(--brand)]' : 'bg-[var(--border)]'}">
                      <span class="absolute top-0.5 left-0.5 h-4 w-4 rounded-full bg-white shadow
                                   transition-transform duration-200
                                   {granted ? 'translate-x-4' : 'translate-x-0'}"></span>
                    </button>
                    <div class="min-w-0">
                      <p class="text-sm font-medium leading-tight
                                {granted ? 'text-[var(--fg)]' : 'text-[var(--fg-muted)]'}">
                        {ACTION_LABELS[action] ?? action}
                      </p>
                      <p class="text-[10px] text-[var(--fg-subtle)]">{module}.{action}</p>
                    </div>
                  </label>
                {/each}
              </div>
            </div>
          {/each}
        </div>

        <!-- Sticky footer when dirty -->
        {#if hasChanges(selected)}
          <div class="sticky bottom-0 flex items-center justify-between rounded-b-2xl border-t
                      border-[var(--border)] bg-[var(--card)] px-5 py-3">
            <p class="text-xs text-amber-600 dark:text-amber-400">You have unsaved changes.</p>
            <button onclick={save} disabled={saving}
              class="rounded-xl bg-[var(--brand)] px-4 py-2 text-sm font-semibold text-white
                     transition hover:opacity-90 disabled:opacity-60">
              {saving ? 'Saving…' : 'Save changes'}
            </button>
          </div>
        {/if}
      </div>

      <p class="mt-2 text-xs text-[var(--fg-subtle)]">
        Per-staff overrides on a staff member's profile always take priority over these role defaults.
      </p>
    </div>
  </div>
{/if}
