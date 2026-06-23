<script lang="ts">
  import { createQuery, createMutation, useQueryClient } from '@tanstack/svelte-query';
  import { recordRollCall, listRollCalls, type RollCall } from '$lib/api/housing';
  import { listCalendar } from '$lib/api/attendance';
  import { listYears } from '$lib/api/academic';
  import { toast } from '$lib/stores/toast';

  interface Props { houseId: string; canManage: boolean; }
  const { houseId, canManage }: Props = $props();

  const qc = useQueryClient();

  const yearsQ     = createQuery({ queryKey: ['academic-years'], queryFn: listYears,                          staleTime: 5 * 60_000 });
  const rollsQ     = createQuery({ queryKey: ['roll-calls', houseId], queryFn: () => listRollCalls(houseId), staleTime: 60_000 });

  const currentTerm = $derived.by(() => {
    for (const y of $yearsQ.data ?? []) {
      const t = y.terms.find(t => t.is_current);
      if (t) return t;
    }
    return null;
  });

  const calendarQ = createQuery({
    queryKey: ['calendar', currentTerm?.id],
    queryFn: () => listCalendar(currentTerm!.id),
    enabled: !!currentTerm,
    staleTime: 10 * 60_000,
  });

  const today = new Date().toISOString().slice(0, 10);

  // Match calendar entry by date string
  const todayCalEntry = $derived(
    ($calendarQ.data ?? []).find(d => d.date === today) ?? null
  );

  // ── Record form ───────────────────────────────────────────────────────────────
  let showForm = $state(false);
  let rf = $state({ expected: '', present: '', notes: '', calendarId: '' });
  let rfErr = $state('');

  $effect(() => {
    if (todayCalEntry && !rf.calendarId) rf.calendarId = todayCalEntry.id;
  });

  const recordMut = createMutation({
    mutationFn: () => recordRollCall({
      house_id: houseId,
      school_calendar_id: rf.calendarId,
      total_expected: parseInt(rf.expected),
      total_present: parseInt(rf.present),
      notes: rf.notes.trim() || undefined,
    }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['roll-calls', houseId] });
      showForm = false;
      rf = { expected: '', present: '', notes: '', calendarId: todayCalEntry?.id ?? '' };
      toast.success('Roll call recorded.');
    },
    onError: (e: unknown) => {
      rfErr = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? 'Could not record roll call.';
    },
  });

  function handleRecord() {
    rfErr = '';
    const exp = parseInt(rf.expected);
    const pre = parseInt(rf.present);
    if (!rf.calendarId)     { rfErr = 'Select a calendar date.'; return; }
    if (isNaN(exp) || exp < 0) { rfErr = 'Enter a valid expected count.'; return; }
    if (isNaN(pre) || pre < 0) { rfErr = 'Enter a valid present count.'; return; }
    $recordMut.mutate();
  }

  function fmt(dt: string) {
    return new Date(dt).toLocaleString('en-GH', { dateStyle: 'medium', timeStyle: 'short' });
  }

  const schoolDays = $derived(
    ($calendarQ.data ?? [])
      .filter(d => d.day_type === 'SCHOOL_DAY' || d.day_type === 'EXAM_DAY')
      .sort((a, b) => b.date.localeCompare(a.date))
      .slice(0, 30)
  );
</script>

