<script lang="ts">
  import { createMutation, useQueryClient } from '@tanstack/svelte-query';
  import { addEmergencyContact, deleteEmergencyContact, type EmergencyContact } from '$lib/api/staff';
  import { apiError } from '$lib/utils';
  import ConfirmModal from '$lib/components/ConfirmModal.svelte';

  interface Props { staffId: string; contacts: EmergencyContact[]; }
  const { staffId, contacts }: Props = $props();

  const qc = useQueryClient();
  const invalidate = () => qc.invalidateQueries({ queryKey: ['staff', staffId] });

  let showContactForm = $state(false);
  let cForm = $state({ name: '', contact_type: '', phone: '', email: '' });
  let cError = $state('');

  const addContactMut = createMutation({
    mutationFn: () => addEmergencyContact(staffId, { name: cForm.name, contact_type: cForm.contact_type, phone: cForm.phone, email: cForm.email || undefined }),
    onSuccess: () => { invalidate(); showContactForm = false; cForm = { name: '', contact_type: '', phone: '', email: '' }; cError = ''; },
    onError: (e) => { cError = apiError(e, 'Failed to save contact.'); },
  });

  const delContactMut = createMutation({
    mutationFn: (contactId: string) => deleteEmergencyContact(staffId, contactId),
    onSuccess: () => { invalidate(); confirmDelContactId = null; },
    onError: () => { confirmDelContactId = null; },
  });
  let confirmDelContactId = $state<string | null>(null);
</script>

<div class="rounded-xl border border-[var(--border)] bg-[var(--card)] p-5">
  <div class="mb-4 flex items-center justify-between">
    <h2 class="text-xs font-semibold uppercase tracking-widest text-[var(--fg-muted)]">Emergency contacts</h2>
    {#if !showContactForm}
      <button onclick={() => showContactForm = true}
        class="text-xs font-semibold transition hover:underline" style="color: var(--brand)">+ Add</button>
    {/if}
  </div>

  {#if showContactForm}
    <div class="mb-4 grid gap-3 sm:grid-cols-2">
      {#each [
        { label: 'Name', key: 'name', placeholder: '' },
        { label: 'Relationship', key: 'contact_type', placeholder: 'e.g. Spouse, Parent' },
        { label: 'Phone', key: 'phone', placeholder: '' },
        { label: 'Email (optional)', key: 'email', placeholder: '' },
      ] as f}
        <div>
          <label class="mb-1 block text-xs font-medium text-[var(--fg-muted)]">{f.label}</label>
          <input bind:value={cForm[f.key as keyof typeof cForm]} placeholder={f.placeholder}
            class="w-full min-h-[44px] rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--fg)] placeholder:text-[var(--fg-muted)] focus:border-[var(--brand)] focus:outline-none" />
        </div>
      {/each}
    </div>
    {#if cError}<p class="text-xs text-red-500">{cError}</p>{/if}
    <div class="flex gap-2">
      <button onclick={() => $addContactMut.mutate()} disabled={$addContactMut.isPending}
        class="min-h-[44px] rounded-xl px-4 text-xs font-semibold text-white transition hover:opacity-90 disabled:opacity-50"
        style="background-color: var(--brand)">
        {$addContactMut.isPending ? 'Saving…' : 'Save'}
      </button>
      <button onclick={() => { showContactForm = false; cError = ''; }}
        class="min-h-[44px] rounded-xl border border-[var(--border)] px-4 text-xs font-medium text-[var(--fg-muted)] transition hover:bg-[var(--bg)]">
        Cancel
      </button>
    </div>
  {/if}

  {#if contacts.length === 0 && !showContactForm}
    <div class="rounded-lg border border-dashed border-[var(--border)] py-5 text-center">
      <p class="text-sm text-[var(--fg-muted)]">No emergency contacts on file.</p>
    </div>
  {:else}
    <div class="mt-3 space-y-2">
      {#each contacts as c (c.id)}
        <div class="flex items-center justify-between rounded-xl border border-[var(--border)] bg-[var(--bg)] px-4 py-3">
          <div>
            <p class="text-sm font-medium text-[var(--fg)]">{c.name} <span class="text-xs text-[var(--fg-muted)]">({c.contact_type})</span></p>
            <p class="text-xs text-[var(--fg-muted)]">{c.phone}{c.email ? ' · ' + c.email : ''}</p>
          </div>
          <button onclick={() => confirmDelContactId = c.id}
            class="flex min-h-[44px] items-center text-xs text-[var(--fg-muted)] transition hover:text-red-500">Remove</button>
        </div>
      {/each}
    </div>
  {/if}
</div>

<ConfirmModal
  open={!!confirmDelContactId}
  title="Remove emergency contact?"
  message="This contact will be permanently removed from the staff member's record."
  confirmLabel="Remove"
  isPending={$delContactMut.isPending}
  onConfirm={() => $delContactMut.mutate(confirmDelContactId!)}
  onCancel={() => confirmDelContactId = null}
/>
