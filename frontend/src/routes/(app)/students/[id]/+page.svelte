<script lang="ts">
  import { page } from '$app/stores';
  import { goto } from '$app/navigation';
  import { createQuery, createMutation, useQueryClient } from '@tanstack/svelte-query';
  import { getStudent, updateStudent, listTransfersForStudent } from '$lib/api/students';
  import { getTranscriptBlob } from '$lib/api/reports';
  import { toast } from '$lib/stores/toast';
  import { setPageTitle } from '$lib/stores/title';
  import ProfileTab    from './ProfileTab.svelte';
  import GuardiansTab  from './GuardiansTab.svelte';
  import EnrollmentTab from './EnrollmentTab.svelte';
  import MedicalTab    from './MedicalTab.svelte';
  import FeesTab       from './FeesTab.svelte';
  import BehaviourTab  from './BehaviourTab.svelte';
  import PhotoAvatar   from './PhotoAvatar.svelte';
  import TabBar        from '$lib/components/TabBar.svelte';
  import Badge         from '$lib/components/Badge.svelte';
  import ConfirmModal  from '$lib/components/ConfirmModal.svelte';
  import DocumentsPanel from '$lib/components/DocumentsPanel.svelte';

  const qc = useQueryClient();
  const studentId = $derived($page.params.id!);

  const query = createQuery({
    queryKey: ['student', studentId],
    queryFn:  () => getStudent(studentId),
    staleTime: 2 * 60_000,
  });

  type Tab = 'profile' | 'guardians' | 'enrollment' | 'medical' | 'fees' | 'behaviour' | 'documents';
  // Icons let TabBar collapse to icon-only on mobile (label reappears from
  // sm: up) — without them every tab shows full text and 6 of them overflow
  // into an unstyled horizontal scroll on a phone. Same fix already applied
  // to admin/staff/[id]/+page.svelte's tabs.
  const TABS = [
    { id: 'profile',    label: 'Profile',
      icon: '<path stroke-linecap="round" stroke-linejoin="round" d="M15.75 6a3.75 3.75 0 11-7.5 0 3.75 3.75 0 017.5 0zM4.501 20.118a7.5 7.5 0 0114.998 0A17.933 17.933 0 0112 21.75c-2.676 0-5.216-.584-7.499-1.632z"/>' },
    { id: 'guardians',  label: 'Guardians',
      icon: '<path stroke-linecap="round" stroke-linejoin="round" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z"/>' },
    { id: 'enrollment', label: 'Enrollment',
      icon: '<path stroke-linecap="round" stroke-linejoin="round" d="M4.26 10.147a60.436 60.436 0 00-.491 6.347A48.627 48.627 0 0112 20.904a48.627 48.627 0 018.232-4.41 60.46 60.46 0 00-.491-6.347m-15.482 0a50.57 50.57 0 00-2.658-.813A59.905 59.905 0 0112 3.493a59.902 59.902 0 0110.399 5.84c-.896.248-1.783.52-2.658.814m-15.482 0A50.697 50.697 0 0112 13.489a50.702 50.702 0 017.74-3.342"/>' },
    { id: 'fees',       label: 'Fees',
      icon: '<path stroke-linecap="round" stroke-linejoin="round" d="M3 10h18M7 15h1m4 0h1m-7 4h12a3 3 0 003-3V8a3 3 0 00-3-3H6a3 3 0 00-3 3v8a3 3 0 003 3z"/>' },
    { id: 'medical',    label: 'Medical',
      icon: '<path stroke-linecap="round" stroke-linejoin="round" d="M21 8.25c0-2.485-2.099-4.5-4.688-4.5-1.935 0-3.597 1.126-4.312 2.733-.715-1.607-2.377-2.733-4.313-2.733C5.1 3.75 3 5.765 3 8.25c0 7.22 9 12 9 12s9-4.78 9-12z"/>' },
    { id: 'behaviour',  label: 'Behaviour',
      icon: '<path stroke-linecap="round" stroke-linejoin="round" d="M9 12h3.75M9 15h3.75M9 18h3.75m3 .75H18a2.25 2.25 0 002.25-2.25V6.108c0-1.135-.845-2.098-1.976-2.192a48.424 48.424 0 00-1.123-.08m-5.801 0c-.065.21-.1.433-.1.664 0 .414.336.75.75.75h4.5a.75.75 0 00.75-.75 2.25 2.25 0 00-.1-.664m-5.8 0A2.251 2.251 0 0113.5 2.25H15c1.012 0 1.867.668 2.15 1.586m-5.8 0c-.376.023-.75.05-1.124.08C9.095 4.01 8.25 4.973 8.25 6.108V8.25m0 0H4.875c-.621 0-1.125.504-1.125 1.125v11.25c0 .621.504 1.125 1.125 1.125h9.75c.621 0 1.125-.504 1.125-1.125V9.375c0-.621-.504-1.125-1.125-1.125H8.25z"/>' },
    { id: 'documents',  label: 'Documents',
      icon: '<path stroke-linecap="round" stroke-linejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z"/>' },
  ];
  const activeTab = $derived(($page.url.searchParams.get('tab') as Tab) ?? 'profile');
  function setTab(id: string) { goto(`?tab=${id}`, { replaceState: true, noScroll: true }); }

  let confirmDeactivate = $state(false);
  let confirmReactivate = $state(false);

  const transfersQ = createQuery({
    queryKey: ['student-transfers', studentId],
    queryFn:  () => listTransfersForStudent(studentId),
    staleTime: 30_000,
  });
  const hasApprovedTransfer = $derived(($transfersQ.data ?? []).some(t => t.status === 'APPROVED'));

  const toggleMut = createMutation({
    mutationFn: () => updateStudent(studentId, { is_active: !$query.data!.is_active }),
    onSuccess: (d) => {
      qc.invalidateQueries({ queryKey: ['student', studentId] });
      qc.invalidateQueries({ queryKey: ['students'] });
      confirmDeactivate = false;
      confirmReactivate = false;
      toast.success(d.is_active ? 'Student reactivated.' : 'Student deactivated.');
    },
    onError: () => { confirmDeactivate = false; confirmReactivate = false; toast.error('Could not update status.'); },
  });

  let downloadingTranscript = $state(false);
  async function downloadTranscript() {
    if (downloadingTranscript) return;
    downloadingTranscript = true;
    try {
      const blob = await getTranscriptBlob(studentId);
      const url = URL.createObjectURL(blob);
      window.open(url, '_blank');
      setTimeout(() => URL.revokeObjectURL(url), 30_000);
    } catch {
      toast.error('Could not generate the transcript. Try again in a moment.');
    } finally {
      downloadingTranscript = false;
    }
  }

  $effect(() => setPageTitle($query.data?.display_name ?? 'Student'));
