<script lang="ts">
  import { createQuery, createMutation, useQueryClient } from '@tanstack/svelte-query';
  import { listConflicts, resolveConflict, type SyncConflict, type ConflictResolution, type ScoreData } from '$lib/api/sync';
  import { getAssessment } from '$lib/api/assessments';
  import { getStudent } from '$lib/api/students';
  import { toast } from '$lib/stores/toast';

  const qc = useQueryClient();

  // Load conflicts + enrich with assessment/student names in one query
  const conflictsQ = createQuery({
    queryKey: ['sync-conflicts'],
    queryFn: async () => {
      const conflicts = await listConflicts();
      if (!conflicts.length) return [];
      const assessmentIds = [...new Set(conflicts.map(c => c.client_data.assessment_id))];
      const studentIds    = [...new Set(conflicts.map(c => c.client_data.student_id))];
      const [assessments, students] = await Promise.all([
        Promise.all(assessmentIds.map(id => getAssessment(id).catch(() => null))),
        Promise.all(studentIds.map(id => getStudent(id).catch(() => null))),
      ]);
      const aMap = new Map(assessments.filter(Boolean).map(a => [a!.id, a!]));
      const sMap = new Map(students.filter(Boolean).map(s => [s!.id, s!]));
      return conflicts.map(c => ({
        ...c,
        assessment: aMap.get(c.client_data.assessment_id) ?? null,
        student:    sMap.get(c.client_data.student_id) ?? null,
      }));
    },
    staleTime: 30_000,
  });

  type EnrichedConflict = SyncConflict & {
    assessment: { id: string; name: string; max_score: number } | null;
    student: { id: string; display_name: string; admission_number: string } | null;
  };

  const conflicts = $derived(($conflictsQ.data ?? []) as EnrichedConflict[]);

  // Per-conflict UI state
  let resolving   = $state<Record<string, ConflictResolution | null>>({});
  let mergeInputs = $state<Record<string, string>>({});

  function setAction(id: string, action: ConflictResolution | null) {
    resolving   = { ...resolving,   [id]: action };
    mergeInputs = { ...mergeInputs, [id]: '' };
  }

  const resolveMut = createMutation({
    mutationFn: ({ id, resolution, mergedData }: {
      id: string;
      resolution: ConflictResolution;
      mergedData?: ScoreData;
    }) => resolveConflict(id, resolution, mergedData),
    onSuccess: (_, vars) => {
      qc.invalidateQueries({ queryKey: ['sync-conflicts'] });
      qc.invalidateQueries({ queryKey: ['scores'] });
      setAction(vars.id, null);
      toast.success(
        vars.resolution === 'CLIENT_WINS' ? 'Your score applied.' :
        vars.resolution === 'SERVER_WINS' ? 'Server score kept.' :
        vars.resolution === 'MERGED'      ? 'Custom score applied.' :
                                            'Conflict discarded.',
      );
    },
    onError: (e: unknown) => toast.error(
      (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? 'Could not resolve.'
    ),
  });

  function resolve(conflict: EnrichedConflict, resolution: ConflictResolution) {
    let mergedData: ScoreData | undefined;
    if (resolution === 'MERGED') {
      const val = parseFloat(mergeInputs[conflict.id] ?? '');
      if (isNaN(val)) { toast.error('Enter a valid score.'); return; }
      if (conflict.assessment && (val < 0 || val > conflict.assessment.max_score)) {
        toast.error(`Score must be 0–${conflict.assessment.max_score}.`); return;
      }
      mergedData = { ...conflict.client_data, raw_score: val };
    }
    $resolveMut.mutate({ id: conflict.id, resolution, mergedData });
  }

  function fmt(d: string) {
    return new Date(d).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' });
  }
</script>

<div class="mx-auto max-w-2xl px-4 py-8">
  <!-- Header -->
  <div class="mb-6">
    <h1 class="text-xl font-bold text-[var(--fg)]">Sync Conflicts</h1>
    <p class="mt-0.5 text-sm text-[var(--fg-muted)]">
      Review scores that conflicted when your offline changes synced with the server.
    </p>
  </div>

  {#if $conflictsQ.isPending}
    <div class="space-y-4">
      {#each [1,2] as _}
        <div class="h-48 animate-pulse rounded-2xl bg-[var(--card)]"></div>
      {/each}
    </div>

  {:else if conflicts.length === 0}
    <div class="rounded-2xl border border-[var(--border)] bg-[var(--card)] px-6 py-16 text-center">
      <svg class="mx-auto mb-4 h-12 w-12 text-emerald-500" fill="none" stroke="currentColor" stroke-width="1.5" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
      </svg>
      <p class="text-base font-semibold text-[var(--fg)]">All clear — no sync conflicts</p>
      <p class="mt-1 text-sm text-[var(--fg-muted)]">Your offline changes synced without any conflicts.</p>
    </div>

  {:else}
    <p class="mb-4 text-xs text-[var(--fg-subtle)]">{conflicts.length} unresolved conflict{conflicts.length !== 1 ? 's' : ''}</p>
    <div class="space-y-4">
      {#each conflicts as c (c.id)}
        {@const action = resolving[c.id] ?? null}
        {@const isPending = $resolveMut.isPending && ($resolveMut.variables as { id: string })?.id === c.id}

        <div class="overflow-hidden rounded-2xl border border-amber-300 bg-[var(--card)] dark:border-amber-800/60">
          <!-- Card header -->
          <div class="flex items-start justify-between border-b border-[var(--border)] bg-amber-50 px-5 py-3 dark:bg-amber-950/20">
            <div>
              <span class="rounded-full bg-amber-200 px-2 py-0.5 text-[10px] font-bold uppercase tracking-widest text-amber-800 dark:bg-amber-800/40 dark:text-amber-300">
                Score conflict
              </span>
              <p class="mt-1.5 font-semibold text-[var(--fg)]">
                {c.assessment?.name ?? 'Assessment'}
              </p>
              <p class="text-sm text-[var(--fg-muted)]">
                {c.student?.display_name ?? 'Student'}
                {#if c.student?.admission_number}
                  <span class="font-mono text-[var(--fg-subtle)]"> · {c.student.admission_number}</span>
                {/if}
              </p>
            </div>
            <span class="shrink-0 text-[10px] text-[var(--fg-subtle)]">{fmt(c.created_at)}</span>
          </div>

          <!-- Score comparison -->
          <div class="grid grid-cols-2 divide-x divide-[var(--border)] px-0 py-0">
            <div class="p-5">
              <p class="mb-1 text-[10px] font-semibold uppercase tracking-widest text-[var(--fg-subtle)]">Your offline score</p>
              <p class="text-4xl font-bold" style="color: var(--brand)">{c.client_data.raw_score}</p>
              {#if c.assessment}
                <p class="mt-0.5 text-xs text-[var(--fg-muted)]">out of {c.assessment.max_score}</p>
              {/if}
            </div>
            <div class="p-5">
              <p class="mb-1 text-[10px] font-semibold uppercase tracking-widest text-[var(--fg-subtle)]">Server score (newer)</p>
              <p class="text-4xl font-bold text-[var(--fg)]">{c.server_data.raw_score}</p>
              {#if c.assessment}
                <p class="mt-0.5 text-xs text-[var(--fg-muted)]">out of {c.assessment.max_score}</p>
              {/if}
            </div>
          </div>

          <!-- Custom score input (MERGED) -->
          {#if action === 'MERGED'}
            <div class="border-t border-[var(--border)] px-5 py-3">
              <label class="mb-1 block text-xs font-medium text-[var(--fg-muted)]">
                Custom score {c.assessment ? `(0–${c.assessment.max_score})` : ''}
              </label>
              <input
                type="number"
                min="0"
                max={c.assessment?.max_score ?? undefined}
                step="0.5"
                bind:value={mergeInputs[c.id]}
                placeholder="Enter score…"
                class="w-36 rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--fg)] focus:border-[var(--brand)] focus:outline-none transition"
              />
            </div>
          {/if}

          <!-- Actions -->
          <div class="flex flex-wrap items-center gap-2 border-t border-[var(--border)] px-5 py-3">
            {#if action === null}
              <button onclick={() => setAction(c.id, 'CLIENT_WINS')}
                class="rounded-xl bg-emerald-600 px-3 py-1.5 text-xs font-semibold text-white transition hover:opacity-90">
                Use mine ({c.client_data.raw_score})
              </button>
              <button onclick={() => setAction(c.id, 'SERVER_WINS')}
                class="rounded-xl border border-[var(--border)] px-3 py-1.5 text-xs font-semibold text-[var(--fg)] transition hover:bg-[var(--hover)]">
                Keep server's ({c.server_data.raw_score})
              </button>
              <button onclick={() => setAction(c.id, 'MERGED')}
                class="rounded-xl border border-amber-300 px-3 py-1.5 text-xs font-semibold text-amber-700 transition hover:bg-amber-50 dark:border-amber-700 dark:text-amber-400 dark:hover:bg-amber-950/20">
                Custom score…
              </button>
              <button onclick={() => setAction(c.id, 'DISCARDED')}
                class="ml-auto rounded-xl px-3 py-1.5 text-xs text-[var(--fg-subtle)] transition hover:text-red-500">
                Discard
              </button>
            {:else}
              <!-- Confirmation row -->
              <span class="text-xs text-[var(--fg-muted)]">
                {action === 'CLIENT_WINS' ? `Apply your score (${c.client_data.raw_score})?` :
                 action === 'SERVER_WINS' ? `Keep server's score (${c.server_data.raw_score})?` :
                 action === 'MERGED'      ? 'Apply this custom score?' :
                                            'Discard this conflict (no score change)?'}
              </span>
              <div class="ml-auto flex gap-2">
                <button onclick={() => setAction(c.id, null)}
                  class="rounded-xl border border-[var(--border)] px-3 py-1.5 text-xs text-[var(--fg-muted)] hover:bg-[var(--hover)] transition">
                  Cancel
                </button>
                <button onclick={() => resolve(c, action)}
                  disabled={isPending}
                  class="rounded-xl px-3 py-1.5 text-xs font-semibold text-white transition hover:opacity-90 disabled:opacity-50"
                  style="background: {action === 'DISCARDED' ? '#dc2626' : 'var(--brand)'}">
                  {isPending ? 'Applying…' : 'Confirm'}
                </button>
              </div>
            {/if}
          </div>
        </div>
      {/each}
    </div>
  {/if}
</div>
