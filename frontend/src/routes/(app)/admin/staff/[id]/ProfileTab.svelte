<script lang="ts">
  import { createMutation, createQuery, useQueryClient } from '@tanstack/svelte-query';
  import { updateStaff, listPositions, addEmergencyContact, deleteEmergencyContact, type StaffCategory, type StaffDetail } from '$lib/api/staff';

  interface Props { staff: StaffDetail; staffId: string; }
  const { staff, staffId }: Props = $props();

  const qc = useQueryClient();
  const invalidate = () => qc.invalidateQueries({ queryKey: ['staff', staffId] });

  const positionsQuery = createQuery({
    queryKey: ['positions'],
    queryFn: listPositions,
    staleTime: 10 * 60_000,
  });

  // ── Profile edit ────────────────────────────────────────────────────────────
  let editing  = $state(false);
  let editForm = $state({
    first_name: '', last_name: '', middle_name: '', phone: '', email: '',
    position_ids: [] as string[],
    gender: '' as '' | 'MALE' | 'FEMALE',
    staff_category: '' as '' | StaffCategory,
    employment_type: '' as '' | 'PERMANENT' | 'CONTRACT' | 'NATIONAL_SERVICE' | 'INTERN',
    marital_status: '' as '' | 'SINGLE' | 'MARRIED' | 'DIVORCED' | 'WIDOWED' | 'SEPARATED',
    national_id: '', ssnit_number: '', address: '',
  });
  let editError = $state('');

  $effect(() => {
    editForm = {
      first_name:      staff.first_name,
      last_name:       staff.last_name,
      middle_name:     staff.middle_name     ?? '',
      phone:           staff.phone           ?? '',
      email:           staff.email           ?? '',
      position_ids:    [...staff.position_ids],
      gender:          staff.gender          ?? '',
      staff_category:  staff.staff_category  ?? '',
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
      position_ids:    editForm.position_ids,
      gender:          (editForm.gender         || undefined) as 'MALE' | 'FEMALE' | undefined,
      staff_category:  (editForm.staff_category || undefined) as StaffCategory | undefined,
      employment_type: (editForm.employment_type || undefined) as 'PERMANENT' | 'CONTRACT' | 'NATIONAL_SERVICE' | 'INTERN' | undefined,
      marital_status:  (editForm.marital_status || undefined) as 'SINGLE' | 'MARRIED' | 'DIVORCED' | 'WIDOWED' | 'SEPARATED' | undefined,
      national_id:     editForm.national_id     || undefined,
      ssnit_number:    editForm.ssnit_number    || undefined,
      address:         editForm.address         || undefined,
    }),
    onSuccess: () => { invalidate(); editing = false; editError = ''; },
    onError: (e: unknown) => {
      editError = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? 'Failed to save.';
    },
  });

  // ── Emergency contacts ──────────────────────────────────────────────────────
  let showContactForm = $state(false);
  let cForm = $state({ name: '', contact_type: '', phone: '', email: '' });
  let cError = $state('');

  const addContactMut = createMutation({
    mutationFn: () => addEmergencyContact(staffId, { name: cForm.name, contact_type: cForm.contact_type, phone: cForm.phone, email: cForm.email || undefined }),
    onSuccess: () => { invalidate(); showContactForm = false; cForm = { name: '', contact_type: '', phone: '', email: '' }; cError = ''; },
    onError: (e: unknown) => { cError = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? 'Failed.'; },
  });

  const delContactMut = createMutation({
    mutationFn: (contactId: string) => deleteEmergencyContact(staffId, contactId),
    onSuccess: () => invalidate(),
  });

  function fmtDate(d: string | null) {
    if (!d) return '—';
    return new Date(d).toLocaleDateString('en-GH', { day: 'numeric', month: 'short', year: 'numeric' });
  }

  const CATEGORY_LABEL: Record<string, string> = { TEACHING: 'Teaching', NON_TEACHING: 'Non-Teaching' };
  const EMPLOYMENT_LABEL: Record<string, string> = { PERMANENT: 'Permanent', CONTRACT: 'Contract', NATIONAL_SERVICE: 'National Service', INTERN: 'Intern' };
  const MARITAL_LABEL: Record<string, string> = { SINGLE: 'Single', MARRIED: 'Married', DIVORCED: 'Divorced', WIDOWED: 'Widowed', SEPARATED: 'Separated' };

  const DETAILS = $derived(() => [
    ['Full name',       staff.display_name],
    ['Staff number',    staff.staff_number],
    ['Category',        staff.staff_category ? CATEGORY_LABEL[staff.staff_category] : '—'],
    ['Employment type', staff.employment_type ? EMPLOYMENT_LABEL[staff.employment_type] : '—'],
    ['Gender',          staff.gender ? staff.gender.charAt(0) + staff.gender.slice(1).toLowerCase() : '—'],
    ['Marital status',  staff.marital_status ? MARITAL_LABEL[staff.marital_status] : '—'],
    ['Date of birth',   fmtDate(staff.date_of_birth)],
    ['Ghana Card',      staff.national_id   ?? '—'],
    ['SSNIT No.',       staff.ssnit_number  ?? '—'],
    ['Address',         staff.address       ?? '—'],
    ['Position(s)',     staff.position_names.length ? staff.position_names.join(', ') : '—'],
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
        <!-- Category toggle -->
        <div class="sm:col-span-2">
          <p class="mb-2 text-xs font-medium text-[var(--fg-muted)]">Staff category</p>
          <div class="flex gap-2">
            {#each [['TEACHING', 'Teaching'], ['NON_TEACHING', 'Non-Teaching']] as [val, label]}
              <button type="button"
                onclick={() => editForm.staff_category = val as StaffCategory}
                class="rounded-xl border px-4 py-2 text-sm font-medium transition
                       {editForm.staff_category === val
                         ? 'border-[var(--brand)] text-[var(--brand)] bg-[var(--hover)]'
                         : 'border-[var(--border)] text-[var(--fg-muted)] hover:bg-[var(--hover)]'}">
                {label}
              </button>
            {/each}
          </div>
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
        <div class="sm:col-span-2">
          <label class="mb-1 block text-xs font-medium text-[var(--fg-muted)]">Positions</label>
          <div class="flex flex-wrap gap-2">
            {#each ($positionsQuery.data ?? []).filter(p => !['Teacher', 'House Master / Mistress', 'Class Teacher'].includes(p.name)) as p (p.id)}
              <label class="flex cursor-pointer items-center gap-2 rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--fg)] hover:bg-[var(--hover)]
                            {editForm.position_ids.includes(p.id) ? 'border-[var(--brand)]' : ''}">
                <input type="checkbox" class="accent-[var(--brand)]"
                  checked={editForm.position_ids.includes(p.id)}
                  onchange={() => {
                    if (editForm.position_ids.includes(p.id))
                      editForm.position_ids = editForm.position_ids.filter(id => id !== p.id);
                    else
                      editForm.position_ids = [...editForm.position_ids, p.id];
                  }} />
                {p.name}
              </label>
            {/each}
          </div>
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
        {#each DETAILS() as [label, value]}
          <div>
            <dt class="text-[10px] font-semibold uppercase tracking-widest text-[var(--fg-muted)]">{label}</dt>
            <dd class="mt-0.5 text-sm text-[var(--fg)]">{value}</dd>
          </div>
        {/each}
      </dl>
    {/if}
  </div>

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
      <p class="text-sm text-[var(--fg-muted)]">No emergency contacts on file.</p>
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
