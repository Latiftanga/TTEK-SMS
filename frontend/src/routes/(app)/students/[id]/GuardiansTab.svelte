<script lang="ts">
  import { createMutation, useQueryClient } from '@tanstack/svelte-query';
  import {
    addGuardian, updateGuardian, removeGuardian,
    type StudentDetail, type Guardian, type GuardianCreate, type GuardianUpdate,
  } from '$lib/api/students';
  import { detailOf } from '$lib/apiError';
  import { toast } from '$lib/stores/toast';
  import ConfirmModal from '$lib/components/ConfirmModal.svelte';
  import PortalAccessCard from './PortalAccessCard.svelte';
  import GuardianPortalAccessButton from './GuardianPortalAccessButton.svelte';
  import GuardianForm, { type GuardianFormData } from './GuardianForm.svelte';

  interface Props { student: StudentDetail; studentId: string; }
  const { student, studentId }: Props = $props();

  const qc = useQueryClient();
  const EMPTY_FORM: GuardianFormData = {
    first_name: '', last_name: '', phone: '', email: '',
    occupation: '', address: '', relation_type: 'Parent', is_primary: false,
  };

  // Create/update take slightly different shapes for an unset optional field
  // (undefined vs. explicit null) — the form itself is shape-agnostic and
  // just hands back trimmed strings; each mutation maps to what its schema
  // actually wants.
  function toCreate(data: GuardianFormData): GuardianCreate {
    return { ...data, email: data.email || undefined, occupation: data.occupation || undefined, address: data.address || undefined };
  }
  function toUpdate(data: GuardianFormData): GuardianUpdate {
    return { ...data, email: data.email || null, occupation: data.occupation || null, address: data.address || null };
  }

  // ── Add ───────────────────────────────────────────────────────────────────────
  let showForm  = $state(false);
  let formError = $state('');

  const addMut = createMutation({
    mutationFn: (data: GuardianFormData) => addGuardian(studentId, toCreate(data)),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['student', studentId] });
      showForm = false; formError = '';
      toast.success('Guardian added.');
    },
    onError: (e: unknown) => { formError = detailOf(e) ?? 'Could not add guardian.'; },
  });

  // ── Edit ──────────────────────────────────────────────────────────────────────
  let editingId = $state<string | null>(null);
  let editError = $state('');

  function startEdit(g: Guardian) { editingId = g.guardian_id; editError = ''; }
  function cancelEdit() { editingId = null; editError = ''; }

  const updateMut = createMutation({
    mutationFn: ({ gid, data }: { gid: string; data: GuardianFormData }) =>
      updateGuardian(studentId, gid, toUpdate(data)),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['student', studentId] });
      editingId = null; editError = '';
      toast.success('Guardian updated.');
    },
    onError: (e: unknown) => { editError = detailOf(e) ?? 'Could not update guardian.'; },
  });

  // ── Remove ────────────────────────────────────────────────────────────────────
  let confirmRemoveGid = $state<string | null>(null);
  const removeMut = createMutation({
    mutationFn: ({ gid }: { gid: string }) => removeGuardian(studentId, gid),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['student', studentId] });
      toast.success('Guardian removed.');
    },
    onError: () => toast.error('Could not remove guardian.'),
  });
</script>

