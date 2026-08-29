<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import { get } from 'svelte/store';
  import { createQuery, createMutation, useQueryClient } from '@tanstack/svelte-query';
  import { currentUser } from '$lib/stores/auth';
  import { listHolidays, deleteHoliday, type HolidayRead } from '$lib/api/holidays';
  import ConfirmModal from '$lib/components/ConfirmModal.svelte';
  import HolidayForm from './HolidayForm.svelte';

  onMount(() => {
    const user = get(currentUser);
    if (!user) goto('/');
  });

  const qc = useQueryClient();
  const holidaysQuery = createQuery({ queryKey: ['holidays'], queryFn: listHolidays });

  let formOpen = $state(false);
  let editingHoliday = $state<HolidayRead | null>(null);
  function openCreate() { editingHoliday = null; formOpen = true; }
  function openEdit(h: HolidayRead) { editingHoliday = h; formOpen = true; }
  function onFormSuccess() { formOpen = false; editingHoliday = null; }

  let deleteTarget = $state<HolidayRead | null>(null);
  const deleteMut = createMutation({
    mutationFn: (h: HolidayRead) => deleteHoliday(h.id),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['holidays'] }); deleteTarget = null; },
  });

  const sorted = $derived(
    [...($holidaysQuery.data ?? [])].sort((a, b) => a.date.localeCompare(b.date)),
  );
</script>

<svelte:head><title>TTEK-SMS — Public Holidays</title></svelte:head>

<div class="min-h-screen bg-[var(--bg)] p-4 sm:p-8">
  <div class="mx-auto max-w-3xl">

    <div class="mb-6 flex flex-wrap items-center justify-between gap-3">
      <div>
        <a href="/superadmin" class="text-xs font-medium text-[var(--fg-muted)] hover:text-[var(--fg)]">← Platform Administration</a>
        <h1 class="mt-1 text-lg font-bold text-[var(--fg)]">Ghana Public Holidays</h1>
        <p class="text-xs text-[var(--fg-muted)]">Shared reference data every school's calendar generation reads from.</p>
      </div>
      <button onclick={openCreate}
        class="min-h-[44px] rounded-xl px-4 py-2 text-sm font-semibold text-white transition hover:opacity-90"
        style="background-color: var(--brand, #111827)">
        + Add holiday
      </button>
    </div>

    <div class="overflow-hidden rounded-2xl border border-[var(--border)] bg-[var(--card)]">
      {#if $holidaysQuery.isPending}
        <div class="space-y-2 p-4">{#each [1,2,3] as _}<div class="h-12 animate-pulse rounded-xl bg-[var(--hover)]"></div>{/each}</div>
      {:else if sorted.length === 0}
        <p class="px-6 py-14 text-center text-sm text-[var(--fg-muted)]">No holidays yet.</p>
      {:else}
        <div class="divide-y divide-[var(--border)]">
          {#each sorted as h (h.id)}
            <div class="flex items-center justify-between gap-3 px-5 py-3">
              <div class="min-w-0">
                <div class="flex items-center gap-2">
                  <p class="truncate text-sm font-medium text-[var(--fg)]">{h.name}</p>
                  {#if h.is_recurring}
                    <span class="rounded-full bg-emerald-100 px-2 py-0.5 text-[10px] font-semibold text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400">Recurring</span>
                  {:else}
                    <span class="rounded-full bg-amber-100 px-2 py-0.5 text-[10px] font-semibold text-amber-700 dark:bg-amber-900/30 dark:text-amber-400">One-off</span>
                  {/if}
                </div>
                <p class="text-xs text-[var(--fg-muted)]">{h.date}{h.description ? ` — ${h.description}` : ''}</p>
              </div>
              <div class="flex shrink-0 gap-1">
                <button onclick={() => openEdit(h)} aria-label="Edit {h.name}"
                  class="flex min-h-[44px] min-w-[44px] items-center justify-center rounded-lg text-[var(--fg-muted)]
                         transition hover:bg-[var(--hover)] hover:text-[var(--fg)]">
                  <svg class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"/>
                  </svg>
                </button>
                <button onclick={() => deleteTarget = h} aria-label="Delete {h.name}"
                  class="flex min-h-[44px] min-w-[44px] items-center justify-center rounded-lg text-[var(--fg-muted)]
                         transition hover:bg-red-50 hover:text-red-600 dark:hover:bg-red-900/20">
                  <svg class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/>
                  </svg>
                </button>
              </div>
            </div>
          {/each}
        </div>
      {/if}
    </div>

  </div>
</div>

<HolidayForm open={formOpen} holiday={editingHoliday} onSuccess={onFormSuccess}
  onCancel={() => { formOpen = false; editingHoliday = null; }} />

<ConfirmModal
  open={!!deleteTarget}
  title="Delete {deleteTarget?.name}?"
  message="Every school's future calendar generation will stop recognizing this date as a holiday. This cannot be undone."
  confirmLabel="Delete"
  variant="danger"
  isPending={$deleteMut.isPending}
  onConfirm={() => deleteTarget && $deleteMut.mutate(deleteTarget)}
  onCancel={() => deleteTarget = null}
/>
