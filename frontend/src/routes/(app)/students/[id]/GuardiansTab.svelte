<script lang="ts">
  import { createMutation, useQueryClient } from '@tanstack/svelte-query';
  import { addGuardian, removeGuardian, type StudentDetail, type GuardianCreate } from '$lib/api/students';
  import { toast } from '$lib/stores/toast';

  interface Props { student: StudentDetail; studentId: string; }
  const { student, studentId }: Props = $props();

  const qc = useQueryClient();
  let showForm = $state(false);
  let formError = $state('');
  let form = $state<GuardianCreate>({
    first_name: '', last_name: '', phone: '', email: '',
    occupation: '', address: '', relation_type: 'Parent', is_primary: false,
  });

  const RELATIONS = ['Parent', 'Mother', 'Father', 'Guardian', 'Sibling', 'Uncle', 'Aunt', 'Grandparent', 'Other'];

  const addMut = createMutation({
    mutationFn: (data: GuardianCreate) => addGuardian(studentId, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['student', studentId] });
      showForm = false; formError = '';
      form = { first_name: '', last_name: '', phone: '', email: '',
               occupation: '', address: '', relation_type: 'Parent', is_primary: false };
      toast.success('Guardian added.');
    },
    onError: (e: unknown) => {
      formError = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? 'Could not add guardian.';
    },
  });

  const removeMut = createMutation({
    mutationFn: ({ gid }: { gid: string }) => removeGuardian(studentId, gid),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['student', studentId] });
      toast.success('Guardian removed.');
    },
    onError: () => toast.error('Could not remove guardian.'),
  });

  function handleAdd() {
    formError = '';
    if (!form.first_name.trim()) { formError = 'First name is required.'; return; }
    if (!form.last_name.trim())  { formError = 'Last name is required.'; return; }
    if (!form.phone.trim())      { formError = 'Phone number is required.'; return; }
    $addMut.mutate({ ...form, email: form.email?.trim() || undefined, occupation: form.occupation?.trim() || undefined });
  }
</script>

<div class="space-y-4">
  <div class="flex items-center justify-between">
    <p class="text-sm text-[var(--fg-muted)]">People responsible for this student.</p>
    <button onclick={() => { showForm = !showForm; formError = ''; }}
      class="flex items-center gap-1.5 rounded-xl px-3 py-1.5 text-xs font-semibold text-white transition hover:opacity-90" style="background: var(--brand)">
      <svg class="h-3.5 w-3.5" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" d="M12 4v16m8-8H4"/>
      </svg>
      Add guardian
    </button>
  </div>

  {#if showForm}
    <div class="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
      <h3 class="mb-3 text-sm font-semibold text-[var(--fg)]">New guardian</h3>
      <div class="grid gap-3 sm:grid-cols-2">
        <div>
          <label for="gt-first" class="label">First name <span class="text-red-500">*</span></label>
          <input id="gt-first" bind:value={form.first_name} placeholder="Kofi" class="input" />
        </div>
        <div>
          <label for="gt-last" class="label">Last name <span class="text-red-500">*</span></label>
          <input id="gt-last" bind:value={form.last_name} placeholder="Mensah" class="input" />
        </div>
        <div>
          <label for="gt-phone" class="label">Phone <span class="text-red-500">*</span></label>
          <input id="gt-phone" bind:value={form.phone} placeholder="024XXXXXXX" class="input" />
        </div>
        <div>
          <label for="gt-email" class="label">Email</label>
          <input id="gt-email" type="email" bind:value={form.email} placeholder="Optional" class="input" />
        </div>
        <div>
          <label for="gt-relation" class="label">Relation</label>
          <select id="gt-relation" bind:value={form.relation_type} class="input">
            {#each RELATIONS as r}<option value={r}>{r}</option>{/each}
          </select>
        </div>
        <div>
          <label for="gt-occupation" class="label">Occupation</label>
          <input id="gt-occupation" bind:value={form.occupation} placeholder="Optional" class="input" />
        </div>
        <div class="sm:col-span-2 flex items-center gap-2">
          <input type="checkbox" id="is_primary" bind:checked={form.is_primary} class="accent-[var(--brand)]" />
          <label for="is_primary" class="text-sm text-[var(--fg)]">Primary contact (receives SMS notifications)</label>
        </div>
      </div>
      {#if formError}<p class="mt-2 text-xs text-red-500">{formError}</p>{/if}
      <div class="mt-3 flex gap-2">
        <button onclick={handleAdd} disabled={$addMut.isPending}
          class="rounded-xl px-4 py-2 text-sm font-semibold text-white disabled:opacity-50 transition hover:opacity-90" style="background: var(--brand)">
          {$addMut.isPending ? 'Adding…' : 'Add guardian'}
        </button>
        <button onclick={() => { showForm = false; formError = ''; }}
          class="rounded-xl border border-[var(--border)] px-4 py-2 text-sm text-[var(--fg-muted)] hover:bg-[var(--hover)] transition">
          Cancel
        </button>
      </div>
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
        <div class="flex items-center gap-4 rounded-xl border border-[var(--border)] bg-[var(--card)] px-4 py-3">
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
            <p class="text-xs text-[var(--fg-muted)]">{g.phone}{g.email ? ` · ${g.email}` : ''}{g.occupation ? ` · ${g.occupation}` : ''}</p>
          </div>
          <button onclick={() => $removeMut.mutate({ gid: g.guardian_id })} disabled={$removeMut.isPending}
            class="shrink-0 rounded-lg p-1.5 text-[var(--fg-subtle)] transition hover:bg-red-50 hover:text-red-500 dark:hover:bg-red-950/30 disabled:opacity-40" title="Remove">
            <svg class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="1.75" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" d="M14.74 9l-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 01-2.244 2.077H8.084a2.25 2.25 0 01-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 00-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 013.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 00-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 00-7.5 0"/>
            </svg>
          </button>
        </div>
      {/each}
    </div>
  {/if}
</div>

<style>
  @reference "tailwindcss";
  .label { @apply block text-xs font-medium text-[var(--fg-muted)] mb-1; }
  .input  { @apply w-full rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--fg)] placeholder:text-[var(--fg-subtle)] focus:border-[var(--brand)] focus:outline-none transition; }
</style>
