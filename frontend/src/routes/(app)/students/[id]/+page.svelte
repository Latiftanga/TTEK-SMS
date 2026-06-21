<script lang="ts">
  import { page } from '$app/stores';
  import { goto } from '$app/navigation';
  import { createQuery, createMutation, useQueryClient } from '@tanstack/svelte-query';
  import { getStudent, updateStudent } from '$lib/api/students';
  import { toast } from '$lib/stores/toast';
  import ProfileTab    from './ProfileTab.svelte';
  import GuardiansTab  from './GuardiansTab.svelte';
  import EnrollmentTab from './EnrollmentTab.svelte';
  import MedicalTab    from './MedicalTab.svelte';
  import FeesTab       from './FeesTab.svelte';

  const qc = useQueryClient();
  const studentId = $derived($page.params.id);

  const query = createQuery({
    queryKey: ['student', studentId],
    queryFn:  () => getStudent(studentId),
    staleTime: 2 * 60_000,
  });

  type Tab = 'profile' | 'guardians' | 'enrollment' | 'medical' | 'fees';
  const TABS: { key: Tab; label: string }[] = [
    { key: 'profile',    label: 'Profile'    },
    { key: 'guardians',  label: 'Guardians'  },
    { key: 'enrollment', label: 'Enrollment' },
    { key: 'fees',       label: 'Fees'       },
    { key: 'medical',    label: 'Medical'    },
  ];
  const activeTab = $derived(($page.url.searchParams.get('tab') as Tab) ?? 'profile');
  function setTab(t: Tab) { goto(`?tab=${t}`, { replaceState: true, noScroll: true }); }

  const toggleMut = createMutation({
    mutationFn: () => updateStudent(studentId, { is_active: !$query.data!.is_active }),
    onSuccess: (d) => {
      qc.invalidateQueries({ queryKey: ['student', studentId] });
      qc.invalidateQueries({ queryKey: ['students'] });
      toast.success(d.is_active ? 'Student reactivated.' : 'Student deactivated.');
    },
    onError: () => toast.error('Could not update status.'),
  });

  function initials(first: string, last: string) {
    return (first[0] + last[0]).toUpperCase();
  }
</script>

<svelte:head>
  <title>{$query.data?.display_name ?? 'Student'} — Profile</title>
</svelte:head>

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
        <div class="flex h-16 w-16 shrink-0 items-center justify-center rounded-2xl text-xl font-bold text-white shadow"
             style="background: linear-gradient(135deg, var(--brand) 0%, color-mix(in oklab, var(--brand) 65%, #7c3aed) 100%)">
          {initials(s.first_name, s.last_name)}
        </div>
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

      <div class="flex flex-wrap gap-2 sm:justify-end">
        <button onclick={() => $toggleMut.mutate()} disabled={$toggleMut.isPending}
          class="rounded-xl border border-[var(--border)] px-3 py-1.5 text-xs font-medium text-[var(--fg-muted)] transition hover:bg-[var(--hover)] disabled:opacity-50">
          {$toggleMut.isPending ? '…' : s.is_active ? 'Deactivate' : 'Reactivate'}
        </button>
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

  <!-- Tabs -->
  <div class="mb-5 border-b border-[var(--border)]">
    <nav class="-mb-px flex gap-1">
      {#each TABS as tab}
        <button onclick={() => setTab(tab.key)}
          class="relative px-4 pb-3 pt-1 text-sm font-medium transition-colors
                 {activeTab === tab.key ? 'text-[var(--brand)]' : 'text-[var(--fg-muted)] hover:text-[var(--fg)]'}">
          {tab.label}
          <span class="pointer-events-none absolute bottom-0 left-0 right-0 h-0.5 rounded-t-sm
                       {activeTab === tab.key ? 'bg-[var(--brand)]' : 'bg-transparent'}"></span>
        </button>
      {/each}
    </nav>
  </div>

  {#if activeTab === 'profile'}
    <ProfileTab student={s} studentId={studentId} />
  {:else if activeTab === 'guardians'}
    <GuardiansTab student={s} studentId={studentId} />
  {:else if activeTab === 'enrollment'}
    <EnrollmentTab studentId={studentId} />
  {:else if activeTab === 'fees'}
    <FeesTab studentId={studentId} />
  {:else if activeTab === 'medical'}
    <MedicalTab studentId={studentId} medical={s.medical_record} />
  {/if}
{/if}
