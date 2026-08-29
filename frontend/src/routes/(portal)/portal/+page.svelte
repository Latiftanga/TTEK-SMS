<script lang="ts">
  import { reactiveQuery } from '$lib/query.svelte';
  import {
    getMyPortalProfile, listMyChildren, listMyTermEnrollments, getMyReportCardBlob,
    type PortalProfile, type PortalTermEnrollment,
  } from '$lib/api/portal';
  import { currentUser } from '$lib/stores/auth';
  import { ghs } from '$lib/api/fees';
  import { toast } from '$lib/stores/toast';
  import { setPageTitle } from '$lib/stores/title';
  import ExcuseRequestPanel from './ExcuseRequestPanel.svelte';

  setPageTitle('My Portal');

  // $currentUser hydrates asynchronously after mount (root layout's getMe() call),
  // so isGuardian isn't known at first render — both queries below use
  // reactiveQuery() rather than a plain createQuery({...}) object so `enabled`
  // re-evaluates once the user store actually populates.
  const isGuardian = $derived(!!$currentUser?.guardian_id);

  const profileQ = reactiveQuery(() => ({
    queryKey: ['portal-me'] as const,
    queryFn:  getMyPortalProfile,
    enabled:  !!$currentUser && !isGuardian,
    staleTime: 5 * 60_000,
  }));
  const childrenQ = reactiveQuery(() => ({
    queryKey: ['portal-children'] as const,
    queryFn:  listMyChildren,
    enabled:  isGuardian,
    staleTime: 5 * 60_000,
  }));

  let selectedChildId = $state<string | null>(null);
  $effect(() => {
    if (isGuardian && !selectedChildId && ($childrenQ.data?.length ?? 0) > 0) {
      selectedChildId = $childrenQ.data![0].student_id;
    }
  });

  const activeProfile = $derived<PortalProfile | undefined>(
    isGuardian ? $childrenQ.data?.find(c => c.student_id === selectedChildId) : $profileQ.data
  );

  const termsQ = reactiveQuery(() => ({
    queryKey: ['portal-term-enrollments', isGuardian ? selectedChildId : 'self'] as const,
    queryFn:  () => listMyTermEnrollments(isGuardian ? selectedChildId! : undefined),
    enabled:  isGuardian ? !!selectedChildId : true,
    staleTime: 60_000,
  }));

  let downloading = $state<Set<string>>(new Set());

  async function viewReportCard(enrollment: PortalTermEnrollment) {
    if (downloading.has(enrollment.id)) return;
    downloading = new Set([...downloading, enrollment.id]);
    try {
      const blob = await getMyReportCardBlob(enrollment.id, isGuardian ? selectedChildId ?? undefined : undefined);
      const url = URL.createObjectURL(blob);
      window.open(url, '_blank');
      setTimeout(() => URL.revokeObjectURL(url), 30_000);
    } catch {
      toast.error('Could not open the report card. Try again in a moment.');
    } finally {
      downloading = new Set([...downloading].filter(id => id !== enrollment.id));
    }
  }

  const loading = $derived(isGuardian ? $childrenQ.isPending || $termsQ.isPending : $profileQ.isPending || $termsQ.isPending);
  const forbidden = $derived(
    ($profileQ.error as { response?: { status?: number } })?.response?.status === 403
    || ($childrenQ.error as { response?: { status?: number } })?.response?.status === 403
    || ($termsQ.error as { response?: { status?: number } })?.response?.status === 403
  );
  const noChildren = $derived(isGuardian && !$childrenQ.isPending && ($childrenQ.data?.length ?? 0) === 0);
</script>

