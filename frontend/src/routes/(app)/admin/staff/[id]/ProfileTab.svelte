<script lang="ts">
  import { createMutation, createQuery, useQueryClient } from '@tanstack/svelte-query';
  import { updateStaff, listCategories, addEmergencyContact, deleteEmergencyContact, type StaffDetail } from '$lib/api/staff';
  import { apiError } from '$lib/utils';
  import PositionsCard from './PositionsCard.svelte';

  interface Props { staff: StaffDetail; staffId: string; }
  const { staff, staffId }: Props = $props();

  const qc = useQueryClient();
  const invalidate = () => qc.invalidateQueries({ queryKey: ['staff', staffId] });

  const categoriesQuery = createQuery({
    queryKey: ['staff-categories'],
    queryFn: listCategories,
    staleTime: 10 * 60_000,
  });

  // ── Profile edit ────────────────────────────────────────────────────────────
  let editing  = $state(false);
  let editForm = $state({
    first_name: '', last_name: '', middle_name: '', phone: '', email: '',
    category_id: '' as string,
    date_of_birth: '',
    joined_date: '',
    gender: '' as '' | 'MALE' | 'FEMALE',
    employment_type: '' as '' | 'PERMANENT' | 'CONTRACT' | 'NATIONAL_SERVICE' | 'INTERN',
    marital_status: '' as '' | 'SINGLE' | 'MARRIED' | 'DIVORCED' | 'WIDOWED' | 'SEPARATED',
    national_id: '', ssnit_number: '', address: '',
  });
  let editError = $state('');

  $effect(() => {
    if (editing) return;
    editForm = {
      first_name:      staff.first_name,
      last_name:       staff.last_name,
      middle_name:     staff.middle_name     ?? '',
      phone:           staff.phone           ?? '',
      email:           staff.email           ?? '',
      category_id:     staff.category_id     ?? '',
      date_of_birth:   staff.date_of_birth   ?? '',
      joined_date:     staff.joined_date     ?? '',
      gender:          staff.gender          ?? '',
      employment_type: staff.employment_type ?? '',
      marital_status:  staff.marital_status  ?? '',
      national_id:     staff.national_id     ?? '',
      ssnit_number:    staff.ssnit_number    ?? '',
      address:         staff.address         ?? '',
    };
  });

  const editMut = createMutation({
    mutationFn: () => updateStaff(staffId, {
      first_name:      editForm.first_name      || undefined,
      last_name:       editForm.last_name       || undefined,
      middle_name:     editForm.middle_name     || undefined,
      phone:           editForm.phone           || undefined,
      email:           editForm.email           || undefined,
      category_id:     editForm.category_id     || undefined,
      date_of_birth:   editForm.date_of_birth   || undefined,
      joined_date:     editForm.joined_date     || undefined,
      gender:          (editForm.gender         || undefined) as 'MALE' | 'FEMALE' | undefined,
      employment_type: (editForm.employment_type || undefined) as 'PERMANENT' | 'CONTRACT' | 'NATIONAL_SERVICE' | 'INTERN' | undefined,
      marital_status:  (editForm.marital_status || undefined) as 'SINGLE' | 'MARRIED' | 'DIVORCED' | 'WIDOWED' | 'SEPARATED' | undefined,
      national_id:     editForm.national_id     || undefined,
      ssnit_number:    editForm.ssnit_number    || undefined,
      address:         editForm.address         || undefined,
    }),
    onSuccess: () => { invalidate(); editing = false; editError = ''; },
    onError: (e) => { editError = apiError(e, 'Failed to save.'); },
  });

  // ── Emergency contacts ──────────────────────────────────────────────────────
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
    onSuccess: () => invalidate(),
  });

  function fmtDate(d: string | null) {
    if (!d) return '—';
    return new Date(d).toLocaleDateString('en-GH', { day: 'numeric', month: 'short', year: 'numeric' });
  }

  const EMPLOYMENT_LABEL: Record<string, string> = { PERMANENT: 'Permanent', CONTRACT: 'Contract', NATIONAL_SERVICE: 'National Service', INTERN: 'Intern' };
  const MARITAL_LABEL: Record<string, string> = { SINGLE: 'Single', MARRIED: 'Married', DIVORCED: 'Divorced', WIDOWED: 'Widowed', SEPARATED: 'Separated' };

  const DETAILS = $derived([
    ['Full name',       staff.display_name],
    ['Staff number',    staff.staff_number],
    ['Category',        staff.category_name ?? '—'],
    ['Employment type', staff.employment_type ? EMPLOYMENT_LABEL[staff.employment_type] : '—'],
    ['Gender',          staff.gender ? staff.gender.charAt(0) + staff.gender.slice(1).toLowerCase() : '—'],
    ['Marital status',  staff.marital_status ? MARITAL_LABEL[staff.marital_status] : '—'],
    ['Date of birth',   fmtDate(staff.date_of_birth)],
    ['Ghana Card',      staff.national_id   ?? '—'],
    ['SSNIT No.',       staff.ssnit_number  ?? '—'],
    ['Address',         staff.address       ?? '—'],
    ['Date joined',     fmtDate(staff.joined_date)],
  ] as [string, string][]);
