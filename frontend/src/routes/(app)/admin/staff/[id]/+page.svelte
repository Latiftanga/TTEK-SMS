<script lang="ts">
  import { page } from '$app/stores';
  import { goto } from '$app/navigation';
  import { createQuery, createMutation, useQueryClient } from '@tanstack/svelte-query';
  import { getStaff, updateStaff, resetStaffPassword, type TempPasswordResult } from '$lib/api/staff';
  import { getMySchool } from '$lib/api/schools';
  import { toast } from '$lib/stores/toast';
  import Badge                from '$lib/components/Badge.svelte';
  import ProfileTab           from './ProfileTab.svelte';
  import QualificationsTab    from './QualificationsTab.svelte';
  import PromotionsTab        from './PromotionsTab.svelte';
  import LeaveTab             from './LeaveTab.svelte';
  import PasswordResetModals  from './PasswordResetModals.svelte';

  const qc = useQueryClient();
  const staffId = $derived(() => $page.params.id);

  const query = createQuery({
    queryKey: ['staff', staffId()],
    queryFn:  () => getStaff(staffId()),
    staleTime: 2 * 60_000,
  });

  const schoolQuery = createQuery({
    queryKey: ['my-school'],
    queryFn:  getMySchool,
    staleTime: 10 * 60_000,
  });

  type Tab = 'profile' | 'qualifications' | 'promotions' | 'leave';
  const TABS = $derived((): { key: Tab; label: string }[] => [
    { key: 'profile',        label: 'Profile'        },
    { key: 'qualifications', label: 'Qualifications' },
    ...($schoolQuery.data?.ownership !== 'PRIVATE' ? [{ key: 'promotions' as Tab, label: 'Promotions' }] : []),
    { key: 'leave',          label: 'Leave'          },
  ]);
  const activeTab = $derived(() => (($page.url.searchParams.get('tab') as Tab) ?? 'profile'));
  function setTab(t: Tab) { goto(`?tab=${t}`, { replaceState: true, noScroll: true }); }

  const toggleMut = createMutation({
    mutationFn: () => updateStaff(staffId(), { is_active: !$query.data!.is_active }),
    onSuccess: (data) => {
      qc.invalidateQueries({ queryKey: ['staff', staffId()] });
      toast.success(data.is_active ? 'Staff member reactivated.' : 'Staff member deactivated.');
    },
    onError: () => toast.error('Could not update status. Try again.'),
  });

  let resetResult   = $state<TempPasswordResult | null>(null);
  let confirmReset  = $state(false);
  const resetMut = createMutation({
    mutationFn: () => resetStaffPassword(staffId()),
    onSuccess: (r) => { confirmReset = false; resetResult = r; },
    onError: (e: unknown) => {
      confirmReset = false;
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
        ?? 'Could not reset password.';
      toast.error(msg);
    },
  });

  const GENDER_BG: Record<string, string> = { MALE: '#3B82F6', FEMALE: '#EC4899' };
  const EMP_LABEL: Record<string, string> = {
    PERMANENT: 'Permanent', CONTRACT: 'Contract',
    NATIONAL_SERVICE: 'National Service', INTERN: 'Intern',
  };

  function fmtDate(d: string | null | undefined) {
    if (!d) return '—';
    return new Date(d).toLocaleDateString('en-GH', { day: 'numeric', month: 'short', year: 'numeric' });
  }
</script>