{#if loading}
  <div class="space-y-4">
    <div class="h-24 animate-pulse rounded-2xl bg-[var(--card)]"></div>
    <div class="h-16 animate-pulse rounded-2xl bg-[var(--card)]"></div>
    <div class="h-16 animate-pulse rounded-2xl bg-[var(--card)]"></div>
  </div>

{:else if forbidden}
  <div class="rounded-2xl border border-red-100 bg-red-50 p-6 text-sm text-red-700 dark:border-red-900 dark:bg-red-950/40 dark:text-red-400">
    This portal is only available to student and parent accounts. If you're a staff member, use the main app instead.
  </div>

{:else if noChildren}
  <div class="rounded-2xl border border-dashed border-[var(--border)] p-6 text-center text-sm text-[var(--fg-muted)]">
    No children are linked to this account yet.
  </div>

{:else if $profileQ.isError || $childrenQ.isError || $termsQ.isError}
  <div class="rounded-2xl border border-red-100 bg-red-50 p-6 text-sm text-red-700 dark:border-red-900 dark:bg-red-950/40 dark:text-red-400">
    Could not load your portal. Please try again shortly.
  </div>

{:else if activeProfile}
  {@const profile = activeProfile}
  {@const terms = $termsQ.data ?? []}

  <!-- Child switcher (guardian accounts with 2+ children only) -->
  {#if isGuardian && ($childrenQ.data?.length ?? 0) > 1}
    <div class="mb-4 flex gap-2 overflow-x-auto overflow-y-hidden pb-1">
      {#each $childrenQ.data ?? [] as child (child.student_id)}
        <button onclick={() => selectedChildId = child.student_id}
          class="shrink-0 rounded-xl border px-3 py-1.5 text-xs font-semibold transition
                 {selectedChildId === child.student_id
                   ? 'border-transparent text-white'
                   : 'border-[var(--border)] text-[var(--fg-muted)] hover:bg-[var(--hover)]'}"
          style={selectedChildId === child.student_id ? 'background: var(--brand)' : ''}>
          {child.display_name}
        </button>
      {/each}
    </div>
  {/if}

  <!-- Profile card -->
  <div class="mb-6 rounded-2xl border border-[var(--border)] bg-[var(--card)] p-6">
    <div class="flex items-center gap-4">
      <div class="flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl text-lg font-bold text-white"
           style="background: linear-gradient(135deg, var(--brand) 0%, color-mix(in oklab, var(--brand) 65%, #7c3aed) 100%)">
        {profile.display_name.split(' ').filter(Boolean).slice(0, 2).map(p => p[0]).join('').toUpperCase()}
      </div>
      <div>
        <h1 class="text-lg font-bold text-[var(--fg)]">{profile.display_name}</h1>
        <p class="mt-0.5 font-mono text-xs text-[var(--fg-muted)]">{profile.admission_number}</p>
        {#if profile.current_class_name}
          <p class="mt-1 text-xs text-[var(--fg-muted)]">{profile.current_class_name}</p>
        {/if}
      </div>
    </div>
  </div>

  <!-- Terms -->
  <h2 class="mb-3 text-xs font-semibold uppercase tracking-widest text-[var(--fg-subtle)]">Report cards &amp; fees</h2>

  {#if terms.length === 0}
    <div class="rounded-2xl border border-dashed border-[var(--border)] p-6 text-center text-sm text-[var(--fg-muted)]">
      No term registrations yet.
    </div>
  {:else}
    <div class="space-y-2">
      {#each terms as term (term.id)}
        <div class="flex items-center justify-between rounded-2xl border border-[var(--border)] bg-[var(--card)] px-5 py-4">
          <div>
            <div class="flex items-center gap-2">
              <span class="text-sm font-semibold text-[var(--fg)]">{term.term_name}</span>
              {#if term.is_current}
                <span class="badge badge-success">Current</span>
              {/if}
            </div>
            <p class="text-xs text-[var(--fg-muted)]">{term.academic_year_name}</p>
            {#if term.fee_balance !== null}
              <p class="mt-1 text-xs font-semibold {Number(term.fee_balance) > 0 ? 'text-red-600 dark:text-red-400' : 'text-green-600 dark:text-green-500'}">
                {Number(term.fee_balance) > 0 ? `Balance due: ${ghs(term.fee_balance)}` : 'Fees fully paid'}
              </p>
            {/if}
          </div>

          {#if term.is_published}
            <button onclick={() => viewReportCard(term)} disabled={downloading.has(term.id)}
              class="rounded-xl px-4 py-2 text-sm font-semibold text-white transition hover:opacity-90 disabled:opacity-50"
              style="background: var(--brand)">
              {downloading.has(term.id) ? 'Opening…' : 'View report card'}
            </button>
          {:else}
            <span class="rounded-full bg-[var(--hover)] px-3 py-1.5 text-xs font-medium text-[var(--fg-muted)]">
              Not yet published
            </span>
          {/if}
        </div>
      {/each}
    </div>
  {/if}

  <ExcuseRequestPanel studentId={isGuardian ? selectedChildId ?? undefined : undefined} />
{/if}
