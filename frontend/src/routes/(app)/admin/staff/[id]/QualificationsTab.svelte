<script lang="ts">
  import { createMutation, useQueryClient } from '@tanstack/svelte-query';
  import { addQualification, updateQualification, deleteQualification, type StaffDetail } from '$lib/api/staff';
  import EmptyState from '$lib/components/EmptyState.svelte';
  import ConfirmModal from '$lib/components/ConfirmModal.svelte';

  interface Props { staff: StaffDetail; staffId: string; }
  const { staff, staffId }: Props = $props();

  const qc = useQueryClient();
  const invalidate = () => qc.invalidateQueries({ queryKey: ['staff', staffId] });

  let showForm     = $state(false);
  let editingId    = $state<string | null>(null);
  let confirmDelId = $state<string | null>(null);
  let form = $state({ institution: '', qualification_type: '', field_of_study: '', year_obtained: '' });
  let formError = $state('');

  function resetForm() {
    form = { institution: '', qualification_type: '', field_of_study: '', year_obtained: '' };
    formError = '';
  }

  function startEdit(q: { id: string; institution: string; qualification_type: string; field_of_study: string | null; year_obtained: number | null }) {
    editingId = q.id;
    showForm  = false;
    form = {
      institution:        q.institution,
      qualification_type: q.qualification_type,
      field_of_study:     q.field_of_study ?? '',
      year_obtained:      q.year_obtained != null ? String(q.year_obtained) : '',
    };
    formError = '';
  }

  const addMut = createMutation({
    mutationFn: () => addQualification(staffId, {
      institution:        form.institution,
      qualification_type: form.qualification_type,
      field_of_study:     form.field_of_study   || undefined,
      year_obtained:      form.year_obtained ? Number(form.year_obtained) : undefined,
    }),
    onSuccess: () => { invalidate(); showForm = false; resetForm(); },
    onError: (e: unknown) => {
      formError = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? 'Failed.';
    },
  });

  const editMut = createMutation({
    mutationFn: (qualId: string) => updateQualification(staffId, qualId, {
      institution:        form.institution        || undefined,
      qualification_type: form.qualification_type || undefined,
      field_of_study:     form.field_of_study     || undefined,
      year_obtained:      form.year_obtained ? Number(form.year_obtained) : undefined,
    }),
    onSuccess: () => { invalidate(); editingId = null; resetForm(); },
    onError: (e: unknown) => {
      formError = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? 'Failed.';
    },
  });

  const delMut = createMutation({
    mutationFn: (qualId: string) => deleteQualification(staffId, qualId),
    onSuccess: () => { invalidate(); confirmDelId = null; },
  });

  const FIELDS = [
    { label: 'Institution *',  key: 'institution',        placeholder: 'e.g. University of Ghana'    },
    { label: 'Qualification *',key: 'qualification_type', placeholder: 'e.g. BSc, PGCE, PhD'         },
    { label: 'Field of study', key: 'field_of_study',     placeholder: 'e.g. Mathematics Education'  },
    { label: 'Year obtained',  key: 'year_obtained',      placeholder: 'e.g. 2018'                   },
  ] as const;
</script>

