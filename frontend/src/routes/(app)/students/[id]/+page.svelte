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
  import DiagnosticsTab from './DiagnosticsTab.svelte';
  import PhotoAvatar   from './PhotoAvatar.svelte';
  import TabBar        from '$lib/components/TabBar.svelte';

  const qc = useQueryClient();
  const studentId = $derived($page.params.id!);

  const query = createQuery({
    queryKey: ['student', studentId],
    queryFn:  () => getStudent(studentId),
    staleTime: 2 * 60_000,
  });

  type Tab = 'profile' | 'guardians' | 'enrollment' | 'medical' | 'fees' | 'behaviour' | 'diagnostics';
  const TABS = [
    { id: 'profile',     label: 'Profile'     },
    { id: 'guardians',   label: 'Guardians'   },
    { id: 'enrollment',  label: 'Enrollment'  },
    { id: 'fees',        label: 'Fees'        },
    { id: 'medical',     label: 'Medical'     },
    { id: 'behaviour',   label: 'Behaviour'   },
    { id: 'diagnostics', label: 'Diagnostics' },
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
  <div class="mb-6 rounded-2xl border border-[var(--border)] bg-[var(--card)] p-6">
    <div class="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
      <div class="flex items-center gap-4">
        <PhotoAvatar studentId={studentId} firstName={s.first_name} lastName={s.last_name} photoUrl={s.photo_url} canEdit={s.can_edit} />
        <div>
          <h1 class="text-xl font-bold text-[var(--fg)]">{s.display_name}</h1>
          <p class="mt-0.5 font-mono text-sm text-[var(--fg-muted)]">{s.admission_number}</p>
          <div class="mt-2 flex flex-wrap items-center gap-2">
            {#if s.is_active}
              <span class="inline-flex items-center gap-1 text-xs font-semibold text-green-600 dark:text-green-500"><svg class="h-3.5 w-3.5" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24"><polyline points="20 6 9 17 4 12"/></svg>Active</span>
            {:else}
              <span class="rounded-full bg-[var(--hover)] px-2.5 py-0.5 text-xs font-semibold text-[var(--fg-muted)]">Inactive</span>
            {/if}
            {#if s.gender}
              <span class="rounded-full px-2.5 py-0.5 text-xs font-semibold
                {s.gender === 'MALE' ? 'bg-blue-50 text-blue-700 dark:bg-blue-950/30 dark:text-blue-300' : 'bg-pink-50 text-pink-700 dark:bg-pink-950/30 dark:text-pink-300'}">
                {s.gender.charAt(0) + s.gender.slice(1).toLowerCase()}
              </span>
            {/if}
          </div>
        </div>
      </div>

      <div class="flex flex-wrap items-center gap-2 sm:justify-end">
        <button onclick={downloadTranscript} disabled={downloadingTranscript}
          class="rounded-xl border border-[var(--border)] px-3 py-1.5 text-xs font-medium text-[var(--fg-muted)] transition hover:bg-[var(--hover)] disabled:opacity-50">
          {downloadingTranscript ? 'Generating…' : 'Download transcript'}
        </button>
        {#if s.can_manage}
          {#if s.is_active}
            {#if confirmDeactivate}
              <span class="text-xs text-[var(--fg-muted)]">Deactivate this student?</span>
              <button onclick={() => $toggleMut.mutate()} disabled={$toggleMut.isPending}
                class="rounded-xl bg-red-50 px-3 py-1.5 text-xs font-semibold text-red-600 ring-1 ring-inset ring-red-600/20 transition hover:bg-red-100 disabled:opacity-50 dark:bg-red-950/30 dark:text-red-400 dark:hover:bg-red-950/50">
                {$toggleMut.isPending ? 'Deactivating…' : 'Yes, deactivate'}
              </button>
              <button onclick={() => confirmDeactivate = false}
                class="text-xs text-[var(--fg-muted)] hover:text-[var(--fg)] transition">
                Cancel
              </button>
            {:else}
              <button onclick={() => confirmDeactivate = true}
                class="rounded-xl border border-[var(--border)] px-3 py-1.5 text-xs font-medium text-[var(--fg-muted)] transition hover:bg-[var(--hover)]">
                Deactivate
              </button>
            {/if}
          {:else if hasApprovedTransfer && confirmReactivate}
            <span class="text-xs text-amber-600 dark:text-amber-400">This student has an approved transfer on record — reactivating won't undo it. Continue?</span>
            <button onclick={() => $toggleMut.mutate()} disabled={$toggleMut.isPending}
              class="rounded-xl bg-amber-50 px-3 py-1.5 text-xs font-semibold text-amber-700 ring-1 ring-inset ring-amber-600/20 transition hover:bg-amber-100 disabled:opacity-50 dark:bg-amber-950/30 dark:text-amber-400 dark:hover:bg-amber-950/50">
              {$toggleMut.isPending ? '…' : 'Yes, reactivate'}
            </button>
            <button onclick={() => confirmReactivate = false}
              class="text-xs text-[var(--fg-muted)] hover:text-[var(--fg)] transition">
              Cancel
            </button>
          {:else if hasApprovedTransfer}
            <button onclick={() => confirmReactivate = true}
              class="rounded-xl border border-[var(--border)] px-3 py-1.5 text-xs font-medium text-[var(--fg-muted)] transition hover:bg-[var(--hover)]">
              Reactivate
            </button>
          {:else}
            <button onclick={() => $toggleMut.mutate()} disabled={$toggleMut.isPending}
              class="rounded-xl border border-[var(--border)] px-3 py-1.5 text-xs font-medium text-[var(--fg-muted)] transition hover:bg-[var(--hover)] disabled:opacity-50">
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
  {:else if activeTab === 'diagnostics'}
    <DiagnosticsTab studentId={studentId} />
  {/if}
{/if}
