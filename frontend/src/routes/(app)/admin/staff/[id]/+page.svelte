<script lang="ts">
  import { page } from '$app/stores';
  import { goto } from '$app/navigation';
  import { createQuery, createMutation, useQueryClient } from '@tanstack/svelte-query';
  import { getStaff, updateStaff } from '$lib/api/staff';
  import ProfileTab        from './ProfileTab.svelte';
  import QualificationsTab from './QualificationsTab.svelte';
  import PromotionsTab     from './PromotionsTab.svelte';
  import LeaveTab          from './LeaveTab.svelte';

  const qc = useQueryClient();
  const staffId = $derived(() => $page.params.id);

  const query = createQuery({
    queryKey: ['staff', staffId()],
    queryFn:  () => getStaff(staffId()),
    staleTime: 2 * 60_000,
  });

  type Tab = 'profile' | 'qualifications' | 'promotions' | 'leave';
  const TAB_LABELS: Record<Tab, string> = { profile: 'Profile', qualifications: 'Qualifications', promotions: 'Promotions', leave: 'Leave' };
  const activeTab = $derived(() => (($page.url.searchParams.get('tab') as Tab) ?? 'profile'));

  function setTab(t: Tab) { goto(`?tab=${t}`, { replaceState: true, noScroll: true }); }

  const toggleMut = createMutation({
    mutationFn: () => updateStaff(staffId(), { is_active: !$query.data!.is_active }),
    onSuccess:  () => qc.invalidateQueries({ queryKey: ['staff', staffId()] }),
  });

  const GENDER_BG: Record<string, string> = { MALE: '#3B82F6', FEMALE: '#EC4899' };
</script>

<div class="mb-5">
  <a href="/admin/staff"
     class="inline-flex items-center gap-1.5 text-sm text-[var(--fg-muted)] transition hover:text-[var(--fg)]">
    <svg class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
      <path stroke-linecap="round" stroke-linejoin="round" d="M15 19l-7-7 7-7"/>
    </svg>
    All staff
  </a>
</div>