<div class="space-y-4">
  <div class="flex items-center justify-between">
    <p class="text-sm text-[var(--fg-muted)]">People responsible for this student.</p>
    {#if student.can_edit}
      <button onclick={() => { showForm = !showForm; formError = ''; editingId = null; }}
        class="flex items-center gap-1.5 rounded-xl px-3 py-1.5 text-xs font-semibold text-white transition hover:opacity-90" style="background: var(--brand)">
        <svg class="h-3.5 w-3.5" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" d="M12 4v16m8-8H4"/>
        </svg>
        Add guardian
      </button>
    {/if}
  </div>

  {#if showForm && student.can_edit}
    <div class="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
      <h3 class="mb-3 text-sm font-semibold text-[var(--fg)]">New guardian</h3>
      <GuardianForm
        idPrefix="gt" initial={EMPTY_FORM} submitLabel="Add guardian"
        pending={$addMut.isPending} serverError={formError}
        onSubmit={(d) => { formError = ''; $addMut.mutate(d); }}
        onCancel={() => { showForm = false; formError = ''; }}
      />
    </div>
  {/if}

  {#if student.guardians.length === 0}
    <div class="rounded-xl border border-dashed border-[var(--border)] p-8 text-center">
      <svg class="mx-auto mb-2 h-8 w-8 text-[var(--fg-subtle)]" fill="none" stroke="currentColor" stroke-width="1.5" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" d="M18 18.72a9.094 9.094 0 003.741-.479 3 3 0 00-4.682-2.72m.94 3.198l.001.031c0 .225-.012.447-.037.666A11.944 11.944 0 0112 21c-2.17 0-4.207-.576-5.963-1.584A6.062 6.062 0 016 18.719m12 0a5.971 5.971 0 00-.941-3.197m0 0A5.995 5.995 0 0012 12.75a5.995 5.995 0 00-5.058 2.772m0 0a3 3 0 00-4.681 2.72 8.986 8.986 0 003.74.477m.94-3.197a5.971 5.971 0 00-.94 3.197M15 6.75a3 3 0 11-6 0 3 3 0 016 0zm6 3a2.25 2.25 0 11-4.5 0 2.25 2.25 0 014.5 0zm-13.5 0a2.25 2.25 0 11-4.5 0 2.25 2.25 0 014.5 0z"/>
      </svg>
      <p class="text-sm text-[var(--fg-muted)]">No guardians added yet.</p>
    </div>
  {:else}
    <div class="space-y-2">
      {#each student.guardians as g (g.guardian_id)}
        <div class="rounded-xl border border-[var(--border)] bg-[var(--card)]">

          <!-- Guardian row -->
          <div class="flex items-center gap-4 px-4 py-3">
            <div class="flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-xs font-bold text-white" style="background: var(--brand)">
              {g.first_name[0]}{g.last_name[0]}
            </div>
            <div class="min-w-0 flex-1">
              <div class="flex items-center gap-2 flex-wrap">
                <p class="text-sm font-semibold text-[var(--fg)]">{g.first_name} {g.last_name}</p>
                <span class="rounded-full bg-[var(--hover)] px-2 py-0.5 text-[10px] font-medium text-[var(--fg-muted)]">{g.relation_type}</span>
                {#if g.is_primary}
                  <span class="rounded-full bg-blue-50 px-2 py-0.5 text-[10px] font-bold text-blue-700 ring-1 ring-inset ring-blue-600/20 dark:bg-blue-950/30 dark:text-blue-300">Primary</span>
                {/if}
              </div>
              <p class="text-xs text-[var(--fg-muted)]">
                {g.phone}{g.email ? ` · ${g.email}` : ''}{g.occupation ? ` · ${g.occupation}` : ''}{g.address ? ` · ${g.address}` : ''}
              </p>
            </div>
            <div class="shrink-0 flex items-center gap-1">
              <GuardianPortalAccessButton guardian={g} {studentId} canManage={student.can_manage} />
              {#if student.can_edit}
                <button onclick={() => editingId === g.guardian_id ? cancelEdit() : startEdit(g)}
                  aria-label="Edit guardian"
                  class="flex min-h-[44px] min-w-[44px] items-center justify-center rounded-lg text-[var(--fg-subtle)] transition hover:bg-[var(--hover)] hover:text-[var(--fg)]">
                  <svg class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="1.75" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M16.862 4.487l1.687-1.688a1.875 1.875 0 112.652 2.652L10.582 16.07a4.5 4.5 0 01-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 011.13-1.897l8.932-8.931z"/>
                  </svg>
                </button>
                <button onclick={() => confirmRemoveGid = g.guardian_id} disabled={$removeMut.isPending}
                  aria-label="Remove guardian"
                  class="flex min-h-[44px] min-w-[44px] items-center justify-center rounded-lg text-[var(--fg-subtle)] transition hover:bg-red-50 hover:text-red-500 dark:hover:bg-red-950/30 disabled:opacity-40">
                  <svg class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="1.75" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M14.74 9l-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 01-2.244 2.077H8.084a2.25 2.25 0 01-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 00-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 013.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 00-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 00-7.5 0"/>
                  </svg>
                </button>
              {/if}
            </div>
          </div>

          <!-- Inline edit form -->
          {#if editingId === g.guardian_id && student.can_edit}
            <div class="border-t border-[var(--border)] px-4 pb-4 pt-3">
              <GuardianForm
                idPrefix="et-{g.guardian_id}" submitLabel="Save changes"
                initial={{
                  first_name: g.first_name, last_name: g.last_name, phone: g.phone,
                  email: g.email ?? '', occupation: g.occupation ?? '', address: g.address ?? '',
                  relation_type: g.relation_type, is_primary: g.is_primary,
                }}
                pending={$updateMut.isPending} serverError={editError}
                onSubmit={(d) => { editError = ''; $updateMut.mutate({ gid: g.guardian_id, data: d }); }}
                onCancel={cancelEdit}
              />
            </div>
          {/if}

        </div>
      {/each}
    </div>
  {/if}

  {#if student.can_manage}
    <PortalAccessCard {student} {studentId} />
  {/if}
</div>

<ConfirmModal
  open={!!confirmRemoveGid}
  title="Remove guardian?"
  message="This guardian will be unlinked from the student. Their contact details are not deleted from the system."
  confirmLabel="Remove"
  isPending={$removeMut.isPending}
  onConfirm={() => { $removeMut.mutate({ gid: confirmRemoveGid! }); confirmRemoveGid = null; }}
  onCancel={() => confirmRemoveGid = null}
/>
