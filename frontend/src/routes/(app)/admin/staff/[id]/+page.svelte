<script lang="ts">
  import { page } from '$app/stores';
  import { goto } from '$app/navigation';
  import { schoolLoginUrl as buildSchoolLoginUrl } from '$lib/platformDomain';
  import { createQuery, createMutation, useQueryClient } from '@tanstack/svelte-query';
  import { getStaff, updateStaff, resetStaffPassword, inviteStaff, type TempPasswordResult, type InviteResult } from '$lib/api/staff';
  import { getMySchool } from '$lib/api/schools';
  import { auth } from '$lib/stores/auth';
  import { toast } from '$lib/stores/toast';
  import { apiError } from '$lib/utils';
  import { userRole } from '$lib/stores/permissions';
  import Badge                from '$lib/components/Badge.svelte';
  import TabBar               from '$lib/components/TabBar.svelte';
  import StaffPhotoAvatar     from './StaffPhotoAvatar.svelte';
  import ProfileTab           from './ProfileTab.svelte';
  import QualificationsTab    from './QualificationsTab.svelte';
  import PromotionsTab        from './PromotionsTab.svelte';
  import LeaveTab             from './LeaveTab.svelte';
  import PasswordResetModals    from './PasswordResetModals.svelte';
  import ResponsibilitiesTab    from './ResponsibilitiesTab.svelte';
  import PermissionsTab         from './PermissionsTab.svelte';
  import { setPageTitle } from '$lib/stores/title';

  const qc = useQueryClient();
  const staffId = $page.params.id!;
  const isOwnProfile = $derived($auth.user?.staff_member_id === staffId);

  const query = createQuery({
    queryKey: ['staff', staffId],
    queryFn:  () => getStaff(staffId),
    staleTime: 2 * 60_000,
  });

  $effect(() => setPageTitle($query.data?.display_name ?? 'Staff'));

  const schoolQuery = createQuery({
    queryKey: ['my-school'],
    queryFn:  getMySchool,
    staleTime: 10 * 60_000,
  });

  type Tab = 'profile' | 'qualifications' | 'promotions' | 'leave' | 'responsibilities' | 'permissions';
  const IC = {
    profile:          `<path stroke-linecap="round" stroke-linejoin="round" d="M15.75 6a3.75 3.75 0 11-7.5 0 3.75 3.75 0 017.5 0zM4.501 20.118a7.5 7.5 0 0114.998 0A17.933 17.933 0 0112 21.75c-2.676 0-5.216-.584-7.499-1.632z"/>`,
    responsibilities: `<path stroke-linecap="round" stroke-linejoin="round" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-3 7h3m-3 4h3m-6-4h.01M9 16h.01"/>`,
    qualifications:   `<path stroke-linecap="round" stroke-linejoin="round" d="M4.26 10.147a60.436 60.436 0 00-.491 6.347A48.627 48.627 0 0112 20.904a48.627 48.627 0 018.232-4.41 60.46 60.46 0 00-.491-6.347m-15.482 0a50.57 50.57 0 00-2.658-.813A59.905 59.905 0 0112 3.493a59.902 59.902 0 0110.399 5.84c-.896.248-1.783.52-2.658.814m-15.482 0A50.697 50.697 0 0112 13.489a50.702 50.702 0 017.74-3.342M6.75 15a.75.75 0 100-1.5.75.75 0 000 1.5zm0 0v-3.675A55.378 55.378 0 0112 8.443m-7.007 11.55A5.981 5.981 0 006.75 15.75v-1.5"/>`,
    promotions:       `<path stroke-linecap="round" stroke-linejoin="round" d="M2.25 18L9 11.25l4.306 4.307a11.95 11.95 0 015.814-5.519l2.74-1.22m0 0l-5.94-2.28m5.94 2.28l-2.28 5.941"/>`,
    leave:            `<path stroke-linecap="round" stroke-linejoin="round" d="M6.75 3v2.25M17.25 3v2.25M3 18.75V7.5a2.25 2.25 0 012.25-2.25h13.5A2.25 2.25 0 0121 7.5v11.25m-18 0A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75m-18 0v-7.5A2.25 2.25 0 015.25 9h13.5A2.25 2.25 0 0121 11.25v7.5"/>`,
    permissions:      `<path stroke-linecap="round" stroke-linejoin="round" d="M16.5 10.5V6.75a4.5 4.5 0 10-9 0v3.75m-.75 11.25h10.5a2.25 2.25 0 002.25-2.25v-6.75a2.25 2.25 0 00-2.25-2.25H6.75a2.25 2.25 0 00-2.25 2.25v6.75a2.25 2.25 0 002.25 2.25z"/>`,
  };

  const TABS = $derived([
    { key: 'profile' as Tab,           label: 'Profile',          icon: IC.profile          },
    { key: 'responsibilities' as Tab,  label: 'Responsibilities', icon: IC.responsibilities },
    { key: 'qualifications' as Tab,    label: 'Qualifications',   icon: IC.qualifications   },
    ...($schoolQuery.data?.ownership !== 'PRIVATE' ? [{ key: 'promotions' as Tab, label: 'Promotions', icon: IC.promotions }] : []),
    { key: 'leave' as Tab,             label: 'Leave',            icon: IC.leave            },
    ...(!isOwnProfile ? [{ key: 'permissions' as Tab, label: 'Permissions', icon: IC.permissions }] : []),
  ]);
  const activeTab = $derived(($page.url.searchParams.get('tab') as Tab) ?? 'profile');
  function setTab(t: Tab) { goto(`?tab=${t}`, { replaceState: true, noScroll: true }); }

  const toggleMut = createMutation({
    mutationFn: () => updateStaff(staffId, { is_active: !($query.data?.is_active ?? true) }),
    onSuccess: (data) => {
      qc.invalidateQueries({ queryKey: ['staff', staffId] });
      toast.success(data.is_active ? 'Staff member reactivated.' : 'Staff member deactivated.');
    },
    onError: () => toast.error('Could not update status. Try again.'),
  });

  let inviteResult = $state<InviteResult | null>(null);
  let inviteLinkCopied = $state(false);

  // Every school gets a branded subdomain by default now (see
  // services/school.py::create_school) — surfacing it here means new staff
  // have a memorable URL to bookmark instead of a "school code" to
  // remember on every future login.
  const schoolLoginUrl = $derived(buildSchoolLoginUrl($schoolQuery.data?.subdomain));

  const inviteMut = createMutation({
    mutationFn: () => inviteStaff(staffId),
    onSuccess: (r) => { inviteResult = r; },
    onError: (e) => toast.error(apiError(e, 'Could not send invitation.')),
  });

  function copyInviteLink() {
    if (!inviteResult) return;
    navigator.clipboard.writeText(inviteResult.invite_link).then(() => {
      inviteLinkCopied = true;
      setTimeout(() => inviteLinkCopied = false, 2000);
    });
  }

  let resetResult   = $state<TempPasswordResult | null>(null);
  let confirmReset  = $state(false);
  const resetMut = createMutation({
    mutationFn: () => resetStaffPassword(staffId),
    onSuccess: (r) => { confirmReset = false; resetResult = r; },
    onError: (e) => { confirmReset = false; toast.error(apiError(e, 'Could not reset password.')); },
  });

  const EMP_LABEL: Record<string, string> = {
    PERMANENT: 'Permanent', CONTRACT: 'Contract',
    NATIONAL_SERVICE: 'National Service', INTERN: 'Intern',
  };

  // Resetting a colleague's password is an account-takeover-shaped action —
  // requires school.manage_users specifically (backend 403s otherwise, same
  // as position changes on ResponsibilitiesTab.svelte); $userRole is
  // 'admin' exactly when the caller holds it.
  const canResetPassword = $derived($userRole === 'admin');

  function fmtDate(d: string | null | undefined) {
    if (!d) return '—';
    return new Date(d).toLocaleDateString('en-GH', { day: 'numeric', month: 'short', year: 'numeric' });
  }
