<script lang="ts">
  import { createQuery, createMutation, useQueryClient } from '@tanstack/svelte-query';
  import {
    listStaffPermissions, setStaffPermission, clearStaffPermission,
    type StaffPermission,
  } from '$lib/api/staff';
  import { toast } from '$lib/stores/toast';
  import { apiError } from '$lib/utils';

  interface Props { staffId: string; }
  let { staffId }: Props = $props();

  const qc = useQueryClient();

  const query = createQuery({
    queryKey: ['staff', staffId, 'permissions'],
    queryFn:  () => listStaffPermissions(staffId),
    staleTime: 60_000,
  });

  const setMut = createMutation({
    mutationFn: ({ module, action, is_allowed }: { module: string; action: string; is_allowed: boolean }) =>
      setStaffPermission(staffId, module, action, is_allowed),
    onSuccess: (data) => {
      qc.setQueryData(['staff', staffId, 'permissions'], data);
      toast.success('Permission updated.');
    },
    onError: (e) => toast.error(apiError(e, 'Could not update permission.')),
  });

  const clearMut = createMutation({
    mutationFn: ({ module, action }: { module: string; action: string }) =>
      clearStaffPermission(staffId, module, action),
    onSuccess: (data) => {
      qc.setQueryData(['staff', staffId, 'permissions'], data);
      toast.success('Override removed — reverted to position default.');
    },
    onError: (e) => toast.error(apiError(e, 'Could not remove override.')),
  });

  const isBusy = $derived($setMut.isPending || $clearMut.isPending);

  // Group permissions by module, preserving catalogue order
  const grouped = $derived.by(() => {
    const perms: StaffPermission[] = $query.data ?? [];
    const map = new Map<string, StaffPermission[]>();
    for (const p of perms) {
      if (!map.has(p.module)) map.set(p.module, []);
      map.get(p.module)!.push(p);
    }
    return [...map.entries()];
  });

  const ACTION_LABEL: Record<string, string> = {
    view: 'View', edit: 'Edit', create: 'Create', delete: 'Delete',
    manage_users: 'Manage Users', record: 'Record', approve: 'Approve',
    enter_scores: 'Enter Scores', approve_scores: 'Approve Scores',
    collect: 'Collect', manage: 'Manage', assign: 'Assign', generate: 'Generate',
  };

  const MODULE_LABEL: Record<string, string> = {
    school: 'School', staff: 'Staff', students: 'Students',
    academic: 'Academic', attendance: 'Attendance', assessments: 'Assessments',
    fees: 'Fees', housing: 'Housing', reports: 'Reports',
  };
</script>