<!-- Back -->
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
    <div class="skeleton h-36"></div>
    <div class="skeleton h-64"></div>
  </div>
{:else if $query.isError}
  <div class="rounded-xl border border-red-100 dark:border-red-900 bg-red-50 dark:bg-red-950/40
              p-4 text-sm text-red-600 dark:text-red-400">
    Could not load staff member.
    <button onclick={() => $query.refetch()} class="ml-2 underline">Retry</button>
  </div>
{:else if $query.data}
  {@const s = $query.data}

  <!-- Hero card -->
  <div class="mb-6 overflow-hidden rounded-xl border border-[var(--border)] bg-[var(--card)]">
    <!-- Accent bar -->
    <div class="h-1.5" style="background: linear-gradient(90deg, var(--brand) 0%, color-mix(in oklab, var(--brand) 55%, #7c3aed) 100%)"></div>

    <div class="flex flex-wrap items-start gap-5 p-6">
      <!-- Avatar -->
      <div class="flex h-20 w-20 shrink-0 items-center justify-center rounded-2xl
                  text-2xl font-bold text-white shadow-md"
           style="background-color: {GENDER_BG[s.gender ?? ''] ?? 'var(--brand)'}">
        {s.first_name[0]}{s.last_name[0]}
      </div>

      <!-- Identity -->
      <div class="min-w-0 flex-1">
        <div class="flex flex-wrap items-center gap-2.5 mb-1">
          <h1 class="text-xl font-bold text-[var(--fg)]">{s.display_name}</h1>
          <Badge label={s.is_active ? 'Active' : 'Inactive'} color={s.is_active ? 'green' : 'gray'} variant="dot" />
          {#if s.category_name}
            <Badge label={s.category_name} color="violet" variant="solid" />
          {/if}
        </div>

        <p class="mb-3 text-sm text-[var(--fg-muted)]">{s.staff_number}</p>

        <!-- Position chips -->
        {#if s.position_names.length}
          <div class="mb-3 flex flex-wrap gap-1.5">
            {#each s.position_names as pos}
              <span class="rounded-lg border border-[var(--border)] bg-[var(--hover)]
                           px-2.5 py-0.5 text-xs font-medium text-[var(--fg)]">
                {pos}
              </span>
            {/each}
          </div>
        {/if}

        <!-- Contact strip -->
        <div class="flex flex-wrap gap-4 text-xs text-[var(--fg-muted)]">
          {#if s.phone}
            <a href="tel:{s.phone}" class="flex items-center gap-1 hover:text-[var(--fg)] transition">
              <svg class="h-3.5 w-3.5 shrink-0" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" d="M2.25 6.338c0 10.309 8.353 18.662 18.662 18.662h.388a1.5 1.5 0 001.378-2.08L21.67 19.4a1.5 1.5 0 00-1.627-.657l-3.65.913a1.5 1.5 0 01-1.397-.378l-3.274-3.274a1.5 1.5 0 01-.378-1.397l.913-3.651a1.5 1.5 0 00-.657-1.627L8.74 7.72a1.5 1.5 0 00-2.08 1.378C6.65 9.447 6.5 9.718 6.5 10c0 .282.15.553.16.662z"/>
              </svg>
              {s.phone}
            </a>
          {/if}
          {#if s.email}
            <a href="mailto:{s.email}" class="flex items-center gap-1 hover:text-[var(--fg)] transition">
              <svg class="h-3.5 w-3.5 shrink-0" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" d="M21.75 6.75v10.5a2.25 2.25 0 01-2.25 2.25h-15a2.25 2.25 0 01-2.25-2.25V6.75m19.5 0A2.25 2.25 0 0019.5 4.5h-15a2.25 2.25 0 00-2.25 2.25m19.5 0v.243a2.25 2.25 0 01-1.07 1.916l-7.5 4.615a2.25 2.25 0 01-2.36 0L3.32 8.91a2.25 2.25 0 01-1.07-1.916V6.75"/>
              </svg>
              {s.email}
            </a>
          {/if}
          {#if s.joined_date}
            <span class="flex items-center gap-1">
              <svg class="h-3.5 w-3.5 shrink-0" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" d="M6.75 3v2.25M17.25 3v2.25M3 18.75V7.5a2.25 2.25 0 012.25-2.25h13.5A2.25 2.25 0 0121 7.5v11.25m-18 0A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75m-18 0v-7.5A2.25 2.25 0 015.25 9h13.5A2.25 2.25 0 0121 11.25v7.5"/>
              </svg>
              Joined {new Date(s.joined_date).toLocaleDateString('en-GH', { month: 'short', year: 'numeric' })}
            </span>
          {/if}
        </div>
      </div>

      <!-- Actions -->
      <div class="flex shrink-0 flex-col gap-2">
        <button onclick={() => $toggleMut.mutate()} disabled={$toggleMut.isPending}
          class="rounded-xl border border-[var(--border)] px-3 py-1.5 text-xs font-medium
                 text-[var(--fg-muted)] transition disabled:opacity-50
                 {s.is_active
                   ? 'hover:border-red-200 hover:bg-red-50 hover:text-red-600 dark:hover:border-red-800 dark:hover:bg-red-950/40 dark:hover:text-red-400'
                   : 'hover:bg-[var(--hover)] hover:text-[var(--fg)]'}">
          {$toggleMut.isPending ? '…' : s.is_active ? 'Deactivate' : 'Reactivate'}
        </button>
        <button onclick={() => confirmReset = true}
          class="rounded-xl border border-[var(--border)] px-3 py-1.5 text-xs font-medium
                 text-[var(--fg-muted)] transition hover:border-amber-300 hover:bg-amber-50 hover:text-amber-700
                 dark:hover:border-amber-700 dark:hover:bg-amber-950/40 dark:hover:text-amber-400">
          Reset password
        </button>
      </div>
    </div>
  </div>

  <!-- Two-column body -->
  <div class="grid grid-cols-1 gap-6 xl:grid-cols-[1fr_256px]">

    <!-- LEFT: tabs + content -->
    <div>
      <!-- Pill tabs -->
      <div class="mb-5 flex flex-wrap gap-1 rounded-xl bg-[var(--hover)] p-1">
        {#each TABS() as t}
          <button onclick={() => setTab(t.key)}
            class="rounded-lg px-4 py-2 text-sm font-medium transition
                   {activeTab() === t.key
                     ? 'bg-[var(--card)] text-[var(--fg)] shadow-sm ring-1 ring-[var(--border)]'
                     : 'text-[var(--fg-muted)] hover:text-[var(--fg)]'}">
            {t.label}
          </button>
        {/each}
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
    </div>

    <!-- RIGHT: sidebar -->
    <div class="space-y-4">

      <!-- Employment card -->
      <div class="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
        <p class="mb-3 text-[11px] font-semibold uppercase tracking-widest text-[var(--fg-muted)]">
          Employment
        </p>
        <dl class="space-y-3">
          {#each ([
            ['Category',      s.category_name ?? '—'],
            ['Type',          s.employment_type ? EMP_LABEL[s.employment_type] : '—'],
            ['Joined',        fmtDate(s.joined_date)],
            ['Date of birth', fmtDate(s.date_of_birth)],
            ['Gender',        s.gender ? s.gender.charAt(0) + s.gender.slice(1).toLowerCase() : '—'],
          ] as Array<[string, string]>) as [rowLabel, rowValue]}
            <div class="flex items-start justify-between gap-3">
              <dt class="shrink-0 text-xs text-[var(--fg-muted)]">{rowLabel}</dt>
              <dd class="text-right text-xs font-medium text-[var(--fg)]">{rowValue}</dd>
            </div>
          {/each}
        </dl>
      </div>

      <!-- HR identifiers -->
      {#if s.national_id || s.ssnit_number}
        <div class="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
          <p class="mb-3 text-[11px] font-semibold uppercase tracking-widest text-[var(--fg-muted)]">
            HR identifiers
          </p>
          <dl class="space-y-3">
            {#if s.national_id}
              <div class="flex items-start justify-between gap-3">
                <dt class="shrink-0 text-xs text-[var(--fg-muted)]">Ghana Card</dt>
                <dd class="text-right font-mono text-xs text-[var(--fg)]">{s.national_id}</dd>
              </div>
            {/if}
            {#if s.ssnit_number}
              <div class="flex items-start justify-between gap-3">
                <dt class="shrink-0 text-xs text-[var(--fg-muted)]">SSNIT</dt>
                <dd class="text-right font-mono text-xs text-[var(--fg)]">{s.ssnit_number}</dd>
              </div>
            {/if}
          </dl>
        </div>
      {/if}

      <!-- Platform access -->
      {#if s.email || s.phone}
        <div class="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
          <p class="mb-1.5 text-[11px] font-semibold uppercase tracking-widest text-[var(--fg-muted)]">Platform access</p>
          <p class="mb-3 text-xs text-[var(--fg-muted)]">
            Send a login invitation to this staff member.
          </p>
          <button
            class="w-full rounded-xl border border-[var(--border)] py-2 text-xs font-medium
                   text-[var(--fg-muted)] transition hover:bg-[var(--hover)] hover:text-[var(--fg)]">
            Send invitation
          </button>
        </div>
      {/if}

    </div>
  </div>
{/if}

<PasswordResetModals
  displayName={$query.data?.display_name ?? ''}
  confirmOpen={confirmReset}
  onConfirm={() => $resetMut.mutate()}
  onCancel={() => confirmReset = false}
  isPending={$resetMut.isPending}
  result={resetResult}
  onDismiss={() => resetResult = null}
/>
