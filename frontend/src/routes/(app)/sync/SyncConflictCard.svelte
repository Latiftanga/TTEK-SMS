<script lang="ts">
  import { createMutation, useQueryClient } from '@tanstack/svelte-query';
  import { resolveConflict, type SyncConflict, type ConflictResolution, type ScoreData, type AttendanceData } from '$lib/api/sync';
  import { assessmentLabel, type Assessment } from '$lib/api/assessments';
  import { toast } from '$lib/stores/toast';

  interface EnrichedConflict extends SyncConflict {
    assessment: Assessment | null;
    typeName: string;
    student: { id: string; display_name: string; admission_number: string } | null;
  }

  interface Props { conflict: EnrichedConflict; }
  const { conflict: c }: Props = $props();

  const qc = useQueryClient();
  const isAttendance = $derived(c.entity_type === 'attendance');

  let action = $state<ConflictResolution | null>(null);
  let mergeInput = $state('');

  const resolveMut = createMutation({
    mutationFn: ({ resolution, mergedData }: { resolution: ConflictResolution; mergedData?: ScoreData | AttendanceData }) =>
      resolveConflict(c.id, resolution, mergedData),
    onSuccess: (_, vars) => {
      qc.invalidateQueries({ queryKey: ['sync-conflicts'] });
      qc.invalidateQueries({ queryKey: isAttendance ? ['att-records'] : ['scores'] });
      action = null;
      toast.success(
        vars.resolution === 'CLIENT_WINS' ? 'Your version applied.' :
        vars.resolution === 'SERVER_WINS' ? "Server's version kept." :
        vars.resolution === 'MERGED'      ? 'Custom score applied.' : 'Conflict discarded.',
      );
    },
    onError: (e: unknown) => toast.error(
      (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? 'Could not resolve.'
    ),
  });

  function resolve(resolution: ConflictResolution) {
    let mergedData: ScoreData | AttendanceData | undefined;
    if (resolution === 'MERGED' && !isAttendance) {
      const val = parseFloat(mergeInput);
      if (isNaN(val)) { toast.error('Enter a valid score.'); return; }
      if (c.assessment && (val < 0 || val > c.assessment.max_score)) {
        toast.error(`Score must be 0–${c.assessment.max_score}.`); return;
      }
      mergedData = { ...(c.client_data as unknown as ScoreData), raw_score: val };
    }
    $resolveMut.mutate({ resolution, mergedData });
  }

  function fmt(d: string) {
    return new Date(d).toLocaleDateString('en-GB', {
      day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit',
    });
  }
</script>

<div class="overflow-hidden rounded-2xl border border-amber-300 bg-[var(--card)] dark:border-amber-800/60">
  <div class="flex items-start justify-between border-b border-[var(--border)] bg-amber-50 px-5 py-3 dark:bg-amber-950/20">
    <div>
      <span class="rounded-full bg-amber-200 px-2 py-0.5 text-[10px] font-bold uppercase tracking-widest text-amber-800 dark:bg-amber-800/40 dark:text-amber-300">
        {isAttendance ? 'Attendance conflict' : 'Score conflict'}
      </span>
      {#if !isAttendance}
        <p class="mt-1.5 font-semibold text-[var(--fg)]">{c.assessment ? assessmentLabel(c.assessment, c.typeName) : 'Assessment'}</p>
      {/if}
      <p class="mt-1.5 text-sm text-[var(--fg-muted)]">
        {c.student?.display_name ?? 'Student'}
        {#if c.student?.admission_number}
          <span class="font-mono text-[var(--fg-subtle)]"> · {c.student.admission_number}</span>
        {/if}
      </p>
    </div>
    <span class="shrink-0 text-[10px] text-[var(--fg-subtle)]">{fmt(c.created_at)}</span>
  </div>

  <div class="grid grid-cols-2 divide-x divide-[var(--border)]">
    <div class="p-5">
      <p class="mb-1 text-[10px] font-semibold uppercase tracking-widest text-[var(--fg-subtle)]">
        Your offline {isAttendance ? 'status' : 'score'}
      </p>
      {#if isAttendance}
        <p class="text-2xl font-bold" style="color: var(--brand)">{c.client_data.status}</p>
      {:else}
        <p class="text-4xl font-bold" style="color: var(--brand)">{c.client_data.raw_score}</p>
        {#if c.assessment}<p class="mt-0.5 text-xs text-[var(--fg-muted)]">out of {c.assessment.max_score}</p>{/if}
      {/if}
    </div>
    <div class="p-5">
      <p class="mb-1 text-[10px] font-semibold uppercase tracking-widest text-[var(--fg-subtle)]">
        Server {isAttendance ? 'status' : 'score'} (newer)
      </p>
      {#if isAttendance}
        <p class="text-2xl font-bold text-[var(--fg)]">{c.server_data.status}</p>
      {:else}
        <p class="text-4xl font-bold text-[var(--fg)]">{c.server_data.raw_score}</p>
        {#if c.assessment}<p class="mt-0.5 text-xs text-[var(--fg-muted)]">out of {c.assessment.max_score}</p>{/if}
      {/if}
    </div>
  </div>

  {#if action === 'MERGED' && !isAttendance}
    <div class="border-t border-[var(--border)] px-5 py-3">
      <label for="merge-score-{c.id}" class="mb-1 block text-xs font-medium text-[var(--fg-muted)]">
        Custom score {c.assessment ? `(0–${c.assessment.max_score})` : ''}
      </label>
      <input id="merge-score-{c.id}" type="number" inputmode="decimal" min="0" max={c.assessment?.max_score ?? undefined} step="0.5"
        bind:value={mergeInput} placeholder="Enter score…"
        class="min-h-[44px] w-36 rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm
               text-[var(--fg)] transition focus:border-[var(--brand)] focus:outline-none" />
    </div>
  {/if}

  <div class="flex flex-wrap items-center gap-2 border-t border-[var(--border)] px-5 py-3">
    {#if action === null}
      <button onclick={() => action = 'CLIENT_WINS'}
        class="min-h-[44px] rounded-xl bg-emerald-600 px-3 py-1.5 text-xs font-semibold text-white transition hover:opacity-90">
        Use mine ({isAttendance ? c.client_data.status : c.client_data.raw_score})
      </button>
      <button onclick={() => action = 'SERVER_WINS'}
        class="min-h-[44px] rounded-xl border border-[var(--border)] px-3 py-1.5 text-xs font-semibold text-[var(--fg)] transition hover:bg-[var(--hover)]">
        Keep server's ({isAttendance ? c.server_data.status : c.server_data.raw_score})
      </button>
      {#if !isAttendance}
        <button onclick={() => action = 'MERGED'}
          class="min-h-[44px] rounded-xl border border-amber-300 px-3 py-1.5 text-xs font-semibold text-amber-700 transition hover:bg-amber-50 dark:border-amber-700 dark:text-amber-400 dark:hover:bg-amber-950/20">
          Custom score…
        </button>
      {/if}
      <button onclick={() => action = 'DISCARDED'}
        class="ml-auto min-h-[44px] rounded-xl px-3 py-1.5 text-xs text-[var(--fg-subtle)] transition hover:text-red-500">
        Discard
      </button>
    {:else}
      <span class="text-xs text-[var(--fg-muted)]">
        {action === 'CLIENT_WINS' ? `Apply your ${isAttendance ? 'status' : 'score'} (${isAttendance ? c.client_data.status : c.client_data.raw_score})?` :
         action === 'SERVER_WINS' ? `Keep server's ${isAttendance ? 'status' : 'score'} (${isAttendance ? c.server_data.status : c.server_data.raw_score})?` :
         action === 'MERGED'      ? 'Apply this custom score?' :
                                    'Discard this conflict (no change)?'}
      </span>
      <div class="ml-auto flex gap-2">
        <button onclick={() => action = null}
          class="min-h-[44px] rounded-xl border border-[var(--border)] px-3 py-1.5 text-xs text-[var(--fg-muted)] transition hover:bg-[var(--hover)]">
          Cancel
        </button>
        <button onclick={() => resolve(action!)} disabled={$resolveMut.isPending}
          class="min-h-[44px] rounded-xl px-3 py-1.5 text-xs font-semibold text-white transition hover:opacity-90 disabled:opacity-50"
          style="background: {action === 'DISCARDED' ? '#dc2626' : 'var(--brand)'}">
          {$resolveMut.isPending ? 'Applying…' : 'Confirm'}
        </button>
      </div>
    {/if}
  </div>
</div>