</script>

<!-- Back -->
<div class="mb-5">
  <a href={isOwnProfile ? '/dashboard' : '/admin/staff'}
     class="inline-flex items-center gap-1.5 text-sm text-[var(--fg-muted)] transition hover:text-[var(--fg)]">
    <svg class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
      <path stroke-linecap="round" stroke-linejoin="round" d="M15 19l-7-7 7-7"/>
    </svg>
    {isOwnProfile ? 'Dashboard' : 'All staff'}
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
      <StaffPhotoAvatar
        staffId={staffId}
        firstName={s.first_name}
        lastName={s.last_name}
        photoUrl={s.photo_url}
        size="lg"
      />

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

      <!-- Actions: hidden on own profile, and blocked until auth hydrates to avoid flash before isOwnProfile resolves -->
      {#if $auth.user && !isOwnProfile}
        <div class="flex shrink-0 flex-col gap-2">
          <button onclick={() => $toggleMut.mutate()} disabled={$toggleMut.isPending} class="btn-ghost">
            {$toggleMut.isPending ? '…' : s.is_active ? 'Deactivate' : 'Reactivate'}
          </button>
          {#if canResetPassword}
            <button onclick={() => confirmReset = true} class="btn-ghost">
              Reset password
            </button>
          {/if}
        </div>
      {/if}
    </div>
  </div>

  <!-- Two-column body -->
  <div class="grid grid-cols-1 gap-6 xl:grid-cols-[1fr_256px]">

    <!-- LEFT: tabs + content -->
    <div>
      <div class="mb-5">
        <TabBar
          tabs={TABS.map(t => ({ id: t.key, label: t.label, icon: t.icon }))}
          active={activeTab}
          onchange={(id) => setTab(id as typeof activeTab)}
        />
      </div>

      {#if activeTab === 'profile'}
        <ProfileTab staff={s} staffId={staffId} {isOwnProfile} />
      {:else if activeTab === 'responsibilities'}
        <ResponsibilitiesTab staff={s} {staffId} boardingEnabled={$schoolQuery.data?.has_boarding ?? false} {isOwnProfile} />
      {:else if activeTab === 'qualifications'}
        <QualificationsTab staff={s} staffId={staffId} />
      {:else if activeTab === 'promotions'}
        <PromotionsTab staff={s} staffId={staffId} readOnly={isOwnProfile} />
      {:else if activeTab === 'leave'}
        <LeaveTab staffId={staffId} {isOwnProfile} />
      {:else if activeTab === 'permissions'}
        <PermissionsTab {staffId} />
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
            ['Staff type',    s.staff_type ? (s.staff_type === 'TEACHING' ? 'Teaching' : 'Non-teaching') : '—'],
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

      <!-- Platform access (hidden on own profile — you're already signed in) -->
      {#if !isOwnProfile && (s.email || s.phone)}
        <div class="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
          <p class="mb-1.5 text-[11px] font-semibold uppercase tracking-widest text-[var(--fg-muted)]">Platform access</p>

          {#if s.has_account}
            <div class="flex items-center gap-2">
              <svg class="h-4 w-4 shrink-0 text-emerald-500" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
              </svg>
              <p class="text-xs text-[var(--fg-muted)]">Has an active account — can sign in already.</p>
            </div>
          {:else}
            <p class="mb-3 text-xs text-[var(--fg-muted)]">
              Send a login invitation to this staff member.
            </p>
            <button
              onclick={() => $inviteMut.mutate()}
              disabled={$inviteMut.isPending}
              class="w-full rounded-xl border border-[var(--border)] py-2 text-xs font-medium
                     text-[var(--fg-muted)] transition hover:bg-[var(--hover)] hover:text-[var(--fg)]
                     disabled:opacity-50">
              {$inviteMut.isPending ? 'Sending…' : 'Send invitation'}
            </button>
          {/if}
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

{#if inviteResult}
  <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
    <div class="w-full max-w-sm rounded-2xl border border-[var(--border)] bg-[var(--card)] p-6 shadow-2xl">
      <div class="mb-4 flex h-10 w-10 items-center justify-center rounded-full bg-emerald-100 dark:bg-emerald-900/40">
        <svg class="h-5 w-5 text-emerald-600 dark:text-emerald-400" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
        </svg>
      </div>

      <h2 class="text-base font-semibold text-[var(--fg)]">Invitation created</h2>

      {#if inviteResult.sms_sent}
        <p class="mt-1 text-sm text-[var(--fg-muted)]">
          An SMS with the link was sent to <span class="font-medium text-[var(--fg)]">{$query.data?.phone}</span>.
          You can also share this link directly:
        </p>
      {:else}
        <p class="mt-1 text-sm text-[var(--fg-muted)]">
          Share this link with <span class="font-medium text-[var(--fg)]">{$query.data?.display_name}</span>.
          They'll use it to set their password and activate their account.
          {#if $query.data?.phone}
            <span class="text-amber-600 dark:text-amber-400"> (No SMS provider configured — share manually.)</span>
          {/if}
        </p>
      {/if}

      <div class="mt-4 flex items-center gap-2 rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2.5">
        <p class="flex-1 truncate font-mono text-xs text-[var(--fg)]">{inviteResult.invite_link}</p>
        <button onclick={copyInviteLink}
          class="shrink-0 rounded-lg border border-[var(--border)] px-3 py-1 text-xs font-medium
                 text-[var(--fg-muted)] transition hover:bg-[var(--hover)]">
          {inviteLinkCopied ? '✓ Copied' : 'Copy'}
        </button>
      </div>

      <p class="mt-3 text-xs text-[var(--fg-subtle)]">Link expires in 72 hours.</p>

      {#if schoolLoginUrl}
        <p class="mt-4 rounded-xl bg-[var(--hover)]/50 px-3 py-2.5 text-xs text-[var(--fg-muted)]">
          Once they've set a password, tell them to bookmark
          <span class="font-mono font-medium text-[var(--fg)]">{schoolLoginUrl}</span>
          — their school's own sign-in page. No school code to remember, ever.
        </p>
      {/if}

      <div class="mt-5 flex justify-end">
        <button onclick={() => inviteResult = null}
          class="rounded-xl px-4 py-2 text-sm font-semibold text-white hover:opacity-90"
          style="background-color: var(--brand)">
          Done
        </button>
      </div>
    </div>
  </div>
{/if}
