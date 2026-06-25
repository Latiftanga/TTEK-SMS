<script lang="ts">
  import { createQuery, createMutation, useQueryClient } from '@tanstack/svelte-query';
  import { listSchedule, upsertSchedule, type DayOfWeek, type ScheduleDay } from '$lib/api/attendance';
  import { userRole } from '$lib/stores/permissions';
  import { toast } from '$lib/stores/toast';
  import { setPageTitle } from '$lib/stores/title';

  const qc = useQueryClient();
  setPageTitle('Schedule');
  const canManage = $derived($userRole === 'admin' || $userRole === 'approver');

  const schedQ = createQuery({ queryKey: ['schedule'], queryFn: listSchedule, staleTime: 5 * 60_000 });

  const DAYS: DayOfWeek[] = ['MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT', 'SUN'];
  const DAY_LABELS: Record<DayOfWeek, string> = {
    MON: 'Monday', TUE: 'Tuesday', WED: 'Wednesday',
    THU: 'Thursday', FRI: 'Friday', SAT: 'Saturday', SUN: 'Sunday',
  };

  let forms = $state<Record<DayOfWeek, { is_school_day: boolean; start_time: string; end_time: string }>>({
    MON: { is_school_day: true,  start_time: '07:30', end_time: '15:30' },
    TUE: { is_school_day: true,  start_time: '07:30', end_time: '15:30' },
    WED: { is_school_day: true,  start_time: '07:30', end_time: '15:30' },
    THU: { is_school_day: true,  start_time: '07:30', end_time: '15:30' },
    FRI: { is_school_day: true,  start_time: '07:30', end_time: '15:30' },
    SAT: { is_school_day: false, start_time: '', end_time: '' },
    SUN: { is_school_day: false, start_time: '', end_time: '' },
  });

  $effect(() => {
    if ($schedQ.data) {
      const map = new Map<DayOfWeek, ScheduleDay>($schedQ.data.map(s => [s.day_of_week, s]));
      for (const d of DAYS) {
        const s = map.get(d);
        if (s) forms[d] = { is_school_day: s.is_school_day, start_time: s.start_time?.slice(0, 5) ?? '', end_time: s.end_time?.slice(0, 5) ?? '' };
      }
    }
  });

  let saving = $state<DayOfWeek | null>(null);
  const saveMut = createMutation({
    mutationFn: (day: DayOfWeek) => {
      const f = forms[day];
      return upsertSchedule({ day_of_week: day, is_school_day: f.is_school_day, start_time: f.start_time || null, end_time: f.end_time || null });
    },
    onSuccess: (_, day) => {
      qc.invalidateQueries({ queryKey: ['schedule'] });
      saving = null;
      toast.success(`${DAY_LABELS[day as DayOfWeek]} schedule saved.`);
    },
    onError: (_, day) => {
      saving = null;
      toast.error(`Could not save ${DAY_LABELS[day as DayOfWeek]}.`);
    },
  });

  let savingAll = $state(false);
  async function saveAll() {
    savingAll = true;
    try {
      await Promise.all(DAYS.map(d => upsertSchedule({ day_of_week: d, is_school_day: forms[d].is_school_day, start_time: forms[d].start_time || null, end_time: forms[d].end_time || null })));
      qc.invalidateQueries({ queryKey: ['schedule'] });
      toast.success('Schedule saved for all days.');
    } catch {
      toast.error('Could not save schedule.');
    } finally {
      savingAll = false;
    }
  }
</script>

{#if !canManage}
  <div class="rounded-2xl border border-dashed border-[var(--border)] p-10 text-center text-sm text-[var(--fg-muted)]">
    Only administrators can manage the school schedule.
  </div>
{:else}
  <div class="mb-3 flex items-center justify-between gap-3">
    <p class="text-sm text-[var(--fg-muted)]">Configure which days are school days and their hours. Used when generating the school calendar for each term.</p>
    <button onclick={saveAll} disabled={savingAll}
      class="shrink-0 rounded-xl px-4 py-1.5 text-xs font-semibold text-white hover:opacity-90 disabled:opacity-50 transition" style="background:var(--brand)">
      {savingAll ? 'Saving…' : 'Save all'}
    </button>
  </div>

  <div class="overflow-hidden rounded-2xl border border-[var(--border)] bg-[var(--card)]">
    <div class="grid grid-cols-[6rem_1fr_1fr_1fr_5rem] gap-px border-b border-[var(--border)] bg-[var(--border)] text-[10px] font-semibold uppercase tracking-widest text-[var(--fg-subtle)]">
      <div class="bg-[var(--card)] px-4 py-3">Day</div>
      <div class="bg-[var(--card)] px-4 py-3">School day</div>
      <div class="bg-[var(--card)] px-4 py-3">Start time</div>
      <div class="bg-[var(--card)] px-4 py-3">End time</div>
      <div class="bg-[var(--card)] px-4 py-3"></div>
    </div>

    {#each DAYS as day}
      {@const f = forms[day]}
      {@const isSaving = saving === day && $saveMut.isPending}
      <div class="grid grid-cols-[6rem_1fr_1fr_1fr_5rem] items-center gap-px border-b border-[var(--border)] bg-[var(--border)] last:border-0">
        <div class="bg-[var(--card)] px-4 py-3 text-sm font-semibold text-[var(--fg)]">{DAY_LABELS[day].slice(0, 3)}</div>
        <div class="bg-[var(--card)] px-4 py-3">
          <label class="flex cursor-pointer items-center gap-2">
            <input type="checkbox" bind:checked={f.is_school_day} class="h-4 w-4 rounded accent-[var(--brand)]" />
            <span class="text-sm {f.is_school_day ? 'text-[var(--fg)]' : 'text-[var(--fg-subtle)]'}">
              {f.is_school_day ? 'Yes' : 'No'}
            </span>
          </label>
        </div>
        <div class="bg-[var(--card)] px-4 py-3">
          {#if f.is_school_day}
            <input type="time" bind:value={f.start_time} class="sel text-sm" />
          {:else}
            <span class="text-[var(--fg-subtle)]">—</span>
          {/if}
        </div>
        <div class="bg-[var(--card)] px-4 py-3">
          {#if f.is_school_day}
            <input type="time" bind:value={f.end_time} class="sel text-sm" />
          {:else}
            <span class="text-[var(--fg-subtle)]">—</span>
          {/if}
        </div>
        <div class="bg-[var(--card)] px-4 py-3">
          <button onclick={() => { saving = day; $saveMut.mutate(day); }} disabled={isSaving}
            class="rounded-lg px-3 py-1.5 text-xs font-semibold text-white hover:opacity-90 disabled:opacity-50 transition" style="background:var(--brand)">
            {isSaving ? '…' : 'Save'}
          </button>
        </div>
      </div>
    {/each}
  </div>
{/if}

<style>
  @reference "tailwindcss";
  .sel { @apply rounded-lg border border-[var(--border)] bg-[var(--bg)] px-2 py-1 text-[var(--fg)] focus:border-[var(--brand)] focus:outline-none transition; }
</style>
