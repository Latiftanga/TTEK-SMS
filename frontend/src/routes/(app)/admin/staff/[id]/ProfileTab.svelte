<script lang="ts">
  import { createMutation, useQueryClient } from '@tanstack/svelte-query';
  import { updateStaff, addEmergencyContact, deleteEmergencyContact, type StaffDetail } from '$lib/api/staff';

  interface Props { staff: StaffDetail; staffId: string; }
  const { staff, staffId }: Props = $props();

  const qc = useQueryClient();
  const invalidate = () => qc.invalidateQueries({ queryKey: ['staff', staffId] });

  // ── Profile edit ────────────────────────────────────────────────────────────
  let editing  = $state(false);
  let editForm = $state({ first_name: '', last_name: '', middle_name: '', phone: '', email: '', department: '', gender: '' as '' | 'MALE' | 'FEMALE' });
  let editError = $state('');

  $effect(() => {
    editForm = {
      first_name:  staff.first_name,
      last_name:   staff.last_name,
      middle_name: staff.middle_name ?? '',
      phone:       staff.phone       ?? '',
      email:       staff.email       ?? '',
      department:  staff.department  ?? '',
      gender:      staff.gender      ?? '',
    };
  });

  const editMut = createMutation({
    mutationFn: () => updateStaff(staffId, {
      first_name:  editForm.first_name  || undefined,
      last_name:   editForm.last_name   || undefined,
      middle_name: editForm.middle_name || undefined,
      phone:       editForm.phone       || undefined,
      email:       editForm.email       || undefined,
      department:  editForm.department  || undefined,
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

  const DETAILS = $derived(() => [
    ['Full name',    staff.display_name],
    ['Staff number', staff.staff_number],
    ['Gender',       staff.gender ? staff.gender.charAt(0) + staff.gender.slice(1).toLowerCase() : '—'],
    ['Date of birth',fmtDate(staff.date_of_birth)],
    ['National ID',  staff.national_id ?? '—'],
    ['Position',     staff.position_name ?? '—'],
    ['Department',   staff.department ?? '—'],
    ['Date joined',  fmtDate(staff.joined_date)],
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
          { label: 'Department',  key: 'department'  },
        ] as f}
          <div>
            <label class="mb-1 block text-xs font-medium text-[var(--fg-muted)]">{f.label}</label>
            <input bind:value={editForm[f.key as keyof typeof editForm] as string}
              class="w-full rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--fg)] focus:border-[var(--brand)] focus:outline-none" />
          </div>
        {/each}
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