{#if $query.isPending}
  <div class="space-y-3">
    {#each Array(3) as _}<div class="skeleton h-24 rounded-xl"></div>{/each}
  </div>

{:else if $query.isError}
  <div class="rounded-xl border border-red-100 dark:border-red-900 bg-red-50 dark:bg-red-950/40
              p-4 text-sm text-red-600 dark:text-red-400">
    Could not load permissions.
    <button onclick={() => $query.refetch()} class="ml-2 underline">Retry</button>
  </div>

{:else}
  <div class="mb-4 rounded-xl border border-amber-200 dark:border-amber-800
              bg-amber-50 dark:bg-amber-950/30 px-4 py-3 text-xs text-amber-700 dark:text-amber-300">
    <strong>Personal overrides</strong> beat position defaults. Only set overrides when a position
    assignment isn't the right tool — for example, to grant a subject teacher access to one
    extra module for a term.
  </div>

  <div class="space-y-4">
    {#each grouped as [module, actions]}
      <div class="overflow-hidden rounded-xl border border-[var(--border)] bg-[var(--card)]">
        <!-- Module header -->
        <div class="border-b border-[var(--border)] bg-[var(--hover)] px-4 py-2.5">
          <p class="text-xs font-bold uppercase tracking-widest text-[var(--fg-muted)]">
            {MODULE_LABEL[module] ?? module}
          </p>
        </div>

        <!-- Permission rows -->
        <div class="divide-y divide-[var(--border)]">
          {#each actions as perm (perm.module + '.' + perm.action)}
            {@const key = `${perm.module}.${perm.action}`}
            {@const isSettingThis = ($setMut.isPending  && ($setMut.variables as {module:string;action:string}).module === perm.module && ($setMut.variables as {module:string;action:string}).action === perm.action)
                                 || ($clearMut.isPending && ($clearMut.variables as {module:string;action:string}).module === perm.module && ($clearMut.variables as {module:string;action:string}).action === perm.action)}
            <div class="flex flex-wrap items-center gap-x-4 gap-y-2 px-4 py-3
                        {isSettingThis ? 'opacity-60' : ''}">

              <!-- Permission name -->
              <div class="min-w-0 flex-1 basis-40">
                <p class="text-sm font-medium text-[var(--fg)]">
                  {ACTION_LABEL[perm.action] ?? perm.action}
                </p>
                <p class="mt-0.5 font-mono text-[10px] text-[var(--fg-subtle)]">{key}</p>
              </div>

              <!-- Source badge -->
              {#if perm.source === 'override'}
                <span class="rounded-full bg-amber-100 dark:bg-amber-900/40 px-2 py-0.5
                             text-[10px] font-semibold text-amber-700 dark:text-amber-300">
                  Override
                </span>
              {:else if perm.source === 'position'}
                <span class="rounded-full bg-blue-50 dark:bg-blue-950/30 px-2 py-0.5
                             text-[10px] font-semibold text-blue-600 dark:text-blue-400">
                  Position
                </span>
              {:else}
                <span class="rounded-full bg-[var(--hover)] px-2 py-0.5
                             text-[10px] font-semibold text-[var(--fg-subtle)]">
                  Default: denied
                </span>
              {/if}

              <!-- Effective value -->
              {#if perm.effective}
                <span class="flex items-center gap-1 text-xs font-semibold text-emerald-600 dark:text-emerald-400">
                  <svg class="h-3.5 w-3.5" fill="none" stroke="currentColor" stroke-width="3" viewBox="0 0 24 24">
                    <polyline points="20 6 9 17 4 12"/>
                  </svg>
                  Granted
                </span>
              {:else}
                <span class="flex items-center gap-1 text-xs font-semibold text-[var(--fg-subtle)]">
                  <svg class="h-3.5 w-3.5" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12"/>
                  </svg>
                  Denied
                </span>
              {/if}

              <!-- Actions -->
              <div class="ml-auto flex shrink-0 flex-wrap items-center gap-1.5">
                {#if perm.source === 'override'}
                  <!-- Flip the override -->
                  <button
                    onclick={() => $setMut.mutate({ module: perm.module, action: perm.action, is_allowed: !perm.override_is_allowed })}
                    disabled={isBusy}
                    class="min-h-[44px] rounded-lg border border-[var(--border)] px-2.5 text-xs
                           font-medium text-[var(--fg-muted)] transition hover:bg-[var(--hover)]
                           hover:text-[var(--fg)] disabled:opacity-40">
                    {perm.effective ? 'Deny' : 'Grant'}
                  </button>
                  <!-- Remove override -->
                  <button
                    onclick={() => $clearMut.mutate({ module: perm.module, action: perm.action })}
                    disabled={isBusy}
                    aria-label="Remove override — revert to position default"
                    title="Remove override — revert to position default"
                    class="min-h-[44px] rounded-lg border border-[var(--border)] px-2.5 text-xs
                           font-medium text-red-500 transition hover:bg-red-50
                           dark:hover:bg-red-950/30 disabled:opacity-40">
                    × Clear
                  </button>
                {:else}
                  <!-- Add an override -->
                  <button
                    onclick={() => $setMut.mutate({ module: perm.module, action: perm.action, is_allowed: !perm.effective })}
                    disabled={isBusy}
                    class="min-h-[44px] rounded-lg border border-[var(--border)] px-2.5 text-xs
                           font-medium text-[var(--fg-muted)] transition hover:bg-[var(--hover)]
                           hover:text-[var(--fg)] disabled:opacity-40">
                    {perm.effective ? 'Override: Deny' : 'Override: Grant'}
                  </button>
                {/if}
              </div>

            </div>
          {/each}
        </div>
      </div>
    {/each}
  </div>
{/if}
