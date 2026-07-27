<script lang="ts">
  import { createQuery, createMutation, useQueryClient } from '@tanstack/svelte-query';
  import { writable } from 'svelte/store';
  import { listYears } from '$lib/api/academic';
  import {
    listCalendar, generateCalendar, overrideCalendarDay,
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
    const cur = allTerms.find(t => t.is_current);
    if (cur && !termId) termId = cur.id;
  });

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

<!-- Toolbar -->
<div class="mb-5 flex flex-wrap items-end gap-3">
  <div>
    <label class="label" for="cal-term">Term</label>
    <select id="cal-term" bind:value={termId} class="sel">
      <option value="">Select term…</option>
      {#each allTerms as t (t.id)}
        <option value={t.id}>{t.yearName} · {t.name}{t.is_current ? ' (current)' : ''}</option>
      {/each}
    </select>
  </div>
  {#if canManage && termId}
    <button onclick={() => $genMut.mutate(false)} disabled={$genMut.isPending}
      class="rounded-xl border border-[var(--border)] px-4 py-2 text-sm font-semibold text-[var(--fg-muted)] hover:bg-[var(--hover)] disabled:opacity-50 transition">
      {$genMut.isPending && !confirmRegen ? 'Generating…' : 'Generate calendar'}
    </button>
    {#if byMonth.length > 0}
      {#if !confirmRegen}
        <button onclick={() => confirmRegen = true}
          class="rounded-xl border border-amber-300 px-4 py-2 text-sm font-semibold text-amber-700 hover:bg-amber-50 transition dark:border-amber-800 dark:text-amber-400 dark:hover:bg-amber-950/30">
          Regenerate
        </button>
      {:else}
        <div class="flex items-center gap-2 rounded-xl border border-amber-300 bg-amber-50 px-3 py-2 dark:border-amber-800 dark:bg-amber-950/30">
          <span class="text-xs text-amber-700 dark:text-amber-300">Re-evaluate all days against the current schedule? Days you've manually overridden (marked <span aria-hidden="true">&#9679;</span>) are protected and won't change.</span>
          <button onclick={() => $genMut.mutate(true)} disabled={$genMut.isPending}
            class="rounded-lg bg-amber-500 px-3 py-1 text-xs font-semibold text-white hover:opacity-90 disabled:opacity-50 transition">
            {$genMut.isPending ? '…' : 'Yes, regenerate'}
          </button>
          <button onclick={() => confirmRegen = false} class="text-xs text-amber-700 hover:text-amber-900 dark:text-amber-400 transition">Cancel</button>
        </div>
      {/if}
    {/if}
  {/if}
</div>

<!-- Legend -->
<div class="mb-5 flex flex-wrap items-center gap-2">
  {#each LEGEND as l}
    <span class="flex items-center gap-1.5 rounded-lg px-2.5 py-1 text-[10px] font-medium text-[var(--fg-muted)] {l.cls}">
      <span class="h-2.5 w-2.5 rounded-sm {l.cls}"></span>{l.label}
    </span>
  {/each}
  <span class="flex items-center gap-1.5 rounded-lg border border-[var(--border)] px-2.5 py-1 text-[10px] font-medium text-[var(--fg-muted)]" title="Protected from Regenerate">
    <span aria-hidden="true">&#9679;</span> Manually overridden
  </span>
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
        <CalendarGrid {year} {month} {days} {canManage} onDayClick={openOverride} />
      </div>
    {/each}
  </div>
{/if}

<!-- Override modal -->
{#if overrideDay && canManage}
  <!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
  <div use:portal role="dialog" aria-modal="true"
    class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
    onkeydown={onModalKeydown}>
    <div class="w-full max-w-sm rounded-2xl border border-[var(--border)] bg-[var(--card)] p-6 shadow-2xl">
      <h2 class="text-base font-semibold text-[var(--fg)]">Override {overrideDay.date}</h2>
      <p class="mt-1 text-sm text-[var(--fg-muted)]">This day will be protected from future "Regenerate" runs.</p>
      <div class="mt-4 space-y-3">
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
      <div class="mt-5 flex justify-end gap-3">
        <button onclick={closeOverride} disabled={$overrideMut.isPending}
          class="rounded-lg px-4 py-2 text-sm text-[var(--fg-muted)] transition hover:bg-[var(--hover)] disabled:opacity-50">
          Cancel
        </button>
        <button onclick={() => $overrideMut.mutate()} disabled={$overrideMut.isPending}
          class="rounded-lg px-4 py-2 text-sm font-semibold text-white transition hover:opacity-90 disabled:opacity-50" style="background:var(--brand)">
          {$overrideMut.isPending ? 'Saving…' : 'Save'}
        </button>
      </div>
    </div>
  </div>
{/if}

<style>
  @reference "tailwindcss";
  .label { @apply block text-xs font-medium text-[var(--fg-muted)] mb-1; }
  .sel   { @apply rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--fg)] focus:border-[var(--brand)] focus:outline-none transition; }
</style>
