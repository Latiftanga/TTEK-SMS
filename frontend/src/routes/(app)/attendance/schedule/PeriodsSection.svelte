<script lang="ts">
  import { createQuery, createMutation, useQueryClient } from '@tanstack/svelte-query';
  import {
    listPeriods, createPeriod, updatePeriod, deletePeriod, copyPeriods, type SchoolPeriod,
  } from '$lib/api/schoolPeriods';
  import { listSchedule, type DayOfWeek } from '$lib/api/attendance';
  import { apiError } from '$lib/utils';
  import { toast } from '$lib/stores/toast';
  import { portal } from '$lib/actions/portal';
  import ConfirmModal from '$lib/components/ConfirmModal.svelte';

  interface Props { selectedDay: DayOfWeek; }
  let { selectedDay = $bindable() }: Props = $props();

  const qc = useQueryClient();

  const DAYS: DayOfWeek[] = ['MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT', 'SUN'];
  const DAY_LABELS: Record<DayOfWeek, string> = {
    MON: 'Monday', TUE: 'Tuesday', WED: 'Wednesday',
    THU: 'Thursday', FRI: 'Friday', SAT: 'Saturday', SUN: 'Sunday',
  };

  const periodsQ  = createQuery({ queryKey: ['school-periods'], queryFn: listPeriods, staleTime: 60_000 });
  const scheduleQ = createQuery({ queryKey: ['schedule'], queryFn: listSchedule, staleTime: 5 * 60_000 });
  const dayPeriods = $derived(
    ($periodsQ.data ?? [])
      .filter(p => p.day_of_week === selectedDay)
      .sort((a, b) => a.period_number - b.period_number)
  );

  // Mirrors the backend's own is_school_day() fallback exactly (see
  // services/attendance_calendar.py::_school_days_set): a day is open if it
  // has an explicit is_school_day=true row; if the school has confirmed NO
  // day open at all yet, Mon–Fri is assumed open by default.
  const DEFAULT_OPEN_DAYS: Set<DayOfWeek> = new Set(['MON', 'TUE', 'WED', 'THU', 'FRI']);
  const openDays = $derived.by(() => {
    const configured = new Set(($scheduleQ.data ?? []).filter(s => s.is_school_day).map(s => s.day_of_week));
    return configured.size > 0 ? configured : DEFAULT_OPEN_DAYS;
  });
  const selectedDayClosed = $derived(!openDays.has(selectedDay));

  function invalidate() { qc.invalidateQueries({ queryKey: ['school-periods'] }); }

  // ── Add ───────────────────────────────────────────────────────────────────
  let showAdd = $state(false);
  let newName = $state('');
  let newNumber = $state('1');
  let newStart = $state('08:00');
  let newEnd = $state('08:45');

  const addMut = createMutation({
    mutationFn: () => createPeriod({
      name: newName.trim() || `Period ${newNumber}`,
      day_of_week: selectedDay,
      period_number: parseInt(newNumber, 10),
      start_time: newStart, end_time: newEnd,
    }),
    onSuccess: () => {
      invalidate();
      showAdd = false; newName = ''; newStart = '08:00'; newEnd = '08:45';
      newNumber = String((dayPeriods.at(-1)?.period_number ?? 0) + 2);
      toast.success('Period added.');
    },
    onError: (e) => toast.error(apiError(e, 'Could not add period.')),
  });

  // ── Edit ──────────────────────────────────────────────────────────────────
  let editingId = $state<string | null>(null);
  let editName  = $state('');
  let editStart = $state('');
  let editEnd   = $state('');

  function startEdit(p: SchoolPeriod) {
    editingId = p.id; editName = p.name;
    editStart = p.start_time.slice(0, 5); editEnd = p.end_time.slice(0, 5);
  }

  const editMut = createMutation({
    mutationFn: () => updatePeriod(editingId!, { name: editName.trim(), start_time: editStart, end_time: editEnd }),
    onSuccess: () => { invalidate(); editingId = null; toast.success('Period updated.'); },
    onError: (e) => toast.error(apiError(e, 'Could not update period.')),
  });

  // ── Delete ────────────────────────────────────────────────────────────────
  let confirmDeleteId = $state<string | null>(null);
  const deleteMut = createMutation({
    mutationFn: (id: string) => deletePeriod(id),
    onSuccess: () => { invalidate(); toast.success('Period removed.'); },
    onError: (e) => toast.error(apiError(e, 'Could not remove period.')),
  });

  // ── Copy to other days ───────────────────────────────────────────────────
  let showCopy = $state(false);
  let copyTargets = $state<Set<DayOfWeek>>(new Set());

  const copyMut = createMutation({
    mutationFn: () => copyPeriods({ source_day: selectedDay, target_days: [...copyTargets] }),
    onSuccess: (created) => {
      invalidate();
      showCopy = false; copyTargets = new Set();
      toast.success(created.length > 0 ? `${created.length} period(s) copied.` : 'Nothing new to copy — targets already match.');
    },
    onError: (e) => toast.error(apiError(e, 'Could not copy periods.')),
  });

  function toggleTarget(day: DayOfWeek) {
    const next = new Set(copyTargets);
    next.has(day) ? next.delete(day) : next.add(day);
    copyTargets = next;
  }
