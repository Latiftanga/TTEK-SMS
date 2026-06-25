<script lang="ts">
  import type { CalendarDay, DayType } from '$lib/api/attendance';

  interface Props {
    year: number;
    month: number;           // 0-indexed (Jan=0)
    days: CalendarDay[];     // pre-filtered to this month
    canManage: boolean;
    onDayClick: (d: CalendarDay) => void;
  }
  let { year, month, days, canManage, onDayClick }: Props = $props();

  const MONTH_NAMES = ['January','February','March','April','May','June',
                       'July','August','September','October','November','December'];
  const DAY_NAMES   = ['Mon','Tue','Wed','Thu','Fri','Sat','Sun'];

  const byDate = $derived(new Map(days.map(d => [d.date, d])));

  // Build 6-row × 7-col grid (Mon-first)
  const cells = $derived.by(() => {
    const first = new Date(year, month, 1);
    const totalDays = new Date(year, month + 1, 0).getDate();
    // Monday-first offset: JS getDay() is 0=Sun; we want 0=Mon
    const offset = (first.getDay() + 6) % 7;
    const grid: (number | null)[] = Array(offset).fill(null);
    for (let d = 1; d <= totalDays; d++) grid.push(d);
    while (grid.length % 7 !== 0) grid.push(null);
    return grid;
  });

  function dateStr(d: number) {
    return `${year}-${String(month + 1).padStart(2, '0')}-${String(d).padStart(2, '0')}`;
  }

  const TYPE_STYLES: Record<DayType, string> = {
    SCHOOL_DAY:    'bg-white dark:bg-[var(--card)] text-[var(--fg)] hover:ring-1 ring-[var(--brand)]',
    EXAM_DAY:      'bg-purple-50 text-purple-800 dark:bg-purple-950/30 dark:text-purple-300 hover:ring-1 ring-purple-400',
    HALF_DAY:      'bg-blue-50 text-blue-800 dark:bg-blue-950/30 dark:text-blue-300 hover:ring-1 ring-blue-400',
    PUBLIC_HOLIDAY:'bg-red-50 text-red-700 dark:bg-red-950/30 dark:text-red-400',
    SCHOOL_HOLIDAY:'bg-amber-50 text-amber-700 dark:bg-amber-950/30 dark:text-amber-400',
    WEEKEND:       'bg-[var(--hover)] text-[var(--fg-subtle)]',
  };

  const TYPE_DOT: Record<DayType, string> = {
    SCHOOL_DAY: '', EXAM_DAY: 'bg-purple-400', HALF_DAY: 'bg-blue-400',
    PUBLIC_HOLIDAY: 'bg-red-400', SCHOOL_HOLIDAY: 'bg-amber-400', WEEKEND: '',
  };
</script>

<div>
  <h3 class="mb-2 text-sm font-semibold text-[var(--fg)]">{MONTH_NAMES[month]} {year}</h3>
  <!-- Day headers -->
  <div class="mb-1 grid grid-cols-7 gap-1 text-center">
    {#each DAY_NAMES as d}
      <div class="text-[10px] font-semibold uppercase text-[var(--fg-subtle)]">{d}</div>
    {/each}
  </div>
  <!-- Day cells -->
  <div class="grid grid-cols-7 gap-1">
    {#each cells as cell}
      {#if cell === null}
        <div></div>
      {:else}
        {@const ds  = dateStr(cell)}
        {@const cal = byDate.get(ds)}
        {@const dot = cal ? TYPE_DOT[cal.day_type] : ''}
        <button
          onclick={() => cal && canManage ? onDayClick(cal) : null}
          class="relative flex min-h-[2.5rem] items-start justify-end rounded-lg p-1 text-right text-xs font-medium transition
            {cal ? TYPE_STYLES[cal.day_type] : 'bg-[var(--hover)] text-[var(--fg-subtle)] opacity-40'}
            {canManage && cal ? 'cursor-pointer' : 'cursor-default'}"
          title={cal?.notes ?? cal?.day_type ?? ''}>
          <span>{cell}</span>
          {#if dot}
            <span class="absolute bottom-1 left-1 h-1.5 w-1.5 rounded-full {dot}"></span>
          {/if}
        </button>
      {/if}
    {/each}
  </div>
</div>
