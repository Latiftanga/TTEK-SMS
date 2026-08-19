<script lang="ts">
  // School-wide "who's marked, who hasn't" for one calendar day — the thing
  // an admin actually wants from this page, distinct from the single-class
  // marking flow the rest of it serves. Visual language mirrors
  // dashboard/MyClassesCard.svelte's own marked/unmarked treatment so this
  // reads as the same product, not a new one — plus the class teacher's name,
  // so an unmarked row also answers "who do I go prompt."
  import { reactiveQuery } from '$lib/query.svelte';
  import { getMarkingStatus } from '$lib/api/attendance';

  interface Props {
    calendarId: string;
    onSelectClass: (id: string) => void;
  }
  const { calendarId, onSelectClass }: Props = $props();

  const statusQ = reactiveQuery(() => ({
    queryKey: ['attendance-marking-status', calendarId] as const,
    queryFn: () => getMarkingStatus(calendarId),
    enabled: !!calendarId,
    staleTime: 30_000,
  }));

  const classes = $derived($statusQ.data ?? []);
  const unmarkedCount = $derived(classes.filter(c => !c.marked).length);
</script>

{#if $statusQ.isPending}
  <div class="space-y-3">{#each [1, 2, 3] as _}<div class="h-16 animate-pulse rounded-xl bg-[var(--card)]"></div>{/each}</div>
{:else if classes.length === 0}
  <div class="rounded-2xl border border-dashed border-[var(--border)] p-10 text-center text-sm text-[var(--fg-muted)]">
    No classes to show.
  </div>
{:else}
  <div class="mb-3 flex items-center justify-between gap-2">
    <p class="text-sm font-semibold text-[var(--fg)]">Today's marking status</p>
    {#if unmarkedCount > 0}
      <span class="text-xs font-semibold text-amber-600 dark:text-amber-400">{unmarkedCount} not marked yet</span>
    {:else}
      <span class="text-xs font-semibold text-green-600 dark:text-green-400">All classes marked</span>
    {/if}
  </div>
  <div class="space-y-3">
    {#each classes as cls (cls.class_id)}
      {@const pct = cls.student_count > 0 ? Math.round((cls.present / cls.student_count) * 100) : 0}
      <button type="button" onclick={() => onSelectClass(cls.class_id)}
        class="block w-full text-left {cls.marked
          ? 'rounded-xl border border-[var(--border)] bg-[var(--card)] p-3 transition hover:opacity-90'
          : 'group rounded-xl border border-amber-200 bg-amber-50 p-3 transition hover:bg-amber-100 dark:border-amber-900 dark:bg-amber-950/30 dark:hover:bg-amber-950/50'}">
        <div class="mb-1.5 flex items-center justify-between gap-2">
          <span class="text-[0.8125rem] font-medium text-[var(--fg)]">{cls.name}</span>
          {#if cls.marked}
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
        {#if cls.marked}
          <div class="h-2 w-full overflow-hidden rounded-full bg-gray-100 dark:bg-gray-800">
            <div class="h-full rounded-full transition-all duration-700" style="width: {pct}%; background-color: var(--brand)"></div>
          </div>
        {/if}
        <p class="mt-1 text-[11px] text-[var(--fg-muted)]">
          {cls.marked ? `${cls.present} of ${cls.student_count} present` : `${cls.student_count} students · not marked yet`}
        </p>
        <p class="mt-0.5 text-[11px] {cls.class_teacher_name ? 'text-[var(--fg-subtle)]' : 'font-medium text-amber-600 dark:text-amber-400'}">
          {cls.class_teacher_name ? `Class teacher: ${cls.class_teacher_name}` : 'No class teacher assigned'}
        </p>
      </button>
    {/each}
  </div>
{/if}