</script>

<div class="mt-8">
  <div class="mb-3 flex flex-wrap items-center justify-between gap-3">
    <div>
      <h2 class="text-sm font-semibold text-[var(--fg)]">Bell periods</h2>
      <p class="text-xs text-[var(--fg-muted)]">Named periods within a day — used for the class timetable and "what do I teach today" schedule.</p>
    </div>
    {#if dayPeriods.length > 0}
      <button onclick={() => showCopy = true}
        class="min-h-[44px] shrink-0 rounded-xl border border-[var(--border)] px-3 py-1.5 text-xs font-semibold text-[var(--fg-muted)] transition hover:bg-[var(--hover)]">
        Copy {DAY_LABELS[selectedDay]}'s periods to other days
      </button>
    {/if}
  </div>

  <div class="overflow-hidden rounded-2xl border border-[var(--border)] bg-[var(--card)]">
    {#if $periodsQ.isPending}
      <div class="p-4"><div class="h-10 animate-pulse rounded-lg bg-[var(--hover)]"></div></div>
    {:else if dayPeriods.length === 0}
      <p class="p-6 text-center text-sm text-[var(--fg-muted)]">No periods defined for {DAY_LABELS[selectedDay]} yet.</p>
    {:else}
      <div class="divide-y divide-[var(--border)]">
        {#each dayPeriods as p (p.id)}
          {#if editingId === p.id}
            <div class="space-y-2 p-3">
              <input bind:value={editName} class="sel w-full text-sm" placeholder="Name" />
              <div class="flex flex-wrap items-center gap-2">
                <input type="time" bind:value={editStart} class="sel text-sm" />
                <span class="text-xs text-[var(--fg-subtle)]">to</span>
                <input type="time" bind:value={editEnd} class="sel text-sm" />
                <button onclick={() => $editMut.mutate()} disabled={$editMut.isPending}
                  class="min-h-[44px] rounded-lg px-3 text-xs font-semibold text-white disabled:opacity-50" style="background:var(--brand)">Save</button>
                <button onclick={() => editingId = null}
                  class="min-h-[44px] rounded-lg border border-[var(--border)] px-3 text-xs text-[var(--fg-muted)]">Cancel</button>
              </div>
            </div>
          {:else}
            <div class="flex items-center gap-3 p-3">
              <span class="shrink-0 rounded-full bg-[var(--hover)] px-2 py-0.5 text-[10px] font-bold text-[var(--fg-subtle)]">#{p.period_number}</span>
              <div class="min-w-0 flex-1">
                <p class="truncate text-sm font-medium text-[var(--fg)]">{p.name}</p>
                <p class="text-xs text-[var(--fg-muted)]">{p.start_time.slice(0, 5)} – {p.end_time.slice(0, 5)}</p>
              </div>
              <button onclick={() => startEdit(p)}
                class="min-h-[44px] shrink-0 px-2 text-xs font-medium transition hover:underline" style="color:var(--brand)">Edit</button>
              <button onclick={() => confirmDeleteId = p.id}
                class="min-h-[44px] shrink-0 px-2 text-xs text-[var(--fg-subtle)] transition hover:text-red-500">Remove</button>
            </div>
          {/if}
        {/each}
      </div>
    {/if}

    <!-- Add form -->
    <div class="border-t border-[var(--border)] p-3">
      {#if selectedDayClosed}
        <p class="text-xs text-[var(--fg-subtle)]">
          {DAY_LABELS[selectedDay]} is closed — tap "Open this day" above before adding periods.
        </p>
      {:else if showAdd}
        <div class="space-y-2">
          <div class="flex items-center gap-2">
            <input bind:value={newName} placeholder="e.g. Period {newNumber}" class="sel min-w-0 flex-1 text-sm" />
            <input type="number" inputmode="numeric" min="1" bind:value={newNumber} class="sel w-16 shrink-0 text-sm" title="Period number" aria-label="Period number" />
          </div>
          <div class="flex flex-wrap items-center gap-2">
            <input type="time" bind:value={newStart} class="sel text-sm" />
            <span class="text-xs text-[var(--fg-subtle)]">to</span>
            <input type="time" bind:value={newEnd} class="sel text-sm" />
            <button onclick={() => $addMut.mutate()} disabled={$addMut.isPending}
              class="min-h-[44px] rounded-lg px-3 text-xs font-semibold text-white disabled:opacity-50" style="background:var(--brand)">
              {$addMut.isPending ? 'Adding…' : 'Add'}
            </button>
            <button onclick={() => showAdd = false}
              class="min-h-[44px] rounded-lg border border-[var(--border)] px-3 text-xs text-[var(--fg-muted)]">Cancel</button>
          </div>
        </div>
      {:else}
        <button onclick={() => { showAdd = true; newNumber = String((dayPeriods.at(-1)?.period_number ?? 0) + 1); }}
          class="flex min-h-[44px] items-center gap-1 text-xs font-semibold transition hover:opacity-70" style="color:var(--brand)">
          <svg class="h-3.5 w-3.5" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" d="M12 4v16m8-8H4"/>
          </svg>
          Add period to {DAY_LABELS[selectedDay]}
        </button>
      {/if}
    </div>
  </div>
</div>

<ConfirmModal
  open={!!confirmDeleteId}
  title="Remove period?"
  message="This period will be removed from the bell schedule. Any timetable slots using it will also be affected."
  confirmLabel="Remove"
  isPending={$deleteMut.isPending}
  onConfirm={() => { $deleteMut.mutate(confirmDeleteId!); confirmDeleteId = null; }}
  onCancel={() => confirmDeleteId = null}
/>

{#if showCopy}
  <div use:portal role="dialog" aria-modal="true" class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
    <div class="w-full max-w-sm rounded-2xl border border-[var(--border)] bg-[var(--card)] p-6 shadow-2xl">
      <h3 class="text-sm font-semibold text-[var(--fg)]">Copy {DAY_LABELS[selectedDay]}'s periods</h3>
      <p class="mt-1 text-xs text-[var(--fg-muted)]">Choose which other days should get the same periods. Days that already have a matching period number, or are marked closed, are skipped.</p>
      <div class="mt-3 grid grid-cols-2 gap-2">
        {#each DAYS.filter(d => d !== selectedDay) as day}
          <label class="flex min-h-[44px] cursor-pointer items-center gap-2 rounded-lg border border-[var(--border)] px-2.5 text-sm">
            <input type="checkbox" checked={copyTargets.has(day)} onchange={() => toggleTarget(day)} class="h-4 w-4 rounded accent-[var(--brand)]" />
            {DAY_LABELS[day]}
            {#if !openDays.has(day)}
              <span class="text-[10px] text-[var(--fg-subtle)]">(closed)</span>
            {/if}
          </label>
        {/each}
      </div>
      <div class="mt-4 flex gap-2">
        <button onclick={() => $copyMut.mutate()} disabled={copyTargets.size === 0 || $copyMut.isPending}
          class="min-h-[44px] flex-1 rounded-xl px-4 text-sm font-semibold text-white disabled:opacity-50" style="background:var(--brand)">
          {$copyMut.isPending ? 'Copying…' : 'Copy'}
        </button>
        <button onclick={() => { showCopy = false; copyTargets = new Set(); }}
          class="min-h-[44px] rounded-xl border border-[var(--border)] px-4 text-sm text-[var(--fg-muted)]">Cancel</button>
      </div>
    </div>
  </div>
{/if}

<style>
  @reference "tailwindcss";
  .sel { @apply min-h-[44px] rounded-lg border border-[var(--border)] bg-[var(--bg)] px-2 py-1 text-[var(--fg)] focus:border-[var(--brand)] focus:outline-none transition; }
</style>