<div>
  {#if canManage}
    <div class="mb-3 flex justify-end">
      <button onclick={() => { showForm = !showForm; rfErr = ''; }}
        class="flex items-center gap-1.5 rounded-xl px-3 py-1.5 text-xs font-semibold text-white transition hover:opacity-90"
        style="background: var(--brand)">
        <svg class="h-3.5 w-3.5" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" d="M12 4v16m8-8H4"/>
        </svg>
        Record roll call
      </button>
    </div>
  {/if}

  {#if showForm}
    <div class="mb-4 rounded-2xl border border-[var(--border)] bg-[var(--card)] p-4">
      <p class="mb-3 text-sm font-semibold text-[var(--fg)]">Tonight's roll call</p>

      {#if $calendarQ.isPending}
        <p class="text-xs text-[var(--fg-muted)]">Loading calendar…</p>
      {:else if !currentTerm}
        <p class="text-xs text-amber-600 dark:text-amber-400">No current term found. Set an active term first.</p>
      {:else}
        <div class="grid gap-3 sm:grid-cols-2">
          <div class="sm:col-span-2">
            <label class="label">Date <span class="text-red-500">*</span></label>
            <select bind:value={rf.calendarId} class="input">
              <option value="">Select date…</option>
              {#each schoolDays as d}
                <option value={d.id}>{d.date}{d.date === today ? ' (today)' : ''}</option>
              {/each}
            </select>
          </div>
          <div>
            <label class="label">Students expected <span class="text-red-500">*</span></label>
            <input type="number" min="0" bind:value={rf.expected} placeholder="e.g. 45" class="input" />
          </div>
          <div>
            <label class="label">Students present <span class="text-red-500">*</span></label>
            <input type="number" min="0" bind:value={rf.present} placeholder="e.g. 43" class="input" />
          </div>
          <div class="sm:col-span-2">
            <label class="label">Notes</label>
            <textarea bind:value={rf.notes} rows="2" placeholder="Any absences or remarks…" class="input resize-none"></textarea>
          </div>
        </div>
        {#if rfErr}<p class="mt-2 text-xs text-red-500">{rfErr}</p>{/if}
        <div class="mt-3 flex gap-2">
          <button onclick={handleRecord} disabled={$recordMut.isPending}
            class="rounded-xl px-4 py-2 text-sm font-semibold text-white transition hover:opacity-90 disabled:opacity-50"
            style="background:var(--brand)">
            {$recordMut.isPending ? 'Saving…' : 'Record'}
          </button>
          <button onclick={() => showForm = false}
            class="rounded-xl border border-[var(--border)] px-4 py-2 text-sm text-[var(--fg-muted)] hover:bg-[var(--hover)] transition">
            Cancel
          </button>
        </div>
      {/if}
    </div>
  {/if}

  <!-- Roll call history -->
  {#if $rollsQ.isPending}
    <div class="space-y-2">{#each [1,2,3] as _}<div class="h-14 animate-pulse rounded-2xl bg-[var(--card)]"></div>{/each}</div>
  {:else if ($rollsQ.data ?? []).length === 0}
    <div class="rounded-2xl border border-dashed border-[var(--border)] p-10 text-center">
      <p class="text-sm text-[var(--fg-muted)]">No roll calls recorded yet.</p>
    </div>
  {:else}
    <div class="overflow-hidden rounded-2xl border border-[var(--border)] bg-[var(--card)]">
      <table class="w-full text-sm">
        <thead><tr class="border-b border-[var(--border)] text-left text-[10px] font-semibold uppercase tracking-widest text-[var(--fg-subtle)]">
          <th class="px-4 py-3">Recorded</th>
          <th class="px-4 py-3 text-center">Expected</th>
          <th class="px-4 py-3 text-center">Present</th>
          <th class="px-4 py-3 text-center">Absent</th>
          <th class="hidden px-4 py-3 sm:table-cell">Notes</th>
        </tr></thead>
        <tbody>
          {#each $rollsQ.data ?? [] as rc (rc.id)}
            {@const absent = rc.total_expected - rc.total_present}
            <tr class="border-b border-[var(--border)] last:border-0 hover:bg-[var(--hover)] transition">
              <td class="px-4 py-3 text-xs text-[var(--fg-muted)]">{fmt(rc.recorded_at)}</td>
              <td class="px-4 py-3 text-center font-mono text-[var(--fg)]">{rc.total_expected}</td>
              <td class="px-4 py-3 text-center font-mono text-green-600 dark:text-green-400">{rc.total_present}</td>
              <td class="px-4 py-3 text-center font-mono {absent > 0 ? 'text-red-600 dark:text-red-400 font-semibold' : 'text-[var(--fg-muted)]'}">
                {absent}
              </td>
              <td class="hidden px-4 py-3 text-xs text-[var(--fg-muted)] sm:table-cell">{rc.notes ?? '—'}</td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  {/if}
</div>

<style>
  @reference "tailwindcss";
  .label { @apply block text-xs font-medium text-[var(--fg-muted)] mb-1; }
  .input  { @apply w-full rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm
                   text-[var(--fg)] placeholder:text-[var(--fg-subtle)] focus:border-[var(--brand)]
                   focus:outline-none transition; }
</style>
