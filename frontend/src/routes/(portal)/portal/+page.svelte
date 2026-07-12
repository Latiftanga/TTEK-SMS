<script lang="ts">
  import { createQuery } from '@tanstack/svelte-query';
  import {
    getMyPortalProfile, listMyTermEnrollments, getMyReportCardBlob,
    type PortalTermEnrollment,
  } from '$lib/api/portal';
  import { toast } from '$lib/stores/toast';
  import { setPageTitle } from '$lib/stores/title';

  setPageTitle('My Report Cards');

  const profileQ = createQuery({ queryKey: ['portal-me'], queryFn: getMyPortalProfile, staleTime: 5 * 60_000 });
  const termsQ   = createQuery({ queryKey: ['portal-term-enrollments'], queryFn: listMyTermEnrollments, staleTime: 60_000 });

  let downloading = $state<Set<string>>(new Set());

  async function viewReportCard(enrollment: PortalTermEnrollment) {
    if (downloading.has(enrollment.id)) return;
    downloading = new Set([...downloading, enrollment.id]);
    try {
      const blob = await getMyReportCardBlob(enrollment.id);
      const url = URL.createObjectURL(blob);
      window.open(url, '_blank');
      setTimeout(() => URL.revokeObjectURL(url), 30_000);
    } catch {
      toast.error('Could not open the report card. Try again in a moment.');
    } finally {
      downloading = new Set([...downloading].filter(id => id !== enrollment.id));
    }
  }

  const forbidden = $derived(
    ($profileQ.error as { response?: { status?: number } })?.response?.status === 403
    || ($termsQ.error as { response?: { status?: number } })?.response?.status === 403
  );
</script>

{#if $profileQ.isPending || $termsQ.isPending}
  <div class="space-y-4">
    <div class="h-24 animate-pulse rounded-2xl bg-[var(--card)]"></div>
    <div class="h-16 animate-pulse rounded-2xl bg-[var(--card)]"></div>
    <div class="h-16 animate-pulse rounded-2xl bg-[var(--card)]"></div>
  </div>

{:else if forbidden}
  <div class="rounded-2xl border border-red-100 bg-red-50 p-6 text-sm text-red-700 dark:border-red-900 dark:bg-red-950/40 dark:text-red-400">
    This portal is only available to student accounts. If you're a staff member, use the main app instead.
  </div>

{:else if $profileQ.isError || $termsQ.isError}
  <div class="rounded-2xl border border-red-100 bg-red-50 p-6 text-sm text-red-700 dark:border-red-900 dark:bg-red-950/40 dark:text-red-400">
    Could not load your portal. Please try again shortly.
  </div>

{:else if $profileQ.data}
  {@const profile = $profileQ.data}
  {@const terms = $termsQ.data ?? []}

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
  <h2 class="mb-3 text-xs font-semibold uppercase tracking-widest text-[var(--fg-subtle)]">Report cards</h2>

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
{/if}