{#if $query.isPending}
  <div class="space-y-4">
    <div class="h-32 animate-pulse rounded-xl bg-[var(--card)]"></div>
    <div class="h-48 animate-pulse rounded-xl bg-[var(--card)]"></div>
  </div>
{:else if $query.isError}
  <div class="rounded-xl border border-red-100 dark:border-red-900 bg-red-50 dark:bg-red-950/40 p-4 text-sm text-red-600 dark:text-red-400">
    Could not load staff member.
    <button onclick={() => $query.refetch()} class="ml-2 underline">Retry</button>
  </div>
{:else if $query.data}
  {@const s = $query.data}

  <!-- Hero card -->
  <div class="mb-6 overflow-hidden rounded-xl border border-[var(--border)] bg-[var(--card)]">
    <div class="flex flex-wrap items-start gap-5 p-6">
      <div class="flex h-16 w-16 shrink-0 items-center justify-center rounded-xl text-2xl font-bold text-white shadow-sm"
           style="background-color: {GENDER_BG[s.gender ?? ''] ?? 'var(--brand)'}">
        {s.first_name[0]}{s.last_name[0]}
      </div>

      <div class="min-w-0 flex-1">
        <div class="flex flex-wrap items-center gap-2">
          <h1 class="text-xl font-bold text-[var(--fg)]">{s.display_name}</h1>
          <span class="rounded-full px-2.5 py-0.5 text-xs font-semibold
                       {s.is_active ? 'bg-green-100 dark:bg-green-950/50 text-green-700 dark:text-green-400'
                                    : 'bg-gray-100 dark:bg-gray-800 text-gray-500'}">
            {s.is_active ? 'Active' : 'Inactive'}
          </span>
        </div>
        <p class="mt-0.5 text-sm text-[var(--fg-muted)]">
          {s.staff_number}{s.position_names.length ? ' · ' + s.position_names.join(', ') : ''}
        </p>
        <div class="mt-3 flex flex-wrap gap-4 text-xs text-[var(--fg-muted)]">
          {#if s.phone}
            <span class="flex items-center gap-1">
              <svg class="h-3.5 w-3.5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" d="M2.25 6.338c0 10.309 8.353 18.662 18.662 18.662h.388a1.5 1.5 0 001.378-2.08L21.67 19.4a1.5 1.5 0 00-1.627-.657l-3.65.913a1.5 1.5 0 01-1.397-.378l-3.274-3.274a1.5 1.5 0 01-.378-1.397l.913-3.651a1.5 1.5 0 00-.657-1.627L8.74 7.72a1.5 1.5 0 00-2.08 1.378C6.65 9.447 6.5 9.718 6.5 10c0 .282.15.553.16.662z"/>
              </svg>
              {s.phone}
            </span>
          {/if}
          {#if s.email}
            <span class="flex items-center gap-1">
              <svg class="h-3.5 w-3.5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" d="M21.75 6.75v10.5a2.25 2.25 0 01-2.25 2.25h-15a2.25 2.25 0 01-2.25-2.25V6.75m19.5 0A2.25 2.25 0 0019.5 4.5h-15a2.25 2.25 0 00-2.25 2.25m19.5 0v.243a2.25 2.25 0 01-1.07 1.916l-7.5 4.615a2.25 2.25 0 01-2.36 0L3.32 8.91a2.25 2.25 0 01-1.07-1.916V6.75"/>
              </svg>
              {s.email}
            </span>
          {/if}
          {#if s.joined_date}
            <span class="flex items-center gap-1">
              <svg class="h-3.5 w-3.5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" d="M6.75 3v2.25M17.25 3v2.25M3 18.75V7.5a2.25 2.25 0 012.25-2.25h13.5A2.25 2.25 0 0121 7.5v11.25m-18 0A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75m-18 0v-7.5A2.25 2.25 0 015.25 9h13.5A2.25 2.25 0 0121 11.25v7.5"/>
              </svg>
              Joined {new Date(s.joined_date).toLocaleDateString('en-GH', { month: 'short', year: 'numeric' })}
            </span>
          {/if}
        </div>
      </div>

      <!-- Active toggle -->
      <button onclick={() => $toggleMut.mutate()} disabled={$toggleMut.isPending}
        class="shrink-0 rounded-xl border border-[var(--border)] px-3 py-1.5 text-xs font-medium text-[var(--fg-muted)] transition hover:bg-[var(--hover)] hover:text-[var(--fg)] disabled:opacity-50">
        {$toggleMut.isPending ? '…' : s.is_active ? 'Deactivate' : 'Reactivate'}
      </button>
    </div>
  </div>

  <!-- Tabs -->
  <div class="mb-5 border-b border-[var(--border)]">
    <nav class="-mb-px flex gap-1">
      {#each Object.entries(TAB_LABELS) as [t, label]}
        <button onclick={() => setTab(t as Tab)}
          class="relative px-4 pb-3 pt-1 text-sm font-medium transition-colors
                 {activeTab() === t ? 'text-[var(--brand)]' : 'text-[var(--fg-muted)] hover:text-[var(--fg)]'}">
          {label}
          <span class="pointer-events-none absolute bottom-0 left-0 right-0 h-0.5 rounded-t-sm
                       {activeTab() === t ? 'bg-[var(--brand)]' : 'bg-transparent'}"></span>
        </button>
      {/each}
    </nav>
  </div>

  {#if activeTab() === 'profile'}
    <ProfileTab staff={s} staffId={staffId()} />
  {:else if activeTab() === 'qualifications'}
    <QualificationsTab staff={s} staffId={staffId()} />
  {:else if activeTab() === 'promotions'}
    <PromotionsTab staff={s} staffId={staffId()} />
  {:else if activeTab() === 'leave'}
    <LeaveTab staffId={staffId()} />
  {/if}
{/if}
