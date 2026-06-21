<script lang="ts">
  import { createQuery } from '@tanstack/svelte-query';
  import { writable } from 'svelte/store';
  import { listClassSubjects, getClassTeacher } from '$lib/api/academic';
  import { listStaff } from '$lib/api/staff';

  interface Props {
    classId: string;
    currentYearId: string;
    onSubjects: () => void;
    onTeacher: () => void;
  }
  const { classId, currentYearId, onSubjects, onTeacher }: Props = $props();

  const subjQ  = createQuery({ queryKey: ['class-subjects', classId],               queryFn: () => listClassSubjects(classId),              staleTime: 2 * 60_000 });
  const tchrOpts = writable({ queryKey: ['class-teacher', classId, currentYearId] as const, queryFn: () => getClassTeacher(classId, currentYearId), enabled: !!currentYearId, staleTime: 60_000 });
  $effect(() => {
    const yid = currentYearId;
    tchrOpts.set({ queryKey: ['class-teacher', classId, yid] as const, queryFn: () => getClassTeacher(classId, yid), enabled: !!yid, staleTime: 60_000 });
  });
  const tchrQ = createQuery(tchrOpts);
  const staffQ = createQuery({ queryKey: ['staff'],                                  queryFn: () => listStaff({ limit: 200 }),                staleTime: 5 * 60_000 });

  const count       = $derived($subjQ.data?.length ?? 0);
  const teacherRec  = $derived($tchrQ.data ?? null);
  const staffMap    = $derived(new Map(($staffQ.data ?? []).map(s => [s.id, s])));
  const teacherName = $derived(teacherRec ? (staffMap.get(teacherRec.staff_member_id)?.display_name ?? null) : null);
</script>

<td class="hidden px-4 py-2.5 md:table-cell">
  <button onclick={onSubjects}
    class="inline-flex items-center gap-1.5 rounded-lg border border-[var(--border)] px-2.5 py-1 text-xs font-medium transition hover:border-[var(--brand)] hover:text-[var(--brand)]">
    {#if $subjQ.isPending}
      <span class="text-[var(--fg-subtle)]">…</span>
    {:else}
      <span class="font-semibold tabular-nums" style="color: var(--brand)">{count}</span>
      <span class="text-[var(--fg-muted)]">subject{count !== 1 ? 's' : ''}</span>
    {/if}
  </button>
</td>
<td class="hidden px-4 py-2.5 md:table-cell">
  <button onclick={onTeacher}
    class="rounded-lg border border-[var(--border)] px-2.5 py-1 text-xs font-medium transition hover:border-[var(--brand)] hover:text-[var(--brand)]
           {teacherName ? 'text-[var(--fg)]' : 'italic text-[var(--fg-subtle)]'}">
    {#if !currentYearId || $tchrQ.isPending}
      <span class="text-[var(--fg-subtle)]">…</span>
    {:else}
      {teacherName ?? 'Unassigned'}
    {/if}
  </button>
</td>
