<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import { getPlatformDomain, schoolLoginUrl } from '$lib/platformDomain';
  import { createQuery, createMutation, useQueryClient } from '@tanstack/svelte-query';
  import { auth, currentUser } from '$lib/stores/auth';
  import { logout } from '$lib/api/auth';
  import { listSchools, updateSchool, deleteSchool, type SchoolRead, type SchoolSummary } from '$lib/api/schools';
  import { get } from 'svelte/store';
  import { portal } from '$lib/actions/portal';
  import ChangePasswordForm from '$lib/components/ChangePasswordForm.svelte';
  import ConfirmModal from '$lib/components/ConfirmModal.svelte';
  import ThemeToggle from '$lib/components/ThemeToggle.svelte';
  import SchoolForm from './SchoolForm.svelte';
  import SchoolsTable from './SchoolsTable.svelte';

  onMount(() => {
    const user = get(currentUser);
    if (!user) goto('/');
  });

  async function handleLogout() {
    const rt = localStorage.getItem('refresh_token') ?? '';
    await logout(rt);
    auth.clearAuth();
    goto('/');
  }

  const qc = useQueryClient();
  const schoolsQuery = createQuery({ queryKey: ['schools'], queryFn: () => listSchools() });

  let search = $state('');
  const filteredSchools = $derived.by(() => {
    const all = $schoolsQuery.data ?? [];
    const q = search.trim().toLowerCase();
    if (!q) return all;
    return all.filter(s => s.name.toLowerCase().includes(q) || s.school_code.toLowerCase().includes(q));
  });

  const platformDomain = getPlatformDomain();
  function loginUrl(subdomain: string | null): string | null {
    return schoolLoginUrl(subdomain);
  }

  let formOpen = $state(false);
  let editingSchool = $state<SchoolSummary | null>(null);
  let createdSchool = $state<SchoolRead | null>(null);
  let linkCopied = $state(false);

  function openCreate() { editingSchool = null; formOpen = true; }
  function openEdit(s: SchoolSummary) { editingSchool = s; formOpen = true; }

  function onFormSuccess(school: SchoolRead) {
    const wasEditing = !!editingSchool;
    formOpen = false;
    editingSchool = null;
    if (!wasEditing) createdSchool = school;
    qc.invalidateQueries({ queryKey: ['schools'] });
  }

  function copyLink() {
    const url = createdSchool && loginUrl(createdSchool.subdomain);
    if (!url) return;
    navigator.clipboard.writeText(url).then(() => {
      linkCopied = true;
      setTimeout(() => linkCopied = false, 2000);
    });
  }

  // ── Quick active/inactive toggle ─────────────────────────────────────────────
  // Reactivating is the safe direction — fires immediately. Deactivating
  // blocks every staff/student login at that school right away (services/
  // auth_lookup.py::resolve_school_id), so it goes through a confirm step
  // first, unlike the Edit form's own toggle (there, "Save changes" is
  // itself already a deliberate, reviewable step — this one-click row
  // toggle has no equivalent pause).
  let togglingId = $state<string | null>(null);
  let deactivateTarget = $state<SchoolSummary | null>(null);

  const toggleMut = createMutation({
    mutationFn: (s: SchoolSummary) => updateSchool(s.id, { is_active: !s.is_active }),
    onMutate: (s) => { togglingId = s.id; },
    onSettled: () => { togglingId = null; deactivateTarget = null; },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['schools'] }),
  });

  function handleToggleActive(s: SchoolSummary) {
    if (s.is_active) deactivateTarget = s;
    else $toggleMut.mutate(s);
  }

  // ── Delete ────────────────────────────────────────────────────────────────────
  let deleteTarget = $state<SchoolSummary | null>(null);
  let deleteError = $state('');

  const deleteMut = createMutation({
    mutationFn: (s: SchoolSummary) => deleteSchool(s.id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['schools'] });
      deleteTarget = null;
      deleteError = '';
    },
    onError: (e: unknown) => {
      deleteError = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
        ?? 'Could not delete this school.';
    },
  });

  let showPasswordModal = $state(false);
  function onKeydown(e: KeyboardEvent) { if (e.key === 'Escape') showPasswordModal = false; }