</script>

<div class="space-y-5">
  <!-- Personal details -->
  <div class="rounded-xl border border-[var(--border)] bg-[var(--card)] p-5">
    <div class="mb-4 flex items-center justify-between">
      <h2 class="text-xs font-semibold uppercase tracking-widest text-[var(--fg-muted)]">Personal details</h2>
      {#if !editing}
        <button onclick={() => editing = true}
          class="text-xs font-semibold transition hover:underline" style="color: var(--brand)">Edit</button>
      {/if}
    </div>

    {#if editing}
      <div class="grid gap-4 sm:grid-cols-2">
        {#each [
          { label: 'First name',  key: 'first_name'  },
          { label: 'Last name',   key: 'last_name'   },
          { label: 'Middle name', key: 'middle_name' },
          { label: 'Phone',       key: 'phone'       },
          { label: 'Email',       key: 'email'       },
        ] as f}
          <div>
            <label class="mb-1 block text-xs font-medium text-[var(--fg-muted)]">{f.label}</label>
            <input bind:value={editForm[f.key as keyof typeof editForm] as string}
              class="w-full rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--fg)] focus:border-[var(--brand)] focus:outline-none" />
          </div>
        {/each}

        <!-- Category -->
        <div class="sm:col-span-2">
          <label class="mb-1 block text-xs font-medium text-[var(--fg-muted)]">Category</label>
          <select bind:value={editForm.category_id}
            class="w-full rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--fg)] focus:border-[var(--brand)] focus:outline-none">
            <option value="">Not specified</option>
            {#each $categoriesQuery.data ?? [] as cat (cat.id)}
              <option value={cat.id}>{cat.name}</option>
            {/each}
          </select>
        </div>

        <div>
          <label class="mb-1 block text-xs font-medium text-[var(--fg-muted)]">Employment type</label>
          <select bind:value={editForm.employment_type}
            class="w-full rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--fg)] focus:border-[var(--brand)] focus:outline-none">
            <option value="">Select…</option>
            <option value="PERMANENT">Permanent</option>
            <option value="CONTRACT">Contract</option>
            <option value="NATIONAL_SERVICE">National Service</option>
            <option value="INTERN">Intern</option>
          </select>
        </div>
        <div>
          <label class="mb-1 block text-xs font-medium text-[var(--fg-muted)]">Marital status</label>
          <select bind:value={editForm.marital_status}
            class="w-full rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--fg)] focus:border-[var(--brand)] focus:outline-none">
            <option value="">Select…</option>
            <option value="SINGLE">Single</option>
            <option value="MARRIED">Married</option>
            <option value="DIVORCED">Divorced</option>
            <option value="WIDOWED">Widowed</option>
            <option value="SEPARATED">Separated</option>
          </select>
        </div>
        {#each [
          { label: 'Ghana Card Number', key: 'national_id',  placeholder: 'GHA-XXXXXXXXX-X' },
          { label: 'SSNIT Number',      key: 'ssnit_number', placeholder: 'C000000000000' },
        ] as f}
          <div>
            <label class="mb-1 block text-xs font-medium text-[var(--fg-muted)]">{f.label}</label>
            <input bind:value={editForm[f.key as keyof typeof editForm] as string} placeholder={f.placeholder}
              class="w-full rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--fg)] placeholder:text-[var(--fg-muted)] focus:border-[var(--brand)] focus:outline-none" />
          </div>
        {/each}
        <div class="sm:col-span-2">
          <label class="mb-1 block text-xs font-medium text-[var(--fg-muted)]">Home address</label>
          <textarea bind:value={editForm.address} rows="2" placeholder="Street, Town, Region"
            class="w-full rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--fg)] placeholder:text-[var(--fg-muted)] focus:border-[var(--brand)] focus:outline-none resize-none"></textarea>
        </div>

        <div>
          <label class="mb-1 block text-xs font-medium text-[var(--fg-muted)]">Gender</label>
          <select bind:value={editForm.gender}
            class="w-full rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--fg)] focus:border-[var(--brand)] focus:outline-none">
            <option value="">Not specified</option>
            <option value="MALE">Male</option>
            <option value="FEMALE">Female</option>
          </select>
        </div>
        <div>
          <label class="mb-1 block text-xs font-medium text-[var(--fg-muted)]">Date of birth</label>
          <input type="date" bind:value={editForm.date_of_birth}
            class="w-full rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--fg)] focus:border-[var(--brand)] focus:outline-none" />
        </div>
        <div>
          <label class="mb-1 block text-xs font-medium text-[var(--fg-muted)]">Date joined</label>
          <input type="date" bind:value={editForm.joined_date}
            class="w-full rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--fg)] focus:border-[var(--brand)] focus:outline-none" />
        </div>
      </div>
      {#if editError}<p class="mt-2 text-xs text-red-500">{editError}</p>{/if}
      <div class="mt-4 flex gap-2">
        <button onclick={() => $editMut.mutate()} disabled={$editMut.isPending}
          class="rounded-xl px-4 py-2 text-sm font-semibold text-white transition hover:opacity-90 disabled:opacity-50"
          style="background-color: var(--brand)">
          {$editMut.isPending ? 'Saving…' : 'Save changes'}
        </button>
        <button onclick={() => { editing = false; editError = ''; }}
          class="rounded-xl border border-[var(--border)] px-4 py-2 text-sm font-medium text-[var(--fg-muted)] transition hover:bg-[var(--bg)]">
          Cancel
        </button>
      </div>
    {:else}
      <dl class="grid gap-x-8 gap-y-3 sm:grid-cols-2">
        {#each DETAILS as [label, value]}
          <div>
            <dt class="text-[11px] font-semibold uppercase tracking-widest text-[var(--fg-muted)]">{label}</dt>
            <dd class="mt-0.5 text-sm text-[var(--fg)]">{value}</dd>
          </div>
        {/each}
      </dl>
    {/if}
  </div>

  <!-- Authority positions -->
  <PositionsCard {staff} {staffId} />

  <!-- Emergency contacts -->
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
              class="w-full rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--fg)] placeholder:text-[var(--fg-muted)] focus:border-[var(--brand)] focus:outline-none" />
          </div>
        {/each}
      </div>
      {#if cError}<p class="text-xs text-red-500">{cError}</p>{/if}
      <div class="flex gap-2">
        <button onclick={() => $addContactMut.mutate()} disabled={$addContactMut.isPending}
          class="rounded-xl px-4 py-1.5 text-xs font-semibold text-white transition hover:opacity-90 disabled:opacity-50"
          style="background-color: var(--brand)">
          {$addContactMut.isPending ? 'Saving…' : 'Save'}
        </button>
        <button onclick={() => { showContactForm = false; cError = ''; }}
          class="rounded-xl border border-[var(--border)] px-4 py-1.5 text-xs font-medium text-[var(--fg-muted)] transition hover:bg-[var(--bg)]">
          Cancel
        </button>
      </div>
    {/if}

    {#if staff.emergency_contacts.length === 0 && !showContactForm}
      <div class="rounded-lg border border-dashed border-[var(--border)] py-5 text-center">
        <p class="text-sm text-[var(--fg-muted)]">No emergency contacts on file.</p>
      </div>
    {:else}
      <div class="mt-3 space-y-2">
        {#each staff.emergency_contacts as c (c.id)}
          <div class="flex items-center justify-between rounded-xl border border-[var(--border)] bg-[var(--bg)] px-4 py-3">
            <div>
              <p class="text-sm font-medium text-[var(--fg)]">{c.name} <span class="text-xs text-[var(--fg-muted)]">({c.contact_type})</span></p>
              <p class="text-xs text-[var(--fg-muted)]">{c.phone}{c.email ? ' · ' + c.email : ''}</p>
            </div>
            <button onclick={() => $delContactMut.mutate(c.id)}
              class="text-xs text-[var(--fg-muted)] transition hover:text-red-500">Remove</button>
          </div>
        {/each}
      </div>
    {/if}
  </div>
</div>
