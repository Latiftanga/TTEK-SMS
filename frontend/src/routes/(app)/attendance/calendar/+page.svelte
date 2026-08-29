<script lang="ts">
  import { createQuery, createMutation, useQueryClient } from '@tanstack/svelte-query';
  import { writable } from 'svelte/store';
  import { listYears } from '$lib/api/academic';
  import { findCurrentTerm } from '$lib/academicPeriod';
  import {
    listCalendar, generateCalendar, overrideCalendarDay, overrideCalendarRange,
    type CalendarDay, type DayType,
  } from '$lib/api/attendance';
  import { userRole } from '$lib/stores/permissions';
  import { toast } from '$lib/stores/toast';
  import { setPageTitle } from '$lib/stores/title';
  import { portal } from '$lib/actions/portal';
  setPageTitle('Attendance Calendar');
  import CalendarGrid from './CalendarGrid.svelte';

  const qc = useQueryClient();

  const canManage = $derived($userRole === 'admin' || $userRole === 'approver');

  // ── Term selection ─────────────────────────────────────────────────────────────
  let termId = $state('');
  const yearsQ   = createQuery({ queryKey: ['academic-years'], queryFn: listYears, staleTime: 5 * 60_000 });
  const allTerms = $derived(($yearsQ.data ?? []).flatMap(y => y.terms.map(t => ({ ...t, yearName: y.name }))));

  $effect(() => {
    const cur = findCurrentTerm(allTerms);
    if (cur && !termId) termId = cur.id;
  });

  // A term "passed" once its end_date is behind today, regardless of
  // is_current — a future term (not yet started) stays fully editable, only
  // a genuinely concluded one is locked. Mirrors the backend's own
  // _reject_if_term_passed() check (services/attendance_calendar.py) —
  // Regenerate and both override actions are blocked; plain "Generate
  // calendar" stays allowed either way (it only fills in missing days, so a
  // school can still backfill a term it forgot to generate at the time).
  const today = new Date().toISOString().slice(0, 10);
  const selectedTerm = $derived(allTerms.find(t => t.id === termId));
  const termPassed = $derived(!!selectedTerm && selectedTerm.end_date < today);
  const canEditCalendar = $derived(canManage && !termPassed);

  // ── Calendar data ──────────────────────────────────────────────────────────────
  const calOpts = writable({ queryKey: ['calendar', termId] as const, queryFn: () => listCalendar(termId), enabled: false, staleTime: 5 * 60_000 });
  $effect(() => {
    if (termId) calOpts.set({ queryKey: ['calendar', termId] as const, queryFn: () => listCalendar(termId), enabled: true, staleTime: 5 * 60_000 });
  });
  const calendarQ = createQuery(calOpts);

  // Group days by YYYY-MM
  const byMonth = $derived.by(() => {
    const map = new Map<string, CalendarDay[]>();
    for (const d of $calendarQ.data ?? []) {
      const key = d.date.slice(0, 7);
      if (!map.has(key)) map.set(key, []);
      map.get(key)!.push(d);
    }
    return [...map.entries()].sort(([a], [b]) => a.localeCompare(b)).map(([k, days]) => ({
      year: parseInt(k.slice(0, 4)), month: parseInt(k.slice(5, 7)) - 1, days,
    }));
  });

  // ── Generate / force-regenerate ───────────────────────────────────────────────
  let confirmRegen = $state(false);

  const genMut = createMutation({
    mutationFn: (force: boolean) => generateCalendar(termId, force),
    onSuccess: (res, force) => {
      qc.invalidateQueries({ queryKey: ['calendar', termId] });
      confirmRegen = false;
      toast.success(force
        ? `Calendar regenerated — ${res.length} day(s) updated.`
        : `${res.length} calendar day(s) generated.`
      );
    },
    onError: (e: unknown) => toast.error(
      (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? 'Could not generate calendar.'
    ),
  });

  // ── Override ──────────────────────────────────────────────────────────────────
  let overrideDay  = $state<CalendarDay | null>(null);
  let overrideType = $state<DayType>('SCHOOL_DAY');
  let overrideNote = $state('');

  function openOverride(d: CalendarDay) {
    overrideDay = d; overrideType = d.day_type; overrideNote = d.notes ?? '';
  }
  function closeOverride() { overrideDay = null; }
  function onModalKeydown(e: KeyboardEvent) { if (e.key === 'Escape') closeOverride(); }

  const overrideMut = createMutation({
    mutationFn: () => overrideCalendarDay(overrideDay!.id, { day_type: overrideType, notes: overrideNote || null }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['calendar', termId] });
      overrideDay = null;
      toast.success('Calendar day updated.');
    },
    onError: () => toast.error('Could not update calendar day.'),
  });

  const DAY_TYPES: DayType[] = ['SCHOOL_DAY','EXAM_DAY','HALF_DAY','PUBLIC_HOLIDAY','SCHOOL_HOLIDAY','WEEKEND'];

  // ── Range override (e.g. a week-long mid-term break in one action) ─────────────
  let rangeOpen  = $state(false);
  let rangeStart = $state('');
  let rangeEnd   = $state('');
  let rangeType  = $state<DayType>('SCHOOL_HOLIDAY');
  let rangeNote  = $state('');
  let rangeError = $state('');

  function openRange() {
    rangeStart = ''; rangeEnd = ''; rangeType = 'SCHOOL_HOLIDAY'; rangeNote = ''; rangeError = '';
    rangeOpen = true;
  }
  function closeRange() { rangeOpen = false; }
  function onRangeModalKeydown(e: KeyboardEvent) { if (e.key === 'Escape') closeRange(); }

  const rangeMut = createMutation({
    mutationFn: () => overrideCalendarRange({
      start_date: rangeStart, end_date: rangeEnd, day_type: rangeType, notes: rangeNote || null,
    }),
    onSuccess: (days) => {
      qc.invalidateQueries({ queryKey: ['calendar', termId] });
      rangeOpen = false;
      toast.success(`${days.length} day(s) updated.`);
    },
    onError: (e: unknown) => {
      rangeError = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
        ?? 'Could not update this range.';
    },
  });

  function submitRange() {
    rangeError = '';
    if (!rangeStart || !rangeEnd) { rangeError = 'Start and end date are required.'; return; }
    if (rangeEnd < rangeStart) { rangeError = 'End date must be on or after the start date.'; return; }
    $rangeMut.mutate();
  }

  // ── Legend ─────────────────────────────────────────────────────────────────────
  const LEGEND = [
    { type: 'SCHOOL_DAY',    label: 'School day',    cls: 'bg-white border border-[var(--border)] dark:bg-[var(--card)]' },
    { type: 'EXAM_DAY',      label: 'Exam day',      cls: 'bg-purple-50 dark:bg-purple-950/30' },
    { type: 'HALF_DAY',      label: 'Half day',      cls: 'bg-blue-50 dark:bg-blue-950/30' },
    { type: 'PUBLIC_HOLIDAY',label: 'Public holiday', cls: 'bg-red-50 dark:bg-red-950/30' },
    { type: 'SCHOOL_HOLIDAY',label: 'School holiday', cls: 'bg-amber-50 dark:bg-amber-950/30' },
    { type: 'WEEKEND',       label: 'Weekend',        cls: 'bg-[var(--hover)]' },
  ];
