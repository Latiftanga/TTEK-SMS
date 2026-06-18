<script lang="ts">
  import { createQuery } from '@tanstack/svelte-query';
  import { goto } from '$app/navigation';
  import { getMe } from '$lib/api/auth';
  import { getStaff } from '$lib/api/staff';
  import { auth } from '$lib/stores/auth';
  import { get } from 'svelte/store';

  const user = get(auth).user;

  const meQuery = createQuery({ queryKey: ['me'], queryFn: getMe, staleTime: 5 * 60_000 });
  const staffQuery = createQuery({
    queryKey: ['staff', user?.staff_member_id],
    queryFn: () => getStaff(user!.staff_member_id!),
    enabled: !!user?.staff_member_id,
    staleTime: 5 * 60_000,
  });

  const LOGIN_LABEL: Record<string, string> = {
    EMAIL: 'Email', PHONE: 'Phone number', ADMISSION_ID: 'Student ID',
  };
  const GENDER_BG: Record<string, string> = { MALE: '#3B82F6', FEMALE: '#EC4899' };
</script>

<svelte:head><title>My Profile</title></svelte:head>

<div class="mx-auto max-w-xl space-y-6">
  <div>
    <h1 class="text-2xl font-bold text-[var(--fg)]">My Profile</h1>
    <p class="mt-1 text-sm text-[var(--fg-muted)]">Your account and identity details.</p>
  </div>

  {#if $staffQuery.data}
    {@const s = $staffQuery.data}
    <div class="overflow-hidden rounded-2xl border border-[var(--border)] bg-[var(--card)] shadow-sm">
      <div class="h-1.5" style="background: linear-gradient(90deg, var(--brand) 0%, color-mix(in oklab, var(--brand) 55%, #7c3aed) 100%)"></div>
      <div class="flex items-center gap-4 p-6">
        <div class="flex h-16 w-16 shrink-0 items-center justify-center rounded-2xl text-xl font-bold text-white shadow"
             style="background-color: {GENDER_BG[s.gender ?? ''] ?? 'var(--brand)'}">
          {s.first_name[0]}{s.last_name[0]}
        </div>
        <div class="min-w-0">
          <p class="text-lg font-bold text-[var(--fg)] truncate">{s.display_name}</p>
          <p class="text-sm text-[var(--fg-muted)]">{s.staff_number}</p>
          {#if s.position_names.length}
            <p class="mt-0.5 text-xs text-[var(--fg-subtle)]">{s.position_names.join(' · ')}</p>
          {/if}
        </div>
      </div>

      <div class="grid grid-cols-2 gap-0 border-t border-[var(--border)] divide-x divide-[var(--border)]">
        {#if s.phone}
          <div class="px-5 py-3">
            <p class="text-[11px] font-semibold uppercase tracking-wide text-[var(--fg-muted)]">Phone</p>
            <p class="mt-0.5 text-sm text-[var(--fg)]">{s.phone}</p>
          </div>
        {/if}
        {#if s.email}
          <div class="px-5 py-3">
            <p class="text-[11px] font-semibold uppercase tracking-wide text-[var(--fg-muted)]">Email</p>
            <p class="mt-0.5 truncate text-sm text-[var(--fg)]">{s.email}</p>
          </div>
        {/if}
      </div>

      <div class="border-t border-[var(--border)] px-6 py-3">
        <button onclick={() => goto(`/admin/staff/${s.id}`)}
          class="text-xs font-medium text-[var(--brand)] hover:underline">
          View full staff profile →
        </button>
      </div>
    </div>
  {:else if $meQuery.data}
    {@const me = $meQuery.data}
    <div class="rounded-2xl border border-[var(--border)] bg-[var(--card)] p-6 shadow-sm">
      <div class="flex items-center gap-4">
        <div class="flex h-12 w-12 shrink-0 items-center justify-center rounded-full bg-[var(--hover)] text-lg font-bold text-[var(--fg)]">
          {(me.display_name?.[0] ?? me.email?.[0] ?? '?').toUpperCase()}
        </div>
        <div>
          <p class="font-semibold text-[var(--fg)]">{me.display_name ?? me.email ?? me.phone}</p>
          <p class="text-xs text-[var(--fg-muted)]">{LOGIN_LABEL[me.login_type] ?? me.login_type} login</p>
        </div>
      </div>
    </div>
  {:else}
    <div class="skeleton h-32 rounded-2xl"></div>
  {/if}

  <!-- Account section -->
  <div class="rounded-2xl border border-[var(--border)] bg-[var(--card)] divide-y divide-[var(--border)] shadow-sm">
    <div class="px-5 py-3.5">
      <p class="text-[11px] font-semibold uppercase tracking-wide text-[var(--fg-muted)]">Account</p>
    </div>
    {#if $meQuery.data}
      <div class="flex items-center justify-between px-5 py-3.5">
        <div>
          <p class="text-sm font-medium text-[var(--fg)]">Sign-in {LOGIN_LABEL[$meQuery.data.login_type] ?? 'identifier'}</p>
          <p class="text-xs text-[var(--fg-muted)] mt-0.5">{$meQuery.data.email ?? $meQuery.data.phone ?? '—'}</p>
        </div>
      </div>
    {/if}
    <div class="flex items-center justify-between px-5 py-3.5">
      <div>
        <p class="text-sm font-medium text-[var(--fg)]">Password</p>
        <p class="text-xs text-[var(--fg-muted)] mt-0.5">Update your account password</p>
      </div>
      <a href="/change-password"
         class="rounded-lg border border-[var(--border)] px-3 py-1.5 text-xs font-medium text-[var(--fg)] transition hover:bg-[var(--hover)]">
        Change
      </a>
    </div>
  </div>
</div>
