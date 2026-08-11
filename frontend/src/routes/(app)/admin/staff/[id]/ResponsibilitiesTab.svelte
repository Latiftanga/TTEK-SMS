<script lang="ts">
  import { createQuery, createMutation, useQueryClient } from '@tanstack/svelte-query';
  import { reactiveQuery } from '$lib/query.svelte';
  import { getStaffResponsibilities, updateStaff, listPositions, type StaffDetail } from '$lib/api/staff';
  import { listYears, listClasses, assignClassTeacher, type AcademicYear, type SchoolClass } from '$lib/api/academic';
  import { listHouses, assignHouseMaster, type House } from '$lib/api/housing';
  import { apiError } from '$lib/utils';
  import { toast } from '$lib/stores/toast';
  import ConfirmModal from '$lib/components/ConfirmModal.svelte';
  import EmptyState from '$lib/components/EmptyState.svelte';

  interface Props { staff: StaffDetail; staffId: string; boardingEnabled: boolean; isOwnProfile?: boolean; }
  const { staff, staffId, boardingEnabled, isOwnProfile = false }: Props = $props();

  const admin = !isOwnProfile;
  const qc = useQueryClient();
  const invalidateStaff = () => qc.invalidateQueries({ queryKey: ['staff', staffId] });
  const invalidateResps = () => qc.invalidateQueries({ queryKey: ['staff-responsibilities', staffId] });

  // ── Data ──────────────────────────────────────────────────────────────────────
  const respsQ = createQuery({ queryKey: ['staff-responsibilities', staffId], queryFn: () => getStaffResponsibilities(staffId), staleTime: 2 * 60_000 });
  const posQ   = createQuery({ queryKey: ['positions'], queryFn: listPositions, enabled: admin, staleTime: 10 * 60_000 });

  // Lazy — only fetch when the assign form is open
  let showForm = $state(false);
  const yearsQ   = reactiveQuery<AcademicYear[]>(() => ({ queryKey: ['years'],   queryFn: listYears,   enabled: admin && showForm, staleTime: 5 * 60_000 }));
  const classesQ = reactiveQuery<SchoolClass[]>(() => ({ queryKey: ['classes'], queryFn: listClasses, enabled: admin && showForm, staleTime: 5 * 60_000 }));
  const housesQ  = reactiveQuery<House[]>(() => ({ queryKey: ['houses'],  queryFn: listHouses,  enabled: admin && showForm && boardingEnabled, staleTime: 5 * 60_000 }));

  // ── Form state ────────────────────────────────────────────────────────────────
  let assignType = $state('');   // 'pos:{id}' | 'class_teacher' | 'house_master'
  let selClass   = $state('');
  let selYear    = $state('');
  let selHouse   = $state('');
  let formError  = $state('');

  const isPos = $derived(assignType.startsWith('pos:'));
  const posId = $derived(isPos ? assignType.slice(4) : '');

  const availablePos = $derived(($posQ.data ?? []).filter(p => !staff.position_ids.includes(p.id)));

  const canSubmit = $derived(
    !!assignType && (
      isPos ||
      (assignType === 'class_teacher' && !!selClass && !!selYear) ||
      (assignType === 'house_master'  && !!selHouse && !!selYear)
    )
  );

  function resetForm() { assignType = ''; selClass = ''; selYear = ''; selHouse = ''; formError = ''; }
  function onTypeChange() { selClass = ''; selYear = ''; selHouse = ''; formError = ''; }

  // ── Mutations ─────────────────────────────────────────────────────────────────
  const assignMut = createMutation({
    mutationFn: async () => {
      if (isPos)                            return updateStaff(staffId, { position_ids: [...new Set([...staff.position_ids, posId])] });
      if (assignType === 'class_teacher')  return assignClassTeacher(selClass, { staff_member_id: staffId, academic_year_id: selYear });
      if (assignType === 'house_master')   return assignHouseMaster(selHouse, { staff_member_id: staffId, academic_year_id: selYear });
      throw new Error('No type selected');
    },
    onSuccess: () => {
      isPos ? invalidateStaff() : invalidateResps();
      showForm = false; resetForm();
      toast.success('Responsibility assigned.');
    },
    onError: (e) => { formError = apiError(e, 'Failed to assign.'); },
  });

  const removePosMut = createMutation({
    mutationFn: (pid: string) => updateStaff(staffId, { position_ids: staff.position_ids.filter(id => id !== pid) }),
    onSuccess: () => invalidateStaff(),
    onError:   (e) => toast.error(apiError(e, 'Failed to remove.')),
  });

  let confirmRemovePosId = $state<string | null>(null);

  // ── Flat list ─────────────────────────────────────────────────────────────────
  type Row = { key: string; label: string; detail: string | null; active: boolean; posId?: string };
  const rows = $derived.by((): Row[] => {
    const list: Row[] = [];
    staff.position_ids.forEach((id, i) =>
      list.push({ key: `pos:${id}`, label: staff.position_names[i] ?? '', detail: null, active: true, posId: id })
    );
    const d = $respsQ.data;
    if (d?.class_teacher) {
      const ct = d.class_teacher;
      list.push({ key: `ct:${ct.class_id}`, label: 'Class Teacher', detail: `${ct.class_name} · ${ct.academic_year_name}`, active: ct.is_active });
    }
    for (const s of d?.subject_assignments ?? [])
      list.push({ key: `st:${s.subject_id}:${s.class_id}:${s.academic_year_id}`, label: s.subject_name, detail: `${s.class_name} · ${s.academic_year_name}`, active: s.is_active });
    for (const h of d?.house_assignments ?? [])
      list.push({ key: `hm:${h.house_id}:${h.academic_year_id}`, label: 'House Master', detail: `${h.house_name} · ${h.academic_year_name}`, active: h.is_active });
    return list;
  });

  const sel = 'w-full rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--fg)] focus:border-[var(--brand)] focus:outline-none disabled:opacity-50';
