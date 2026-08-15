<script lang="ts">
  import type { CalendarDay } from '$lib/api/attendance';

  interface ClassOption { id: string; display_name: string; }
  interface Props {
    classId: string;
    classes: ClassOption[];
    today: string;
    selectedDate: string;
    calDay: CalendarDay | null;
    dayTypeColor: Record<string, string>;
    onClassChange: (id: string) => void;
    onDateChange: (date: string) => void;
  }
  const { classId, classes, today, selectedDate, calDay, dayTypeColor, onClassChange, onDateChange }: Props = $props();
</script>

<!-- Selectors — stacked full-width on mobile (this pair is the first thing
     a teacher touches every time they open the page), side by side from
     sm: up where there's room for both without crowding. -->
<div class="mb-5 grid grid-cols-1 gap-3 sm:grid-cols-2 sm:items-end">
  <div>
    <label class="label" for="att-class">Class</label>
    <select id="att-class" value={classId} onchange={e => onClassChange(e.currentTarget.value)} class="sel w-full">
      <option value="">Select class…</option>
      {#each classes as c (c.id)}
        <option value={c.id}>{c.display_name}</option>
      {/each}
    </select>
  </div>
  <div>
    <label class="label" for="att-date">Date</label>
    <div class="flex flex-wrap items-center gap-1.5">
      <input id="att-date" type="date" value={selectedDate} max={today}
        onchange={e => onDateChange(e.currentTarget.value)} class="sel min-w-0 flex-1" />
      {#if selectedDate !== today}
        <button onclick={() => onDateChange(today)} title="Jump to today"
          class="today-btn shrink-0">
          Today
        </button>
      {/if}
    </div>
  </div>
  {#if calDay}
    <span class="w-fit rounded-full px-3 py-1 text-xs font-semibold sm:col-span-2 {dayTypeColor[calDay.day_type]}">
      {calDay.day_type.replace(/_/g, ' ')}
      {#if calDay.notes} · {calDay.notes}{/if}
    </span>
  {/if}
</div>

<style>
  @reference "tailwindcss";
  .label     { @apply block text-xs font-medium text-[var(--fg-muted)] mb-1; }
  .sel       { @apply min-h-[44px] rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 text-sm text-[var(--fg)] focus:border-[var(--brand)] focus:outline-none transition; }
  .today-btn { @apply min-h-[44px] rounded-xl border border-[var(--border)] px-3 text-sm font-medium text-[var(--fg-muted)] transition hover:bg-[var(--hover)]; }
</style>
