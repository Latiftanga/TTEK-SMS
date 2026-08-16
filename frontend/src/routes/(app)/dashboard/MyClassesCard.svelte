<script lang="ts">
  // Mirrors AdminView.svelte's "Attendance by class" card exactly (same
  // markup/progress-bar pattern) so the staff dashboard's left column reads
  // as the same product, not a differently-styled one-off.
  import type { ClassSnapshot } from '$lib/api/dashboard';

  interface Props { classes: ClassSnapshot[]; }
  const { classes }: Props = $props();
</script>

<div class="rounded-[1.25rem] border border-[var(--border)] bg-[var(--card)] p-6" style="box-shadow: var(--shadow-sm);">
  <div class="mb-5 flex items-center justify-between">
    <div>
      <p class="text-sm font-semibold text-[var(--fg)]">My Classes</p>
      <p class="mt-0.5 text-[11px] text-[var(--fg-muted)]">Today's attendance</p>
    </div>
    <a href="/attendance" class="text-xs font-semibold transition hover:opacity-80" style="color: var(--brand)">
      Mark attendance →
    </a>
  </div>
  <div class="space-y-4">
    {#each classes as cls (cls.id)}
      {@const pct = cls.student_count > 0 ? Math.round((cls.present_today / cls.student_count) * 100) : 0}
      <!-- Unmarked classes are now the primary "what do I do" cue on this
           page (the dedicated hero prompt was removed) — the whole row is
           a real link to /attendance, not just static amber text, so
           there's an obvious tap target instead of a passive status label. -->
      <svelte:element this={cls.attendance_marked_today ? 'div' : 'a'} href={cls.attendance_marked_today ? undefined : '/attendance'}
        class="block {cls.attendance_marked_today ? '' : 'group -mx-2 rounded-lg px-2 py-1 transition hover:bg-amber-50 dark:hover:bg-amber-950/30'}">
        <div class="mb-1.5 flex items-center justify-between gap-2">
          <span class="text-[0.8125rem] font-medium text-[var(--fg)]">{cls.name}</span>
          {#if cls.attendance_marked_today}
            <span class="text-sm font-bold text-[var(--fg)]">{pct}%</span>
          {:else}
            <span class="flex items-center gap-1 text-sm font-bold text-amber-600 dark:text-amber-400">
              Mark now
              <svg class="h-3.5 w-3.5 transition-transform group-hover:translate-x-0.5" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" d="M9 5l7 7-7 7"/>
              </svg>
            </span>
          {/if}
        </div>
        <div class="h-2 w-full overflow-hidden rounded-full bg-gray-100 dark:bg-gray-800">
          <div class="h-full rounded-full transition-all duration-700"
               style="width: {cls.attendance_marked_today ? pct : 0}%; background-color: var(--brand)"></div>
        </div>
        <p class="mt-1 text-[11px] text-[var(--fg-muted)]">
          {cls.attendance_marked_today ? `${cls.present_today} of ${cls.student_count} present` : `${cls.student_count} students · not marked yet`}
        </p>
      </svelte:element>
    {/each}
  </div>
</div>
