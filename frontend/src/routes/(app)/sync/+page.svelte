<script lang="ts">
  import { onMount } from 'svelte';
  import { createQuery, useQueryClient } from '@tanstack/svelte-query';
  import { listConflicts, type SyncConflict } from '$lib/api/sync';
  import { getAssessment, listAssessmentTypes, type Assessment } from '$lib/api/assessments';
  import { getStudent } from '$lib/api/students';
  import { getPendingItems, type OutboxItem } from '$lib/offline/outbox';
  import { drainOutbox, refreshOutboxCount } from '$lib/offline/sync';
  import SyncConflictCard from './SyncConflictCard.svelte';

  const qc = useQueryClient();

  // ── Pending outbox (local Dexie) ──────────────────────────────────────────
  let pending        = $state<OutboxItem[]>([]);
  let pendingLoading = $state(true);
  let syncing        = $state(false);

  async function loadPending() {
    pending = await getPendingItems();
    pendingLoading = false;
  }

  async function syncNow() {
    syncing = true;
    await drainOutbox();
    await loadPending();
    await refreshOutboxCount();
    qc.invalidateQueries({ queryKey: ['sync-conflicts'] });
    syncing = false;
  }

  onMount(loadPending);

  // ── Server conflicts ───────────────────────────────────────────────────────
  const typesQ = createQuery({ queryKey: ['assessment-types'], queryFn: listAssessmentTypes, staleTime: 5 * 60_000 });
  const typeName = (id: string) => ($typesQ.data ?? []).find(t => t.id === id)?.name ?? '—';

  const conflictsQ = createQuery({
    queryKey: ['sync-conflicts'],
    queryFn: async () => {
      const conflicts = await listConflicts();
      if (!conflicts.length) return [];
      const scoreConflicts = conflicts.filter(c => c.entity_type !== 'attendance');
      const assessmentIds  = [...new Set(scoreConflicts.map(c => c.client_data.assessment_id as string))];
      const studentIds     = [...new Set(conflicts.map(c => c.client_data.student_id as string))];
      const [assessments, students] = await Promise.all([
        Promise.all(assessmentIds.map(id => getAssessment(id).catch(() => null))),
        Promise.all(studentIds.map(id => getStudent(id).catch(() => null))),
      ]);
      const aMap = new Map(assessments.filter(Boolean).map(a => [a!.id, a!]));
      const sMap = new Map(students.filter(Boolean).map(s => [s!.id, s!]));
      return conflicts.map(c => ({
        ...c,
        assessment: c.entity_type !== 'attendance'
          ? (aMap.get(c.client_data.assessment_id as string) ?? null) : null,
        typeName: c.entity_type !== 'attendance'
          ? typeName(aMap.get(c.client_data.assessment_id as string)?.assessment_type_id ?? '') : '',
        student: sMap.get(c.client_data.student_id as string) ?? null,
      }));
    },
    staleTime: 30_000,
  });

  type EnrichedConflict = SyncConflict & {
    assessment: Assessment | null;
    typeName: string;
    student: { id: string; display_name: string; admission_number: string } | null;
  };

  const conflicts = $derived(($conflictsQ.data ?? []) as EnrichedConflict[]);

  function fmtTime(ts: number) {
    return new Date(ts).toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' });
  }
</script>

<div class="mx-auto max-w-2xl px-4 py-8">
  <div class="mb-6">
    <h1 class="text-xl font-bold text-[var(--fg)]">Sync</h1>
    <p class="mt-0.5 text-sm text-[var(--fg-muted)]">
      Offline scores and attendance waiting to upload, and any conflicts to resolve.
    </p>
  </div>

  <!-- Pending outbox -->
  {#if pendingLoading}
    <div class="mb-6 h-20 animate-pulse rounded-2xl bg-[var(--card)]"></div>
  {:else if pending.length > 0}
    <div class="mb-6 rounded-2xl border border-amber-300 bg-amber-50 px-5 py-4
                dark:border-amber-800/60 dark:bg-amber-950/20">
      <div class="flex items-center justify-between gap-3">
        <div>
          <p class="font-semibold text-amber-800 dark:text-amber-300">
            {pending.length} item{pending.length !== 1 ? 's' : ''} queued offline
          </p>
          <p class="mt-0.5 text-xs text-amber-700/70 dark:text-amber-400/70">
            Sync now or they will upload automatically when you reconnect.
          </p>
        </div>
        <button onclick={syncNow} disabled={syncing}
          class="min-h-[44px] shrink-0 rounded-xl bg-amber-600 px-4 py-2 text-xs font-semibold text-white
                 transition hover:bg-amber-700 disabled:opacity-50">
          {syncing ? 'Syncing…' : 'Sync now'}
        </button>
      </div>
      <ul class="mt-3 space-y-1.5">
        {#each pending as item (item.id)}
          <li class="flex items-center gap-2 text-xs text-amber-800 dark:text-amber-300">
            <span class="h-1.5 w-1.5 rounded-full bg-amber-500"></span>
            {#if item.entity === 'Attendance'}
              {@const status = (item.payload as { status?: string }).status}
              Attendance <span class="font-semibold">{status ?? '?'}</span> — queued at {fmtTime(item.created_at)}
            {:else}
              {@const score = (item.payload as { raw_score?: number }).raw_score}
              Score <span class="font-semibold">{score ?? '?'}</span> — queued at {fmtTime(item.created_at)}
            {/if}
          </li>
        {/each}
      </ul>
    </div>
  {/if}

  <!-- Server conflicts -->
  {#if $conflictsQ.isPending}
    <div class="space-y-4">
      {#each [1, 2] as _}
        <div class="h-48 animate-pulse rounded-2xl bg-[var(--card)]"></div>
      {/each}
    </div>

  {:else if conflicts.length === 0 && pending.length === 0}
    <div class="rounded-2xl border border-[var(--border)] bg-[var(--card)] px-6 py-16 text-center">
      <svg class="mx-auto mb-4 h-12 w-12 text-emerald-500" fill="none" stroke="currentColor" stroke-width="1.5" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
      </svg>
      <p class="text-base font-semibold text-[var(--fg)]">All clear — nothing to sync</p>
      <p class="mt-1 text-sm text-[var(--fg-muted)]">Your offline changes synced without any conflicts.</p>
    </div>

  {:else if conflicts.length > 0}
    <p class="mb-4 text-xs text-[var(--fg-subtle)]">
      {conflicts.length} unresolved conflict{conflicts.length !== 1 ? 's' : ''}
    </p>
    <div class="space-y-4">
      {#each conflicts as c (c.id)}
        <SyncConflictCard conflict={c} />
      {/each}
    </div>
  {/if}
</div>
