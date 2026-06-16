<script lang="ts">
  import { createMutation, createQuery, useQueryClient } from '@tanstack/svelte-query';
  import { createStaff, listPositions, type StaffCategory, type StaffDetail } from '$lib/api/staff';

  interface Props { onSuccess: (staff: StaffDetail) => void; onCancel: () => void; }
  const { onSuccess, onCancel }: Props = $props();

  const qc = useQueryClient();

  const positionsQuery = createQuery({
    queryKey: ['positions'],
    queryFn: listPositions,
    staleTime: 10 * 60_000,
  });

  let form = $state({
    staff_number: '', first_name: '', last_name: '', middle_name: '',
    gender: '' as '' | 'MALE' | 'FEMALE',
    staff_category: '' as '' | StaffCategory,
    employment_type: '' as '' | 'PERMANENT' | 'CONTRACT' | 'NATIONAL_SERVICE' | 'INTERN',
    position_ids: [] as string[],
    phone: '', email: '', joined_date: '',
  });
  let formError = $state('');

  const teacherPositionId = $derived(() => {
    return ($positionsQuery.data ?? []).find(p => p.name === 'Teacher')?.id ?? null;
  });

  // When category switches to TEACHING, auto-add Teacher position
  $effect(() => {
    const tid = teacherPositionId();
    if (!tid) return;
    if (form.staff_category === 'TEACHING' && !form.position_ids.includes(tid)) {
      form.position_ids = [...form.position_ids, tid];
    }
  });

  const createMut = createMutation({
    mutationFn: createStaff,
    onSuccess: (data: StaffDetail) => {
      qc.invalidateQueries({ queryKey: ['staff'] });
      onSuccess(data);
    },
    onError: (e: unknown) => {
      formError = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? 'Failed to create staff member.';
    },
  });

  function submit() {
    formError = '';
    if (!form.staff_number || !form.first_name || !form.last_name) {
      formError = 'Staff number, first name, and last name are required.';
      return;
    }
    if (!form.staff_category) {
      formError = 'Please select Teaching or Non-Teaching.';
      return;
    }
    $createMut.mutate({
      staff_number:    form.staff_number,
      first_name:      form.first_name,
      last_name:       form.last_name,
      middle_name:     form.middle_name     || undefined,
      gender:          (form.gender         || undefined) as 'MALE' | 'FEMALE' | undefined,
      staff_category:  form.staff_category  as StaffCategory,
      employment_type: (form.employment_type || undefined) as 'PERMANENT' | 'CONTRACT' | 'NATIONAL_SERVICE' | 'INTERN' | undefined,
      position_ids:    form.position_ids.length ? form.position_ids : undefined,
      phone:           form.phone           || undefined,
      email:           form.email           || undefined,
      joined_date:     form.joined_date     || undefined,
    });
  }
</script>

