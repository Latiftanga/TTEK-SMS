<script lang="ts">
  import { createQuery, createMutation, useQueryClient } from '@tanstack/svelte-query';
  import { listYears, getClassTeacher, assignClassTeacher, type AcademicYear } from '$lib/api/academic';
  import { listStaff, type StaffSummary } from '$lib/api/staff';
  import { portal } from '$lib/actions/portal';
  import { toast } from '$lib/stores/toast';

  interface Props { classId: string; className: string; currentYearId: string; onClose: () => void; }
  const { classId, className, currentYearId, onClose }: Props = $props();

  const qc = useQueryClient();

  const yearsQ = createQuery({ queryKey: ['years'], queryFn: listYears, staleTime: 5 * 60_000 });
  const staffQ = createQuery({ queryKey: ['staff'], queryFn: () => listStaff({ limit: 200 }), staleTime: 5 * 60_000 });

  const years = $derived<AcademicYear[]>([...($yearsQ.data ?? [])].sort((a, b) => b.start_date.localeCompare(a.start_date)));
  const staff = $derived<StaffSummary[]>($staffQ.data ?? []);

  let selectedYearId = $state('');
  $effect(() => {
    if (!selectedYearId && years.length)
      selectedYearId = years.find(y => y.is_current)?.id ?? years[0]?.id ?? '';
  });

  const classTchrQ = createQuery({
    queryKey: () => ['class-teacher', classId, selectedYearId],
    queryFn:  () => getClassTeacher(classId, selectedYearId),
    enabled:  () => !!selectedYearId,
    staleTime: 60_000,
  });

  const classTeacher   = $derived($classTchrQ.data ?? null);
  const staffMap       = $derived(new Map(staff.map(s => [s.id, s])));
  const currentTeacher = $derived(classTeacher ? staffMap.get(classTeacher.staff_member_id) : null);

  let showPicker  = $state(false);
  let staffSearch = $state('');
  let pickedStaff = $state('');

  const teachingStaff = $derived(
    staff.filter(s => s.is_active && s.staff_type === 'TEACHING' &&
      (!staffSearch || s.display_name.toLowerCase().includes(staffSearch.toLowerCase())))
  );

  function openPicker() { showPicker = true; staffSearch = ''; pickedStaff = classTeacher?.staff_member_id ?? ''; }
  function closePicker() { showPicker = false; staffSearch = ''; pickedStaff = ''; }

  const assignMut = createMutation({
    mutationFn: () => assignClassTeacher(classId, { staff_member_id: pickedStaff, academic_year_id: selectedYearId }),
    onSuccess: (ct) => {
      qc.setQueryData(['class-teacher', classId, selectedYearId], ct);
      closePicker();
      toast.success('Class teacher assigned.');
    },
    onError: (e: unknown) => toast.error((e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? 'Failed to assign teacher.'),
  });
</script>

<div use:portal class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
  <div class="w-full max-w-sm rounded-2xl border border-[var(--border)] bg-[var(--card)] shadow-2xl">

    <!-- Header -->
    <div class="flex items-center justify-between border-b border-[var(--border)] px-6 py-4">
      <div>
        <h2 class="text-base font-semibold text-[var(--fg)]">Class Teacher</h2>
        <p class="text-xs text-[var(--fg-muted)]">{className}</p>
      </div>
      <button onclick={onClose} class="rounded-lg p-1.5 text-[var(--fg-muted)] transition hover:bg-[var(--hover)] hover:text-[var(--fg)]">
        <svg class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12"/></svg>
      </button>
    </div>

    <div class="space-y-4 p-6">
      <!-- Year selector -->
      <label class="block">
        <span class="mb-1 block text-xs font-medium text-[var(--fg-muted)]">Academic Year</span>
        <select bind:value={selectedYearId}
          class="w-full rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--fg)] transition focus:border-[var(--brand)] focus:outline-none">
          {#each years as y}<option value={y.id}>{y.name}{y.is_current ? ' (current)' : ''}</option>{/each}
        </select>
      </label>

      <!-- Current teacher card -->
      {#if !selectedYearId || $classTchrQ.isPending}
        <div class="h-14 animate-pulse rounded-xl bg-[var(--hover)]"></div>
      {:else}
        <div class="flex items-center gap-4 rounded-xl border border-[var(--border)] bg-[var(--bg)] p-4">
          <div class="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-[var(--hover)] text-sm font-bold text-[var(--fg)]">
            {(currentTeacher?.display_name?.[0] ?? '?').toUpperCase()}
          </div>
          <div class="min-w-0 flex-1">
            {#if currentTeacher}
              <p class="font-medium text-[var(--fg)]">{currentTeacher.display_name}</p>
              {#if currentTeacher.position_names?.length}
                <p class="text-xs text-[var(--fg-muted)]">{currentTeacher.position_names.join(', ')}</p>
              {/if}
            {:else}
              <p class="text-sm italic text-[var(--fg-subtle)]">No teacher assigned for this year.</p>
            {/if}
          </div>
          <button onclick={openPicker} class="btn-ghost">
            {currentTeacher ? 'Change' : 'Assign'}
          </button>
        </div>
      {/if}

      <!-- Staff picker (inline expand) -->
      {#if showPicker}
        <div class="space-y-2 rounded-xl border border-[var(--border)] p-3">
          <input bind:value={staffSearch} placeholder="Search teaching staff…" autofocus
            class="w-full rounded-lg border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--fg)] transition focus:border-[var(--brand)] focus:outline-none" />
          <div class="max-h-44 divide-y divide-[var(--border)] overflow-y-auto rounded-lg border border-[var(--border)]">
            {#if teachingStaff.length === 0}
              <p class="px-3 py-4 text-center text-sm text-[var(--fg-muted)]">No teaching staff found.</p>
            {:else}
              {#each teachingStaff as s}
                <button onclick={() => pickedStaff = s.id}
                  class="w-full px-3 py-2 text-left text-sm transition hover:bg-[var(--hover)] {pickedStaff === s.id ? 'bg-[var(--hover)] font-medium' : ''}">
                  {s.display_name}{s.position_names?.length ? ` · ${s.position_names.join(', ')}` : ''}
                </button>
              {/each}
            {/if}
          </div>
          <div class="flex justify-end gap-2 pt-1">
            <button onclick={closePicker} class="btn-ghost">Cancel</button>
            <button onclick={() => $assignMut.mutate()} disabled={!pickedStaff || $assignMut.isPending} class="btn-primary">
              {$assignMut.isPending ? 'Saving…' : 'Confirm'}
            </button>
          </div>
        </div>
      {/if}
    </div>

  </div>
</div>