<div class="space-y-4">
  <div class="flex justify-end">
    <button onclick={() => { showForm = !showForm; editingId = null; resetForm(); }}
      class="flex items-center gap-2 rounded-xl px-4 py-2 text-sm font-semibold text-white transition hover:opacity-90"
      style="background-color: var(--brand)">
      <svg class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" d="M12 4v16m8-8H4"/>
      </svg>
      Add qualification
    </button>
  </div>

  {#if showForm}
    <div class="rounded-xl border border-[var(--border)] bg-[var(--card)] p-5">
      <div class="grid gap-4 sm:grid-cols-2">
        {#each FIELDS as f}
          <div>
            <label class="mb-1 block text-xs font-medium text-[var(--fg-muted)]">{f.label}</label>
            <input bind:value={form[f.key]} placeholder={f.placeholder}
              type={f.key === 'year_obtained' ? 'number' : 'text'}
              class="w-full rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--fg)] placeholder:text-[var(--fg-muted)] focus:border-[var(--brand)] focus:outline-none" />
          </div>
        {/each}
      </div>
      {#if formError}<p class="mt-2 text-xs text-red-500">{formError}</p>{/if}
      <div class="mt-4 flex gap-2">
        <button onclick={() => $addMut.mutate()} disabled={$addMut.isPending}
          class="rounded-xl px-4 py-2 text-sm font-semibold text-white transition hover:opacity-90 disabled:opacity-50"
          style="background-color: var(--brand)">
          {$addMut.isPending ? 'Saving…' : 'Add qualification'}
        </button>
        <button onclick={() => { showForm = false; resetForm(); }}
          class="rounded-xl border border-[var(--border)] px-4 py-2 text-sm font-medium text-[var(--fg-muted)] transition hover:bg-[var(--bg)]">
          Cancel
        </button>
      </div>
    </div>
  {/if}

  {#if staff.qualifications.length === 0}
    <EmptyState
      iconPath="M4.26 10.147a60.436 60.436 0 00-.491 6.347A48.627 48.627 0 0112 20.904a48.627 48.627 0 018.232-4.41 60.46 60.46 0 00-.491-6.347m-15.482 0a50.57 50.57 0 00-2.658-.813A59.905 59.905 0 0112 3.493a59.902 59.902 0 0110.399 5.84c-.896.248-1.783.52-2.658.814m-15.482 0A50.697 50.697 0 0112 13.489a50.702 50.702 0 017.74-3.342M6.75 15a.75.75 0 100-1.5.75.75 0 000 1.5zm0 0v-3.675A55.378 55.378 0 0112 8.443m-7.007 11.55A5.981 5.981 0 006.75 15.75v-1.5"
      title="No qualifications recorded yet."
      description="Add academic and professional qualifications for this staff member."
      action={() => showForm = true}
      actionLabel="Add qualification"
    />
  {:else}
    <div class="overflow-hidden rounded-xl border border-[var(--border)] bg-[var(--card)]">
      {#each staff.qualifications as q, i (q.id)}
        <div class="px-5 py-4 {i > 0 ? 'border-t border-[var(--border)]' : ''}">
          {#if editingId === q.id}
            <div class="grid gap-4 sm:grid-cols-2">
              {#each FIELDS as f}
                <div>
                  <label class="mb-1 block text-xs font-medium text-[var(--fg-muted)]">{f.label}</label>
                  <input bind:value={form[f.key]} placeholder={f.placeholder}
                    type={f.key === 'year_obtained' ? 'number' : 'text'}
                    class="w-full rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--fg)] placeholder:text-[var(--fg-muted)] focus:border-[var(--brand)] focus:outline-none" />
                </div>
              {/each}
            </div>
            {#if formError}<p class="mt-2 text-xs text-red-500">{formError}</p>{/if}
            <div class="mt-3 flex gap-2">
              <button onclick={() => $editMut.mutate(q.id)} disabled={$editMut.isPending}
                class="rounded-xl px-4 py-2 text-sm font-semibold text-white transition hover:opacity-90 disabled:opacity-50"
                style="background-color: var(--brand)">
                {$editMut.isPending ? 'Saving…' : 'Save changes'}
              </button>
              <button onclick={() => { editingId = null; resetForm(); }}
                class="rounded-xl border border-[var(--border)] px-4 py-2 text-sm font-medium text-[var(--fg-muted)] transition hover:bg-[var(--bg)]">
                Cancel
              </button>
            </div>
          {:else}
            <div class="flex items-start gap-4">
              <div class="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-[var(--brand-dim)]">
                <svg class="h-5 w-5 text-[var(--brand)]" fill="none" stroke="currentColor" stroke-width="1.75" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M4.26 10.147a60.436 60.436 0 00-.491 6.347A48.627 48.627 0 0112 20.904a48.627 48.627 0 018.232-4.41 60.46 60.46 0 00-.491-6.347m-15.482 0a50.57 50.57 0 00-2.658-.813A59.905 59.905 0 0112 3.493a59.902 59.902 0 0110.399 5.84c-.896.248-1.783.52-2.658.814m-15.482 0A50.697 50.697 0 0112 13.489a50.702 50.702 0 017.74-3.342M6.75 15a.75.75 0 100-1.5.75.75 0 000 1.5zm0 0v-3.675A55.378 55.378 0 0112 8.443m-7.007 11.55A5.981 5.981 0 006.75 15.75v-1.5"/>
                </svg>
              </div>
              <div class="min-w-0 flex-1">
                <p class="font-semibold text-[var(--fg)]">{q.qualification_type}</p>
                <p class="text-sm text-[var(--fg-muted)]">{q.institution}{q.field_of_study ? ' · ' + q.field_of_study : ''}</p>
                {#if q.year_obtained}<p class="text-xs text-[var(--fg-muted)]">{q.year_obtained}</p>{/if}
              </div>
              <div class="flex shrink-0 gap-1">
                <button onclick={() => startEdit(q)} title="Edit"
                  class="rounded-lg p-1.5 text-[var(--fg-muted)] transition hover:bg-[var(--hover)] hover:text-[var(--fg)]">
                  <svg class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="1.75" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M16.862 4.487l1.687-1.688a1.875 1.875 0 112.652 2.652L10.582 16.07a4.5 4.5 0 01-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 011.13-1.897l8.932-8.931zm0 0L19.5 7.125"/>
                  </svg>
                </button>
                <button onclick={() => confirmDelId = q.id} title="Delete"
                  class="rounded-lg p-1.5 text-[var(--fg-muted)] transition hover:bg-red-50 hover:text-red-500 dark:hover:bg-red-950/30">
                  <svg class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="1.75" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M14.74 9l-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 01-2.244 2.077H8.084a2.25 2.25 0 01-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 00-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 013.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 00-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 00-7.5 0"/>
                  </svg>
                </button>
              </div>
            </div>
          {/if}
        </div>
      {/each}
    </div>
  {/if}
</div>

<ConfirmModal
  open={!!confirmDelId}
  title="Delete qualification?"
  message="This qualification will be permanently removed. This cannot be undone."
  confirmLabel="Delete"
  isPending={$delMut.isPending}
  onConfirm={() => confirmDelId && $delMut.mutate(confirmDelId)}
  onCancel={() => confirmDelId = null}
/>
