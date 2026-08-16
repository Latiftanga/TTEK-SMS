<script lang="ts">
  import type { StaffDetail } from '$lib/api/staff';

  interface Props {
    staff: StaffDetail;
    isOwnProfile: boolean;
    inviting: boolean;
    onInvite: () => void;
  }
  const { staff: s, isOwnProfile, inviting, onInvite }: Props = $props();

  const EMP_LABEL: Record<string, string> = {
    PERMANENT: 'Permanent', CONTRACT: 'Contract',
    NATIONAL_SERVICE: 'National Service', INTERN: 'Intern',
  };

  function fmtDate(d: string | null | undefined) {
    if (!d) return '—';
    return new Date(d).toLocaleDateString('en-GH', { day: 'numeric', month: 'short', year: 'numeric' });
  }
</script>

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
          onclick={onInvite}
          disabled={inviting}
          class="w-full rounded-xl border border-[var(--border)] py-2 text-xs font-medium
                 text-[var(--fg-muted)] transition hover:bg-[var(--hover)] hover:text-[var(--fg)]
                 disabled:opacity-50">
          {inviting ? 'Sending…' : 'Send invitation'}
        </button>
      {/if}
    </div>
  {/if}

</div>