<div class="rounded-xl border border-[var(--border)] bg-[var(--card)] p-5">
  <h2 class="mb-4 text-sm font-semibold text-[var(--fg)]">New Staff Member</h2>

  <!-- Category toggle — must be chosen first -->
  <div class="mb-5">
    <p class="mb-2 text-xs font-medium text-[var(--fg-muted)]">Staff category *</p>
    <div class="flex gap-2">
      {#each [['TEACHING', 'Teaching'], ['NON_TEACHING', 'Non-Teaching']] as [val, label]}
        <button type="button"
          onclick={() => form.staff_category = val as StaffCategory}
          class="rounded-xl border px-4 py-2 text-sm font-medium transition
                 {form.staff_category === val
                   ? 'border-[var(--brand)] text-[var(--brand)] bg-[var(--hover)]'
                   : 'border-[var(--border)] text-[var(--fg-muted)] hover:bg-[var(--hover)]'}">
          {label}
        </button>
      {/each}
    </div>
  </div>

  <div class="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
    {#each [
      { label: 'Staff number *', key: 'staff_number', placeholder: 'e.g. T001' },
      { label: 'First name *',   key: 'first_name',   placeholder: 'First name' },
      { label: 'Last name *',    key: 'last_name',    placeholder: 'Last name'  },
      { label: 'Middle name',    key: 'middle_name',  placeholder: 'Middle name' },
      { label: 'Phone',          key: 'phone',        placeholder: '0XX XXX XXXX' },
      { label: 'Email',          key: 'email',        placeholder: 'staff@school.edu.gh' },
    ] as f}
      <div>
        <label class="mb-1 block text-xs font-medium text-[var(--fg-muted)]">{f.label}</label>
        <input bind:value={form[f.key as keyof typeof form] as string} placeholder={f.placeholder}
          class="w-full rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--fg)] placeholder:text-[var(--fg-muted)] focus:border-[var(--brand)] focus:outline-none" />
      </div>
    {/each}
    <div>
      <label class="mb-1 block text-xs font-medium text-[var(--fg-muted)]">Gender</label>
      <select bind:value={form.gender}
        class="w-full rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--fg)] focus:border-[var(--brand)] focus:outline-none">
        <option value="">Select…</option>
        <option value="MALE">Male</option>
        <option value="FEMALE">Female</option>
      </select>
    </div>
    <div>
      <label class="mb-1 block text-xs font-medium text-[var(--fg-muted)]">Employment type</label>
      <select bind:value={form.employment_type}
        class="w-full rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--fg)] focus:border-[var(--brand)] focus:outline-none">
        <option value="">Select…</option>
        <option value="PERMANENT">Permanent</option>
        <option value="CONTRACT">Contract</option>
        <option value="NATIONAL_SERVICE">National Service</option>
        <option value="INTERN">Intern</option>
      </select>
    </div>
    <div>
      <label class="mb-1 block text-xs font-medium text-[var(--fg-muted)]">Date joined</label>
      <input type="date" bind:value={form.joined_date}
        class="w-full rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--fg)] focus:border-[var(--brand)] focus:outline-none" />
    </div>
    <div class="sm:col-span-2 lg:col-span-3">
      <label class="mb-1 block text-xs font-medium text-[var(--fg-muted)]">
        Positions
        {#if form.staff_category === 'TEACHING'}
          <span class="ml-1 text-[var(--brand)]">— Teacher auto-assigned</span>
        {/if}
      </label>
      <div class="flex flex-wrap gap-3">
        {#each ($positionsQuery.data ?? []).filter(p => !['Teacher', 'House Master / Mistress', 'Class Teacher'].includes(p.name)) as p (p.id)}
          <label class="flex cursor-pointer items-center gap-2 rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--fg)] hover:bg-[var(--hover)]
                        {form.position_ids.includes(p.id) ? 'border-[var(--brand)] bg-[var(--hover)]' : ''}">
            <input type="checkbox" class="accent-[var(--brand)]"
              checked={form.position_ids.includes(p.id)}
              onchange={() => {
                if (form.position_ids.includes(p.id))
                  form.position_ids = form.position_ids.filter(id => id !== p.id);
                else
                  form.position_ids = [...form.position_ids, p.id];
              }} />
            {p.name}
          </label>
        {/each}
      </div>
    </div>
  </div>
  {#if formError}<p class="mt-3 text-xs text-red-500">{formError}</p>{/if}
  <div class="mt-4 flex gap-2">
    <button onclick={submit} disabled={$createMut.isPending}
      class="rounded-xl px-4 py-2 text-sm font-semibold text-white transition hover:opacity-90 disabled:opacity-50"
      style="background-color: var(--brand)">
      {$createMut.isPending ? 'Creating…' : 'Create and open profile'}
    </button>
    <button onclick={onCancel}
      class="rounded-xl border border-[var(--border)] px-4 py-2 text-sm font-medium text-[var(--fg-muted)] transition hover:bg-[var(--bg)]">
      Cancel
    </button>
  </div>
</div>
