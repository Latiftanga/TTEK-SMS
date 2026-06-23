<script lang="ts">
  import { createQuery, createMutation, useQueryClient } from '@tanstack/svelte-query';
  import {
    listPositionsWithPerms, updatePositionPermissions, grantedSet,
    PERMISSION_MATRIX, MODULE_LABELS, ACTION_LABELS,
    type PositionWithPerms,
  } from '$lib/api/permissions';
  import { toast } from '$lib/stores/toast';

  const qc = useQueryClient();
  const posQ = createQuery({ queryKey: ['positions-perms'], queryFn: listPositionsWithPerms, staleTime: 60_000 });
  const positions = $derived<PositionWithPerms[]>($posQ.data ?? []);

  // Local editable state: Map<positionId, Set<"module.action">>
  let dirty = $state<Map<string, Set<string>>>(new Map());
  let saving = $state<string | null>(null); // positionId currently saving

  // When positions load, initialise local state from server data
  $effect(() => {
    if ($posQ.data) {
      const m = new Map<string, Set<string>>();
      for (const pos of $posQ.data) {
        m.set(pos.id, grantedSet(pos));
      }
      dirty = m;
    }
  });

  function toggle(posId: string, module: string, action: string) {
    const set = dirty.get(posId);
    if (!set) return;
    const key = `${module}.${action}`;
    if (set.has(key)) set.delete(key); else set.add(key);
    dirty = new Map(dirty); // trigger reactivity
  }

  function isGranted(posId: string, module: string, action: string) {
    return dirty.get(posId)?.has(`${module}.${action}`) ?? false;
  }

  const saveMut = createMutation({
    mutationFn: ({ posId, perms }: { posId: string; perms: { module: string; action: string; is_allowed: boolean }[] }) =>
      updatePositionPermissions(posId, perms),
    onSuccess: (updated) => {
      qc.setQueryData(['positions-perms'], (old: PositionWithPerms[] | undefined) =>
        old?.map(p => p.id === updated.id ? updated : p) ?? [updated]
      );
      toast.success('Permissions saved.');
      saving = null;
    },
    onError: (e: unknown) => {
      toast.error((e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? 'Save failed.');
      saving = null;
    },
  });

  function save(pos: PositionWithPerms) {
    saving = pos.id;
    const granted = dirty.get(pos.id) ?? new Set();
    const perms: { module: string; action: string; is_allowed: boolean }[] = [];
    for (const [module, actions] of Object.entries(PERMISSION_MATRIX)) {
      for (const action of actions) {
        perms.push({ module, action, is_allowed: granted.has(`${module}.${action}`) });
      }
    }
    $saveMut.mutate({ posId: pos.id, perms });
  }

  function hasChanges(pos: PositionWithPerms): boolean {
    const original = grantedSet(pos);
    const current = dirty.get(pos.id) ?? new Set();
    if (original.size !== current.size) return true;
    for (const k of original) if (!current.has(k)) return true;
    return false;
  }

  // Scroll: active column highlight
  let activePos = $state<string | null>(null);
</script>

<svelte:head><title>Permissions</title></svelte:head>

<div class="space-y-4">
  <div class="flex items-center justify-between">
    <div>
      <h1 class="text-xl font-bold text-[var(--fg)]">Role Permissions</h1>
      <p class="mt-0.5 text-sm text-[var(--fg-muted)]">
        Toggle permissions per position. Changes take effect immediately after saving.
      </p>
    </div>
  </div>

  {#if $posQ.isPending}
    <div class="space-y-2">
      {#each [0,1,2,3] as _}
        <div class="h-10 animate-pulse rounded-xl bg-[var(--card)]"></div>
      {/each}
    </div>

  {:else if $posQ.isError}
    <div class="rounded-2xl border border-red-200 bg-red-50 p-6 text-center text-sm text-red-600 dark:border-red-900 dark:bg-red-950/30 dark:text-red-400">
      Failed to load permissions. You may not have access to this page.
    </div>

  {:else}
    <!-- Scrollable matrix -->
    <div class="overflow-x-auto rounded-2xl border border-[var(--border)] bg-[var(--card)]">
      <table class="w-full min-w-max text-sm">
        <thead>
          <tr class="border-b border-[var(--border)]">
            <th class="sticky left-0 z-10 bg-[var(--card)] px-4 py-3 text-left text-xs font-semibold
                       uppercase tracking-widest text-[var(--fg-subtle)] min-w-[160px]">
              Permission
            </th>
            {#each positions as pos}
              <th class="px-3 py-3 text-center min-w-[110px]
                         {activePos === pos.id ? 'bg-[color-mix(in_oklab,var(--brand)_6%,transparent)]' : ''}">
                <div class="flex flex-col items-center gap-1">
                  <span class="text-xs font-semibold text-[var(--fg)] leading-tight">{pos.name}</span>
                  {#if pos.is_template}
                    <span class="rounded-full bg-[var(--hover)] px-1.5 py-0.5 text-[9px]
                                 font-semibold uppercase tracking-wide text-[var(--fg-subtle)]">
                      Platform
                    </span>
                  {/if}
                </div>
              </th>
            {/each}
          </tr>
        </thead>

        <tbody>
          {#each Object.entries(PERMISSION_MATRIX) as [module, actions]}
            <!-- Module header row -->
            <tr class="border-t border-[var(--border)] bg-[var(--hover)]/50">
              <td colspan={positions.length + 1}
                  class="sticky left-0 px-4 py-1.5 text-[10px] font-bold uppercase tracking-widest text-[var(--fg-subtle)]">
                {MODULE_LABELS[module]}
              </td>
            </tr>

            {#each actions as action}
              {@const key = `${module}.${action}`}
              <tr class="border-t border-[var(--border)]/50 transition hover:bg-[var(--hover)]/40">
                <td class="sticky left-0 z-10 bg-[var(--card)] px-4 py-2.5 text-sm text-[var(--fg-muted)]
                           hover:bg-[var(--hover)]/40">
                  {ACTION_LABELS[action] ?? action}
                </td>

                {#each positions as pos}
                  <td class="px-3 py-2.5 text-center
                             {activePos === pos.id ? 'bg-[color-mix(in_oklab,var(--brand)_6%,transparent)]' : ''}">
                    <input
                      type="checkbox"
                      checked={isGranted(pos.id, module, action)}
                      onchange={() => toggle(pos.id, module, action)}
                      onfocus={() => activePos = pos.id}
                      onblur={() => activePos = null}
                      class="h-4 w-4 cursor-pointer rounded accent-[var(--brand)]"
                    />
                  </td>
                {/each}
              </tr>
            {/each}
          {/each}
        </tbody>

        <!-- Save row -->
        <tfoot>
          <tr class="border-t-2 border-[var(--border)] bg-[var(--hover)]/30">
            <td class="sticky left-0 z-10 bg-[var(--card)] px-4 py-3 text-xs text-[var(--fg-subtle)]">
              Save changes
            </td>
            {#each positions as pos}
              <td class="px-3 py-3 text-center">
                <button
                  onclick={() => save(pos)}
                  disabled={!hasChanges(pos) || saving === pos.id}
                  class="rounded-lg px-3 py-1.5 text-xs font-semibold transition
                         {hasChanges(pos)
                           ? 'bg-[var(--brand)] text-white hover:opacity-90'
                           : 'bg-[var(--hover)] text-[var(--fg-subtle)] cursor-not-allowed'}
                         disabled:opacity-60">
                  {saving === pos.id ? '…' : 'Save'}
                </button>
              </td>
            {/each}
          </tr>
        </tfoot>
      </table>
    </div>

    <p class="text-xs text-[var(--fg-subtle)]">
      "Platform" positions are shared across all schools. Changes apply to all schools using that position.
      Per-staff overrides set individually on a staff member's profile always take priority.
    </p>
  {/if}
</div>