</script>

<svelte:head><title>TTEK-SMS — Platform Admin</title></svelte:head>

<div class="min-h-screen bg-[var(--bg)] p-4 sm:p-8">
  <div class="mx-auto max-w-4xl">

    <!-- Header -->
    <div class="mb-6 flex flex-wrap items-center justify-between gap-3">
      <div class="flex items-center gap-3">
        <div class="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-gray-900 text-sm font-black text-white dark:bg-gray-800">
          T
        </div>
        <div>
          <h1 class="text-lg font-bold text-[var(--fg)]">Platform Administration</h1>
          <p class="text-xs text-[var(--fg-muted)]">{$currentUser?.email ?? '—'}</p>
        </div>
      </div>
      <div class="flex items-center gap-2">
        <ThemeToggle />
        <button onclick={openCreate}
          class="min-h-[44px] rounded-xl px-4 py-2 text-sm font-semibold text-white transition hover:opacity-90"
          style="background-color: var(--brand, #111827)">
          + Onboard school
        </button>
        <button onclick={() => showPasswordModal = true}
          class="min-h-[44px] rounded-xl border border-[var(--border)] px-4 py-2 text-sm font-medium
                 text-[var(--fg-muted)] transition hover:bg-[var(--hover)] hover:text-[var(--fg)]">
          Change password
        </button>
        <button onclick={handleLogout}
          class="min-h-[44px] rounded-xl border border-red-200 px-4 py-2 text-sm font-medium
                 text-red-600 transition hover:bg-red-50 dark:border-red-800 dark:text-red-400 dark:hover:bg-red-900/20">
          Sign out
        </button>
      </div>
    </div>

    <!-- Newly created school — sign-in link -->
    {#if createdSchool}
      <div class="mb-6 rounded-2xl border border-emerald-200 bg-emerald-50 p-5 dark:border-emerald-900 dark:bg-emerald-950/20">
        <div class="flex items-start justify-between gap-3">
          <div>
            <p class="text-sm font-semibold text-emerald-800 dark:text-emerald-300">
              {createdSchool.name} is onboarded
            </p>
            <p class="mt-0.5 text-xs text-emerald-700 dark:text-emerald-400">
              Share this link with the school — it's their own branded sign-in page.
            </p>
          </div>
          <button onclick={() => createdSchool = null} aria-label="Dismiss"
            class="shrink-0 text-emerald-700 hover:text-emerald-900 dark:text-emerald-400">
            <svg class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12"/>
            </svg>
          </button>
        </div>
        {#if loginUrl(createdSchool.subdomain)}
          <div class="mt-3 flex items-center gap-2 rounded-xl border border-emerald-200 bg-white px-3 py-2.5 dark:border-emerald-900 dark:bg-[var(--card)]">
            <p class="flex-1 truncate font-mono text-xs text-[var(--fg)]">{loginUrl(createdSchool.subdomain)}</p>
            <button onclick={copyLink}
              class="shrink-0 rounded-lg border border-[var(--border)] px-3 py-1 text-xs font-medium
                     text-[var(--fg-muted)] transition hover:bg-[var(--hover)]">
              {linkCopied ? '✓ Copied' : 'Copy'}
            </button>
          </div>
        {:else}
          <p class="mt-3 text-xs text-emerald-700 dark:text-emerald-400">
            Sign-in link not shown yet — set <code class="font-mono">PUBLIC_PLATFORM_DOMAIN</code> once the platform domain is purchased.
          </p>
        {/if}
      </div>
    {/if}

    <!-- Schools list -->
    <div class="overflow-hidden rounded-2xl border border-[var(--border)] bg-[var(--card)]">
      <div class="flex flex-wrap items-center justify-between gap-3 border-b border-[var(--border)] px-5 py-3">
        <p class="text-[10px] font-bold uppercase tracking-widest text-[var(--fg-subtle)]">
          {filteredSchools.length} of {$schoolsQuery.data?.length ?? 0} school{($schoolsQuery.data?.length ?? 0) !== 1 ? 's' : ''}
        </p>
        {#if ($schoolsQuery.data?.length ?? 0) > 0}
          <input bind:value={search} type="search" placeholder="Search by name or code…"
            class="min-h-[44px] w-full max-w-[220px] rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-1.5 text-xs text-[var(--fg)] placeholder:text-[var(--fg-subtle)] focus:border-[var(--brand)] focus:outline-none" />
        {/if}
      </div>

      {#if $schoolsQuery.isPending}
        <div class="space-y-2 p-4">{#each [1,2,3] as _}<div class="h-12 animate-pulse rounded-xl bg-[var(--hover)]"></div>{/each}</div>
      {:else if ($schoolsQuery.data ?? []).length === 0}
        <div class="px-6 py-14 text-center">
          <p class="text-sm font-medium text-[var(--fg-muted)]">No schools onboarded yet.</p>
          <button onclick={openCreate}
            class="mt-3 rounded-xl px-4 py-2 text-sm font-semibold text-white transition hover:opacity-90"
            style="background-color: var(--brand, #111827)">
            Onboard the first school
          </button>
        </div>
      {:else if filteredSchools.length === 0}
        <p class="px-6 py-10 text-center text-sm text-[var(--fg-muted)]">No school matches "{search}".</p>
      {:else}
        <SchoolsTable schools={filteredSchools} {platformDomain} {loginUrl} {togglingId}
          onEdit={openEdit} onToggleActive={handleToggleActive}
          onDelete={(s) => { deleteTarget = s; deleteError = ''; }} />
      {/if}
    </div>

    <p class="mt-8 text-center text-xs text-[var(--fg-muted)]">TTEK-SMS by Tagnatek</p>
  </div>
</div>

<SchoolForm open={formOpen} school={editingSchool} onSuccess={onFormSuccess}
  onCancel={() => { formOpen = false; editingSchool = null; }} />

<ConfirmModal
  open={!!deactivateTarget}
  title="Disable {deactivateTarget?.name}?"
  message="Every staff member and student at this school will be signed out and blocked from logging in immediately. You can re-enable it here at any time."
  confirmLabel="Disable"
  variant="warning"
  isPending={$toggleMut.isPending}
  onConfirm={() => deactivateTarget && $toggleMut.mutate(deactivateTarget)}
  onCancel={() => deactivateTarget = null}
/>

<ConfirmModal
  open={!!deleteTarget}
  title="Permanently delete {deleteTarget?.name}?"
  message={deleteError || "This cannot be undone. The school record will be permanently removed."}
  confirmLabel="Delete forever"
  variant="danger"
  isPending={$deleteMut.isPending}
  onConfirm={() => deleteTarget && $deleteMut.mutate(deleteTarget)}
  onCancel={() => { deleteTarget = null; deleteError = ''; }}
/>

{#if showPasswordModal}
  <!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
  <div use:portal role="dialog" aria-modal="true" tabindex="-1"
    class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
    onclick={() => showPasswordModal = false} onkeydown={onKeydown}>
    <div class="w-full max-w-sm" onclick={(e) => e.stopPropagation()} role="none">
      <div class="mb-3 flex items-center justify-between">
        <h2 class="text-sm font-semibold text-[var(--fg)]">Change password</h2>
        <button onclick={() => showPasswordModal = false} aria-label="Close"
          class="flex min-h-[44px] min-w-[44px] items-center justify-center rounded-lg text-[var(--fg-muted)]
                 transition hover:bg-[var(--hover)] hover:text-[var(--fg)]">
          <svg class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12"/>
          </svg>
        </button>
      </div>
      <ChangePasswordForm showForgotLink={false} onSuccess={() => showPasswordModal = false} />
    </div>
  </div>
{/if}
