<script lang="ts">
  // Shared by GuardiansTab.svelte's "add guardian" panel and its per-row
  // inline edit — both used to be separate ~35-line copies of the same
  // field set with duplicated required-field validation.
  export interface GuardianFormData {
    first_name: string; last_name: string; phone: string; email: string;
    occupation: string; address: string; relation_type: string; is_primary: boolean;
  }

  const RELATIONS = ['Parent', 'Mother', 'Father', 'Guardian', 'Sibling', 'Uncle', 'Aunt', 'Grandparent', 'Other'];

  interface Props {
    idPrefix: string;
    initial: GuardianFormData;
    submitLabel: string;
    pending: boolean;
    serverError: string;
    onSubmit: (data: GuardianFormData) => void;
    onCancel: () => void;
  }
  const { idPrefix, initial, submitLabel, pending, serverError, onSubmit, onCancel }: Props = $props();

  let form = $state<GuardianFormData>({ ...initial });
  let localError = $state('');
  const error = $derived(localError || serverError);

  function submit() {
    localError = '';
    if (!form.first_name.trim()) { localError = 'First name is required.'; return; }
    if (!form.last_name.trim())  { localError = 'Last name is required.'; return; }
    if (!form.phone.trim())      { localError = 'Phone number is required.'; return; }
    onSubmit({
      first_name: form.first_name.trim(),
      last_name:  form.last_name.trim(),
      phone:      form.phone.trim(),
      email:      form.email.trim(),
      occupation: form.occupation.trim(),
      address:    form.address.trim(),
      relation_type: form.relation_type,
      is_primary: form.is_primary,
    });
  }
</script>

<div class="grid gap-3 sm:grid-cols-2">
  <div><label for="{idPrefix}-first" class="label">First name <span class="text-red-500">*</span></label><input id="{idPrefix}-first" bind:value={form.first_name} placeholder="Kofi" class="input" /></div>
  <div><label for="{idPrefix}-last" class="label">Last name <span class="text-red-500">*</span></label><input id="{idPrefix}-last" bind:value={form.last_name} placeholder="Mensah" class="input" /></div>
  <div><label for="{idPrefix}-phone" class="label">Phone <span class="text-red-500">*</span></label><input id="{idPrefix}-phone" bind:value={form.phone} placeholder="024XXXXXXX" class="input" /></div>
  <div><label for="{idPrefix}-email" class="label">Email</label><input id="{idPrefix}-email" type="email" bind:value={form.email} placeholder="Optional" class="input" /></div>
  <div>
    <label for="{idPrefix}-relation" class="label">Relation</label>
    <select id="{idPrefix}-relation" bind:value={form.relation_type} class="input">
      {#each RELATIONS as r}<option value={r}>{r}</option>{/each}
    </select>
  </div>
  <div><label for="{idPrefix}-occ" class="label">Occupation</label><input id="{idPrefix}-occ" bind:value={form.occupation} placeholder="Optional" class="input" /></div>
  <div class="sm:col-span-2"><label for="{idPrefix}-addr" class="label">Address</label><input id="{idPrefix}-addr" bind:value={form.address} placeholder="Optional" class="input" /></div>
  <div class="sm:col-span-2 flex items-center gap-2">
    <input type="checkbox" id="{idPrefix}-primary" bind:checked={form.is_primary} class="accent-[var(--brand)]" />
    <label for="{idPrefix}-primary" class="text-sm text-[var(--fg)]">Primary contact (receives SMS notifications)</label>
  </div>
</div>
{#if error}<p class="mt-2 text-xs text-red-500">{error}</p>{/if}
<div class="mt-3 flex gap-2">
  <button onclick={submit} disabled={pending}
    class="rounded-xl px-4 py-2 text-sm font-semibold text-white disabled:opacity-50 transition hover:opacity-90" style="background: var(--brand)">
    {pending ? 'Saving…' : submitLabel}
  </button>
  <button onclick={onCancel}
    class="rounded-xl border border-[var(--border)] px-4 py-2 text-sm text-[var(--fg-muted)] hover:bg-[var(--hover)] transition">
    Cancel
  </button>
</div>

<style>
  @reference "tailwindcss";
  .label { @apply block text-xs font-medium text-[var(--fg-muted)] mb-1; }
  .input  { @apply w-full rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--fg)] placeholder:text-[var(--fg-subtle)] focus:border-[var(--brand)] focus:outline-none transition; }
</style>
