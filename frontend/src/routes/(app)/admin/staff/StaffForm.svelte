<script lang="ts">
  import { createMutation, useQueryClient } from '@tanstack/svelte-query';
  import { createStaff, type StaffDetail } from '$lib/api/staff';

  interface Props { onSuccess: (staff: StaffDetail) => void; onCancel: () => void; }
  const { onSuccess, onCancel }: Props = $props();

  const qc = useQueryClient();

  let form = $state({
    staff_number: '', first_name: '', last_name: '', middle_name: '',
    gender: '' as '' | 'MALE' | 'FEMALE',
    phone: '', email: '', department: '', joined_date: '',
  });
  let formError = $state('');

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
    $createMut.mutate({
      staff_number: form.staff_number,
      first_name:   form.first_name,
      last_name:    form.last_name,
      middle_name:  form.middle_name  || undefined,
      gender:       (form.gender      || undefined) as 'MALE' | 'FEMALE' | undefined,
      phone:        form.phone        || undefined,
      email:        form.email        || undefined,
      department:   form.department   || undefined,
      joined_date:  form.joined_date  || undefined,
    });
  }
</script>

<div class="rounded-xl border border-[var(--border)] bg-[var(--card)] p-5">
  <h2 class="mb-4 text-sm font-semibold text-[var(--fg)]">New Staff Member</h2>
  <div class="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
    {#each [
      { label: 'Staff number *', key: 'staff_number', placeholder: 'e.g. T001' },
      { label: 'First name *',   key: 'first_name',   placeholder: 'First name' },
      { label: 'Last name *',    key: 'last_name',    placeholder: 'Last name'  },
      { label: 'Middle name',    key: 'middle_name',  placeholder: 'Middle name' },
      { label: 'Phone',          key: 'phone',        placeholder: '0XX XXX XXXX' },
      { label: 'Email',          key: 'email',        placeholder: 'staff@school.edu.gh' },
      { label: 'Department',     key: 'department',   placeholder: 'e.g. Science' },
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
      <label class="mb-1 block text-xs font-medium text-[var(--fg-muted)]">Date joined</label>
      <input type="date" bind:value={form.joined_date}
        class="w-full rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--fg)] focus:border-[var(--brand)] focus:outline-none" />
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