</script>

<div class="space-y-4">

  <!-- Header -->
  <div class="flex items-center justify-between">
    <h3 class="text-xs font-semibold uppercase tracking-widest text-[var(--fg-muted)]">Responsibilities</h3>
    {#if admin && !showForm}
      <button onclick={() => showForm = true} class="text-xs font-semibold text-[var(--brand)] hover:underline">+ Assign</button>
    {/if}
  </div>

  <!-- Assign form -->
  {#if showForm}
    <div class="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4 space-y-3">

      <!-- Responsibility type -->
      <div>
        <label class="mb-1 block text-xs font-medium text-[var(--fg-muted)]">Responsibility *</label>
        <select bind:value={assignType} onchange={onTypeChange} class={sel}>
          <option value="">Select…</option>
          {#if availablePos.length}
            <optgroup label="Authority">
              {#each availablePos as p (p.id)}<option value="pos:{p.id}">{p.name}</option>{/each}
            </optgroup>
          {/if}
          <optgroup label="Academic">
            <option value="class_teacher">Class Teacher</option>
          </optgroup>
          {#if boardingEnabled}
            <optgroup label="Boarding">
              <option value="house_master">House Master</option>
            </optgroup>
          {/if}
        </select>
      </div>

      <!-- Cascading: Class Teacher -->
      {#if assignType === 'class_teacher'}
        <div class="grid gap-3 sm:grid-cols-2">
          <div>
            <label class="mb-1 block text-xs font-medium text-[var(--fg-muted)]">Class *</label>
            <select bind:value={selClass} class={sel}>
              <option value="">Select class…</option>
              {#each $classesQ.data ?? [] as c (c.id)}<option value={c.id}>{c.display_name}</option>{/each}
            </select>
          </div>
          <div>
            <label class="mb-1 block text-xs font-medium text-[var(--fg-muted)]">Academic year *</label>
            <select bind:value={selYear} class={sel}>
              <option value="">Select year…</option>
              {#each $yearsQ.data ?? [] as y (y.id)}<option value={y.id}>{y.name}</option>{/each}
            </select>
          </div>
        </div>

      <!-- Cascading: House Master -->
      {:else if assignType === 'house_master'}
        <div class="grid gap-3 sm:grid-cols-2">
          <div>
            <label class="mb-1 block text-xs font-medium text-[var(--fg-muted)]">House *</label>
            <select bind:value={selHouse} class={sel}>
              <option value="">Select house…</option>
              {#each $housesQ.data ?? [] as h (h.id)}<option value={h.id}>{h.name} ({h.code})</option>{/each}
            </select>
          </div>
          <div>
            <label class="mb-1 block text-xs font-medium text-[var(--fg-muted)]">Academic year *</label>
            <select bind:value={selYear} class={sel}>
              <option value="">Select year…</option>
              {#each $yearsQ.data ?? [] as y (y.id)}<option value={y.id}>{y.name}</option>{/each}
            </select>
          </div>
        </div>
      {/if}

      {#if formError}<p class="text-xs text-red-500">{formError}</p>{/if}
      <div class="flex gap-2">
        <button onclick={() => $assignMut.mutate()} disabled={$assignMut.isPending || !canSubmit}
          class="rounded-xl px-4 py-2 text-sm font-semibold text-white transition hover:opacity-90 disabled:opacity-50"
          style="background-color: var(--brand)">{$assignMut.isPending ? 'Saving…' : 'Assign'}</button>
        <button onclick={() => { showForm = false; resetForm(); }}
          class="rounded-xl border border-[var(--border)] px-4 py-2 text-sm text-[var(--fg-muted)] hover:bg-[var(--hover)]">Cancel</button>
      </div>
    </div>
  {/if}

  <!-- Flat list -->
  {#if $respsQ.isPending && !staff.position_ids.length}
    <div class="space-y-2">
      {#each [1, 2] as _}<div class="skeleton h-12"></div>{/each}
    </div>
  {:else if rows.length === 0}
    <EmptyState
      iconPath="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-3 7h3m-3 4h3m-6-4h.01M9 16h.01"
      title="No responsibilities assigned yet."
      description="Use the form above to assign a position, class, or house."
    />
  {:else}
    <div class="overflow-hidden rounded-xl border border-[var(--border)] bg-[var(--card)]">
      {#each rows as row, i (row.key)}
        <div class="flex items-center gap-3 px-4 py-3 {i > 0 ? 'border-t border-[var(--border)]' : ''}">
          <span class="h-2 w-2 shrink-0 rounded-full {row.active ? 'bg-emerald-500' : 'bg-[var(--fg-muted)]'}"></span>
          <div class="min-w-0 flex-1">
            <p class="text-sm font-medium text-[var(--fg)]">{row.label}</p>
            {#if row.detail}<p class="text-xs text-[var(--fg-muted)]">{row.detail}</p>{/if}
          </div>
          {#if admin && row.posId}
            <button onclick={() => confirmRemovePosId = row.posId!} disabled={$removePosMut.isPending}
              class="shrink-0 text-xs text-[var(--fg-muted)] transition hover:text-red-500 disabled:opacity-50">
              Remove
            </button>
          {/if}
        </div>
      {/each}
    </div>
  {/if}
</div>

<ConfirmModal
  open={!!confirmRemovePosId}
  title="Remove position?"
  message="This position and its permission template will be removed from the staff member. Their personal permission overrides are unaffected."
  confirmLabel="Remove"
  isPending={$removePosMut.isPending}
  onConfirm={() => { $removePosMut.mutate(confirmRemovePosId!); confirmRemovePosId = null; }}
  onCancel={() => confirmRemovePosId = null}
/>
