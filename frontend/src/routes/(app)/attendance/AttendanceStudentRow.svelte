<script lang="ts">
  import type { AttendanceStatus, StudentAbsenceSummary } from '$lib/api/attendance';

  interface StudentLike { id: string; display_name: string; admission_number: string }

  interface Props {
    student: StudentLike;
    index: number;
    status: AttendanceStatus | '';
    summary: StudentAbsenceSummary | undefined;
    onToggle: (status: AttendanceStatus) => void;
  }
  const { student, index, status, summary, onToggle }: Props = $props();

  type StatusOption = { code: AttendanceStatus; label: string; active: string; idle: string };
  const STATUSES: StatusOption[] = [
    { code: 'PRESENT', label: 'P', active: 'bg-green-500 text-white', idle: 'border border-green-300 text-green-700 hover:bg-green-50 dark:border-green-800 dark:text-green-400 dark:hover:bg-green-950/40' },
    { code: 'ABSENT',  label: 'A', active: 'bg-red-500 text-white',   idle: 'border border-red-300 text-red-700 hover:bg-red-50 dark:border-red-800 dark:text-red-400 dark:hover:bg-red-950/40' },
    { code: 'LATE',    label: 'L', active: 'bg-amber-500 text-white', idle: 'border border-amber-300 text-amber-700 hover:bg-amber-50 dark:border-amber-800 dark:text-amber-400 dark:hover:bg-amber-950/40' },
    { code: 'EXCUSED', label: 'E', active: 'bg-blue-500 text-white',  idle: 'border border-blue-300 text-blue-700 hover:bg-blue-50 dark:border-blue-800 dark:text-blue-400 dark:hover:bg-blue-950/40' },
  ];
</script>

<div class="flex items-center gap-3 border-b border-[var(--border)] px-4 py-3 last:border-0 {index % 2 === 1 ? 'bg-[var(--hover)]' : ''}">
  <span class="w-7 text-right text-xs font-mono text-[var(--fg-subtle)]">{index + 1}</span>
  <div class="min-w-0 flex-1">
    <p class="truncate text-sm font-medium text-[var(--fg)]">{student.display_name}</p>
    <div class="flex items-center gap-2">
      <p class="text-[10px] font-mono text-[var(--fg-subtle)]">{student.admission_number}</p>
      {#if summary && summary.days_absent > 0}
        <span class="text-[10px] font-semibold text-red-500" title="{summary.days_absent} absences this term">{summary.days_absent} abs</span>
      {/if}
      {#if summary && summary.days_late > 0}
        <span class="text-[10px] font-semibold text-amber-500" title="{summary.days_late} lates this term">{summary.days_late} late</span>
      {/if}
    </div>
  </div>
  <div class="flex gap-1">
    {#each STATUSES as s}
      <button onclick={() => onToggle(s.code)}
        class="h-8 w-8 rounded-lg text-xs font-bold transition {status === s.code ? s.active : s.idle}"
        title={s.code}>
        {s.label}
      </button>
    {/each}
  </div>
</div>