</script>

<div class="mb-2">
  <button onclick={() => goto('/students')}
    class="flex items-center gap-1 text-xs text-[var(--fg-muted)] hover:text-[var(--fg)] transition">
    <svg class="h-3.5 w-3.5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
      <path stroke-linecap="round" stroke-linejoin="round" d="M10.5 19.5L3 12m0 0l7.5-7.5M3 12h18"/>
    </svg>
    All students
  </button>
</div>

{#if $query.isPending}
  <div class="animate-pulse space-y-4">
    <div class="h-32 rounded-2xl bg-[var(--card)]"></div>
    <div class="h-64 rounded-2xl bg-[var(--card)]"></div>
  </div>
{:else if $query.isError}
  <div class="rounded-xl bg-red-50 dark:bg-red-950/30 p-4 text-sm text-red-600 dark:text-red-400">
    Could not load student. They may have been deleted or you may not have access.
  </div>
{:else if $query.data}
  {@const s = $query.data}

  <!-- Card header -->
  <div class="mb-6 overflow-hidden rounded-2xl border border-[var(--border)] bg-[var(--card)]">
    <!-- Accent bar — matches admin/staff/[id]'s hero card -->
    <div class="h-1.5" style="background: linear-gradient(90deg, var(--brand) 0%, color-mix(in oklab, var(--brand) 55%, #7c3aed) 100%)"></div>

    <div class="p-6">
      <div class="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div class="flex min-w-0 items-center gap-4">
          <PhotoAvatar studentId={studentId} firstName={s.first_name} lastName={s.last_name} photoUrl={s.photo_url} canEdit={s.can_edit} />
          <div class="min-w-0">
            <h1 class="truncate text-xl font-bold text-[var(--fg)]">{s.display_name}</h1>
            <p class="mt-0.5 font-mono text-sm text-[var(--fg-muted)]">{s.admission_number}</p>
            <div class="mt-2 flex flex-wrap items-center gap-2">
              <Badge label={s.is_active ? 'Active' : 'Inactive'} color={s.is_active ? 'green' : 'gray'} variant="dot" />
              {#if s.gender}
                <Badge label={s.gender.charAt(0) + s.gender.slice(1).toLowerCase()} color={s.gender === 'MALE' ? 'blue' : 'violet'} variant="solid" />
              {/if}
            </div>
          </div>
        </div>

        <div class="flex flex-wrap items-center gap-2 sm:justify-end">
          <button onclick={downloadTranscript} disabled={downloadingTranscript}
            class="min-h-[44px] rounded-xl border border-[var(--border)] px-3 py-1.5 text-xs font-medium text-[var(--fg-muted)] transition hover:bg-[var(--hover)] disabled:opacity-50">
            {downloadingTranscript ? 'Generating…' : 'Download transcript'}
          </button>
          {#if s.can_manage}
            {#if s.is_active}
              <button onclick={() => confirmDeactivate = true}
                class="min-h-[44px] rounded-xl border border-[var(--border)] px-3 py-1.5 text-xs font-medium text-[var(--fg-muted)] transition hover:bg-[var(--hover)]">
                Deactivate
              </button>
            {:else if hasApprovedTransfer}
              <button onclick={() => confirmReactivate = true}
                class="min-h-[44px] rounded-xl border border-[var(--border)] px-3 py-1.5 text-xs font-medium text-[var(--fg-muted)] transition hover:bg-[var(--hover)]">
                Reactivate
              </button>
            {:else}
              <button onclick={() => $toggleMut.mutate()} disabled={$toggleMut.isPending}
                class="min-h-[44px] rounded-xl border border-[var(--border)] px-3 py-1.5 text-xs font-medium text-[var(--fg-muted)] transition hover:bg-[var(--hover)] disabled:opacity-50">
                {$toggleMut.isPending ? '…' : 'Reactivate'}
              </button>
            {/if}
          {/if}
        </div>
      </div>

      <!-- Quick stats -->
      <div class="mt-4 grid grid-cols-2 gap-3 border-t border-[var(--border)] pt-4 sm:grid-cols-4">
        <div>
          <p class="text-[10px] font-semibold uppercase tracking-widest text-[var(--fg-subtle)]">Date of birth</p>
          <p class="mt-0.5 text-sm font-medium text-[var(--fg)]">{s.date_of_birth ?? '—'}</p>
        </div>
        <div>
          <p class="text-[10px] font-semibold uppercase tracking-widest text-[var(--fg-subtle)]">Nationality</p>
          <p class="mt-0.5 text-sm font-medium text-[var(--fg)]">{s.nationality ?? '—'}</p>
        </div>
        <div>
          <p class="text-[10px] font-semibold uppercase tracking-widest text-[var(--fg-subtle)]">Guardians</p>
          <p class="mt-0.5 text-sm font-medium text-[var(--fg)]">{s.guardians.length}</p>
        </div>
        <div>
          <p class="text-[10px] font-semibold uppercase tracking-widest text-[var(--fg-subtle)]">Religion</p>
          <p class="mt-0.5 text-sm font-medium text-[var(--fg)]">{s.religion ?? '—'}</p>
        </div>
      </div>
    </div>
  </div>

  <div class="mb-5">
    <TabBar tabs={TABS} active={activeTab} onchange={setTab} />
  </div>

  {#if activeTab === 'profile'}
    <ProfileTab student={s} studentId={studentId} />
  {:else if activeTab === 'guardians'}
    <GuardiansTab student={s} studentId={studentId} />
  {:else if activeTab === 'enrollment'}
    <EnrollmentTab studentId={studentId} canEdit={s.can_edit} canManage={s.can_manage} />
  {:else if activeTab === 'fees'}
    <FeesTab studentId={studentId} />
  {:else if activeTab === 'medical'}
    <MedicalTab studentId={studentId} medical={s.medical_record} canEdit={s.can_edit} />
  {:else if activeTab === 'behaviour'}
    <BehaviourTab studentId={studentId} canEdit={s.can_edit} />
  {:else if activeTab === 'documents'}
    <DocumentsPanel entityType="student" entityId={studentId} />
  {/if}

  <ConfirmModal
    open={confirmDeactivate}
    title="Deactivate student?"
    message="{s.display_name} will no longer appear in active lists. This can be reversed later."
    confirmLabel="Deactivate"
    variant="danger"
    isPending={$toggleMut.isPending}
    onConfirm={() => $toggleMut.mutate()}
    onCancel={() => confirmDeactivate = false}
  />

  <ConfirmModal
    open={confirmReactivate}
    title="Reactivate student?"
    message="This student has an approved transfer on record — reactivating won't undo it. Continue?"
    confirmLabel="Reactivate"
    variant="warning"
    isPending={$toggleMut.isPending}
    onConfirm={() => $toggleMut.mutate()}
    onCancel={() => confirmReactivate = false}
  />
{/if}