</script>

<!-- Toolbar — stacks vertically on narrow screens (full-width term select,
     then a side-by-side button row) rather than a single flex-wrap row,
     which used to let a bare button end up bottom-aligned next to the
     labeled select and let the confirm-regenerate text/buttons crowd
     together with no clean break. -->
<div class="mb-5 flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-end">
  <div class="w-full sm:w-auto">
    <label class="label" for="cal-term">Term</label>
    <select id="cal-term" bind:value={termId} class="sel w-full sm:w-auto">
      <option value="">Select term…</option>
      {#each allTerms as t (t.id)}
        <option value={t.id}>{t.yearName} · {t.name}{t.is_current ? ' (current)' : ''}</option>
      {/each}
    </select>
  </div>
  {#if canManage && termId}
    <div class="flex flex-wrap gap-2">
      <button onclick={() => $genMut.mutate(false)} disabled={$genMut.isPending}
        class="min-h-[44px] flex-1 rounded-xl border border-[var(--border)] px-4 py-2 text-sm font-semibold text-[var(--fg-muted)] hover:bg-[var(--hover)] disabled:opacity-50 transition sm:flex-none">
        {$genMut.isPending && !confirmRegen ? 'Generating…' : 'Generate calendar'}
      </button>
      {#if byMonth.length > 0 && !confirmRegen && canEditCalendar}
        <button onclick={() => confirmRegen = true}
          class="min-h-[44px] flex-1 rounded-xl border border-amber-300 px-4 py-2 text-sm font-semibold text-amber-700 hover:bg-amber-50 transition dark:border-amber-800 dark:text-amber-400 dark:hover:bg-amber-950/30 sm:flex-none">
          Regenerate
        </button>
      {/if}
      {#if byMonth.length > 0 && canEditCalendar}
        <button onclick={openRange}
          class="min-h-[44px] flex-1 rounded-xl border border-[var(--border)] px-4 py-2 text-sm font-semibold text-[var(--fg-muted)] hover:bg-[var(--hover)] transition sm:flex-none">
          Mark a range…
        </button>
      {/if}
    </div>
    {#if byMonth.length > 0 && termPassed}
      <p class="w-full text-xs text-[var(--fg-subtle)] sm:w-auto">
        This term ended {selectedTerm?.end_date} — Regenerate and day overrides are locked. "Generate calendar" still works, to backfill any missing days.
      </p>
    {/if}
    {#if byMonth.length > 0 && confirmRegen && canEditCalendar}
      <div class="flex w-full flex-col gap-2 rounded-xl border border-amber-300 bg-amber-50 px-3 py-2.5 dark:border-amber-800 dark:bg-amber-950/30 sm:w-auto">
        <span class="text-xs text-amber-700 dark:text-amber-300">Re-evaluate all days against the current schedule? Days you've manually overridden (marked <span aria-hidden="true">&#9679;</span>) are protected and won't change.</span>
        <div class="flex gap-2">
          <button onclick={() => $genMut.mutate(true)} disabled={$genMut.isPending}
            class="min-h-[44px] flex-1 rounded-lg bg-amber-500 px-3 py-1 text-xs font-semibold text-white hover:opacity-90 disabled:opacity-50 transition sm:flex-none">
            {$genMut.isPending ? '…' : 'Yes, regenerate'}
          </button>
          <button onclick={() => confirmRegen = false}
            class="min-h-[44px] flex-1 rounded-lg border border-amber-300 px-3 py-1 text-xs font-semibold text-amber-700 hover:bg-amber-100 dark:border-amber-800 dark:text-amber-400 dark:hover:bg-amber-950/50 transition sm:flex-none">
            Cancel
          </button>
        </div>
      </div>
    {/if}
  {/if}
</div>

{#if !termId}
  <div class="rounded-2xl border border-dashed border-[var(--border)] p-10 text-center text-sm text-[var(--fg-muted)]">Select a term to view the calendar.</div>
{:else if $calendarQ.isPending}
  <div class="h-48 animate-pulse rounded-2xl bg-[var(--card)]"></div>
{:else if byMonth.length === 0}
  <div class="rounded-2xl border border-dashed border-[var(--border)] bg-[var(--card)] p-10 text-center">
    <p class="text-sm text-[var(--fg-muted)]">No calendar days yet.</p>
    {#if canManage}<p class="mt-1 text-xs text-[var(--fg-subtle)]">Click "Generate calendar" to create school days for this term.</p>{/if}
  </div>
{:else}
  <div class="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
    {#each byMonth as { year, month, days } (year + '-' + month)}
      <div class="rounded-2xl border border-[var(--border)] bg-[var(--card)] p-4">
        <CalendarGrid {year} {month} {days} canManage={canEditCalendar} onDayClick={openOverride} />
      </div>
    {/each}
  </div>
{/if}

<!-- Legend -->
<!-- 2-column grid on mobile — 7 chips of uneven label length in a plain
     flex-wrap row wrapped raggedly (different item counts per row); a grid
     aligns them into clean, even rows instead. Reverts to the original
     flex-wrap row at sm: and up, where there's enough width for it to
     read fine on one or two lines. -->
<div class="mt-5 grid grid-cols-2 gap-2 sm:flex sm:flex-wrap sm:items-center">
  {#each LEGEND as l}
    <span class="flex items-center gap-1.5 rounded-lg px-2.5 py-1 text-[10px] font-medium text-[var(--fg-muted)] {l.cls}">
      <span class="h-2.5 w-2.5 shrink-0 rounded-sm {l.cls}"></span>{l.label}
    </span>
  {/each}
  <span class="flex items-center gap-1.5 rounded-lg border border-[var(--border)] px-2.5 py-1 text-[10px] font-medium text-[var(--fg-muted)]" title="Protected from Regenerate">
    <span aria-hidden="true" class="shrink-0">&#9679;</span> Manually overridden
  </span>
</div>

<!-- Override modal -->
{#if overrideDay && canEditCalendar}
  <!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
  <div use:portal role="dialog" aria-modal="true"
    class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
    onkeydown={onModalKeydown}>
    <div class="flex max-h-[90vh] w-full max-w-sm flex-col rounded-2xl border border-[var(--border)] bg-[var(--card)] shadow-2xl">
      <div class="shrink-0 p-6 pb-0">
        <h2 class="text-base font-semibold text-[var(--fg)]">Override {overrideDay.date}</h2>
        <p class="mt-1 text-sm text-[var(--fg-muted)]">This day will be protected from future "Regenerate" runs.</p>
      </div>
      <div class="min-h-0 flex-1 overflow-y-auto p-6">
        <div class="space-y-3">
          <div>
            <label class="label" for="ov-type">Day type</label>
            <select id="ov-type" bind:value={overrideType} class="sel w-full">
              {#each DAY_TYPES as t}
                <option value={t}>{t.replace(/_/g, ' ')}</option>
              {/each}
            </select>
          </div>
          <div>
            <label class="label" for="ov-note">Notes (optional)</label>
            <input id="ov-note" bind:value={overrideNote} placeholder="e.g. Sports Day" class="sel w-full" />
          </div>
        </div>
      </div>
      <div class="flex shrink-0 justify-end gap-3 p-6 pt-0">
        <button onclick={closeOverride} disabled={$overrideMut.isPending}
          class="min-h-[44px] rounded-lg px-4 py-2 text-sm text-[var(--fg-muted)] transition hover:bg-[var(--hover)] disabled:opacity-50">
          Cancel
        </button>
        <button onclick={() => $overrideMut.mutate()} disabled={$overrideMut.isPending}
          class="min-h-[44px] rounded-lg px-4 py-2 text-sm font-semibold text-white transition hover:opacity-90 disabled:opacity-50" style="background:var(--brand)">
          {$overrideMut.isPending ? 'Saving…' : 'Save'}
        </button>
      </div>
    </div>
  </div>
{/if}

<!-- Range override modal — e.g. a week-long mid-term break in one action,
     instead of overriding each day individually. -->
{#if rangeOpen && canEditCalendar}
  <!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
  <div use:portal role="dialog" aria-modal="true"
    class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
    onkeydown={onRangeModalKeydown}>
    <div class="flex max-h-[90vh] w-full max-w-sm flex-col rounded-2xl border border-[var(--border)] bg-[var(--card)] shadow-2xl">
      <div class="shrink-0 p-6 pb-0">
        <h2 class="text-base font-semibold text-[var(--fg)]">Mark a date range</h2>
        <p class="mt-1 text-sm text-[var(--fg-muted)]">
          e.g. a mid-term break — every already-generated day in this range is updated at once and protected from future "Regenerate" runs.
        </p>
      </div>
      <div class="min-h-0 flex-1 overflow-y-auto p-6">
        <div class="space-y-3">
          <div class="grid grid-cols-2 gap-3">
            <div>
              <label class="label" for="range-start">From</label>
              <input id="range-start" type="date" bind:value={rangeStart} class="sel w-full" />
            </div>
            <div>
              <label class="label" for="range-end">To</label>
              <input id="range-end" type="date" bind:value={rangeEnd} class="sel w-full" />
            </div>
          </div>
          <div>
            <label class="label" for="range-type">Day type</label>
            <select id="range-type" bind:value={rangeType} class="sel w-full">
              {#each DAY_TYPES as t}
                <option value={t}>{t.replace(/_/g, ' ')}</option>
              {/each}
            </select>
          </div>
          <div>
            <label class="label" for="range-note">Notes (optional)</label>
            <input id="range-note" bind:value={rangeNote} placeholder="e.g. Mid-term break" class="sel w-full" />
          </div>
          {#if rangeError}<p class="text-xs text-red-500">{rangeError}</p>{/if}
        </div>
      </div>
      <div class="flex shrink-0 justify-end gap-3 p-6 pt-0">
        <button onclick={closeRange} disabled={$rangeMut.isPending}
          class="min-h-[44px] rounded-lg px-4 py-2 text-sm text-[var(--fg-muted)] transition hover:bg-[var(--hover)] disabled:opacity-50">
          Cancel
        </button>
        <button onclick={submitRange} disabled={$rangeMut.isPending}
          class="min-h-[44px] rounded-lg px-4 py-2 text-sm font-semibold text-white transition hover:opacity-90 disabled:opacity-50" style="background:var(--brand)">
          {$rangeMut.isPending ? 'Saving…' : 'Save'}
        </button>
      </div>
    </div>
  </div>
{/if}

<style>
  @reference "tailwindcss";
  .label { @apply block text-xs font-medium text-[var(--fg-muted)] mb-1; }
  .sel   { @apply min-h-[44px] rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--fg)] focus:border-[var(--brand)] focus:outline-none transition; }
</style>
