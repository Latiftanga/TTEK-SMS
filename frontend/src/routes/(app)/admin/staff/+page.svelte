<script lang="ts">
  import { createQuery, createMutation, useQueryClient } from '@tanstack/svelte-query';
  import { goto } from '$app/navigation';
  import { listStaff, createStaff, type StaffSummary } from '$lib/api/staff';

  const qc = useQueryClient();

  let activeOnly = $state(true);
  let search = $state('');

  const query = createQuery({
    queryKey: ['staff', activeOnly],
    queryFn: () => listStaff({ active_only: activeOnly }),
    staleTime: 2 * 60_000,
  });

  const filtered = $derived(() => {
    const q = search.trim().toLowerCase();
    if (!q) return $query.data ?? [];
    return ($query.data ?? []).filter((s: StaffSummary) =>
      s.display_name.toLowerCase().includes(q) ||
      s.staff_number.toLowerCase().includes(q) ||
      (s.position_name ?? '').toLowerCase().includes(q) ||
      (s.department ?? '').toLowerCase().includes(q)
    );
  });

  let showForm = $state(false);
  let form = $state({
    staff_number: '',
    first_name: '',
    last_name: '',
    middle_name: '',
    gender: '' as '' | 'MALE' | 'FEMALE',
    phone: '',
    email: '',
    department: '',
    joined_date: '',
  });
  let formError = $state('');

  const createMut = createMutation({
    mutationFn: createStaff,
    onSuccess: (data: import('$lib/api/staff').StaffDetail) => {
      qc.invalidateQueries({ queryKey: ['staff'] });
      showForm = false;
      form = {
        staff_number: '', first_name: '', last_name: '', middle_name: '',
        gender: '', phone: '', email: '', department: '', joined_date: '',
      };
      goto(`/admin/staff/${data.id}`);
    },
    onError: (e: unknown) => {
      formError = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? 'Failed to create staff.';
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
      first_name: form.first_name,
      last_name: form.last_name,
      middle_name: form.middle_name || undefined,
      gender: (form.gender || undefined) as 'MALE' | 'FEMALE' | undefined,
      phone: form.phone || undefined,
      email: form.email || undefined,
      department: form.department || undefined,
      joined_date: form.joined_date || undefined,
    });
  }

  function initials(s: StaffSummary) {
    return (s.first_name[0] + s.last_name[0]).toUpperCase();
  }

  const GENDER_COLORS: Record<string, string> = {
    MALE: '#3B82F6',
    FEMALE: '#EC4899',
  };
</script>

<div class="space-y-6">
  <!-- Header -->
  <div class="flex flex-wrap items-center justify-between gap-3">
    <div>
      <h1 class="text-2xl font-bold text-[var(--fg)]">Staff</h1>
      <p class="mt-0.5 text-sm text-[var(--fg-muted)]">
        {($query.data ?? []).length} member{($query.data ?? []).length !== 1 ? 's' : ''} on record
      </p>
    </div>
    <button
      onclick={() => { showForm = !showForm; formError = ''; }}
      class="flex items-center gap-2 rounded-xl px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:opacity-90 active:scale-[0.98]"
      style="background-color: var(--brand)"
    >
      <svg class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" d="M12 4v16m8-8H4"/>
      </svg>
      Add staff
    </button>
  </div>

  <!-- Add staff form -->
  {#if showForm}
    <div class="rounded-2xl border border-[var(--border)] bg-[var(--card)] p-5">
      <h2 class="mb-4 text-sm font-semibold text-[var(--fg)]">New Staff Member</h2>
      <div class="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <div>
          <label class="mb-1 block text-xs font-medium text-[var(--fg-muted)]">Staff number *</label>
          <input bind:value={form.staff_number} placeholder="e.g. T001"
            class="w-full rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2.5 text-sm text-[var(--fg)] placeholder:text-[var(--fg-muted)] focus:border-[var(--brand)] focus:outline-none focus:ring-2 focus:ring-[var(--brand)]/20" />
        </div>
        <div>
          <label class="mb-1 block text-xs font-medium text-[var(--fg-muted)]">First name *</label>
          <input bind:value={form.first_name} placeholder="First name"
            class="w-full rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2.5 text-sm text-[var(--fg)] placeholder:text-[var(--fg-muted)] focus:border-[var(--brand)] focus:outline-none focus:ring-2 focus:ring-[var(--brand)]/20" />
        </div>
        <div>
          <label class="mb-1 block text-xs font-medium text-[var(--fg-muted)]">Last name *</label>
          <input bind:value={form.last_name} placeholder="Last name"
            class="w-full rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2.5 text-sm text-[var(--fg)] placeholder:text-[var(--fg-muted)] focus:border-[var(--brand)] focus:outline-none focus:ring-2 focus:ring-[var(--brand)]/20" />
        </div>
        <div>
          <label class="mb-1 block text-xs font-medium text-[var(--fg-muted)]">Middle name</label>
          <input bind:value={form.middle_name} placeholder="Middle name"
            class="w-full rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2.5 text-sm text-[var(--fg)] placeholder:text-[var(--fg-muted)] focus:border-[var(--brand)] focus:outline-none focus:ring-2 focus:ring-[var(--brand)]/20" />
        </div>
        <div>
          <label class="mb-1 block text-xs font-medium text-[var(--fg-muted)]">Gender</label>
          <select bind:value={form.gender}
            class="w-full rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2.5 text-sm text-[var(--fg)] focus:border-[var(--brand)] focus:outline-none">
            <option value="">Select…</option>
            <option value="MALE">Male</option>
            <option value="FEMALE">Female</option>
          </select>
        </div>
        <div>
          <label class="mb-1 block text-xs font-medium text-[var(--fg-muted)]">Phone</label>
          <input bind:value={form.phone} placeholder="0XX XXX XXXX"
            class="w-full rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2.5 text-sm text-[var(--fg)] placeholder:text-[var(--fg-muted)] focus:border-[var(--brand)] focus:outline-none focus:ring-2 focus:ring-[var(--brand)]/20" />
        </div>
        <div>
          <label class="mb-1 block text-xs font-medium text-[var(--fg-muted)]">Email</label>
          <input type="email" bind:value={form.email} placeholder="staff@school.edu.gh"
            class="w-full rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2.5 text-sm text-[var(--fg)] placeholder:text-[var(--fg-muted)] focus:border-[var(--brand)] focus:outline-none focus:ring-2 focus:ring-[var(--brand)]/20" />
        </div>
        <div>
          <label class="mb-1 block text-xs font-medium text-[var(--fg-muted)]">Department</label>
          <input bind:value={form.department} placeholder="e.g. Science"
            class="w-full rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2.5 text-sm text-[var(--fg)] placeholder:text-[var(--fg-muted)] focus:border-[var(--brand)] focus:outline-none focus:ring-2 focus:ring-[var(--brand)]/20" />
        </div>
        <div>
          <label class="mb-1 block text-xs font-medium text-[var(--fg-muted)]">Date joined</label>
          <input type="date" bind:value={form.joined_date}
            class="w-full rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2.5 text-sm text-[var(--fg)] focus:border-[var(--brand)] focus:outline-none focus:ring-2 focus:ring-[var(--brand)]/20" />
        </div>
      </div>
      {#if formError}
        <p class="mt-2 text-xs text-red-500">{formError}</p>
      {/if}
      <div class="mt-4 flex gap-2">
        <button onclick={submit} disabled={$createMut.isPending}
          class="rounded-xl px-4 py-2 text-sm font-semibold text-white transition hover:opacity-90 disabled:opacity-50"
          style="background-color: var(--brand)">
          {$createMut.isPending ? 'Creating…' : 'Create and view profile'}
        </button>
        <button onclick={() => { showForm = false; formError = ''; }}
          class="rounded-xl border border-[var(--border)] px-4 py-2 text-sm font-medium text-[var(--fg-muted)] transition hover:bg-[var(--bg)]">
          Cancel
        </button>
      </div>
    </div>
  {/if}

  <!-- Search + filter -->
  <div class="flex flex-wrap gap-3">
    <div class="relative flex-1 min-w-48">
      <svg class="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--fg-muted)]"
           fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
        <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
      </svg>
      <input
        bind:value={search}
        placeholder="Search name, ID, position…"
        class="w-full rounded-xl border border-[var(--border)] bg-[var(--card)] py-2.5 pl-9 pr-4 text-sm text-[var(--fg)] placeholder:text-[var(--fg-muted)] focus:border-[var(--brand)] focus:outline-none focus:ring-2 focus:ring-[var(--brand)]/20"
      />
    </div>
    <label class="flex cursor-pointer items-center gap-2 rounded-xl border border-[var(--border)] bg-[var(--card)] px-4 py-2.5 text-sm text-[var(--fg-muted)]">
      <input type="checkbox" bind:checked={activeOnly} class="accent-[var(--brand)] rounded" />
      Active only
    </label>
  </div>

  <!-- List -->
  {#if $query.isPending}
    <div class="space-y-2">
      {#each [1,2,3,4,5] as _}
        <div class="h-16 animate-pulse rounded-2xl bg-[var(--card)]"></div>
      {/each}
    </div>
  {:else if $query.isError}
    <div class="rounded-2xl border border-red-100 dark:border-red-900 bg-red-50 dark:bg-red-950/40 p-5 text-sm text-red-600 dark:text-red-400">
      Could not load staff.
      <button onclick={() => $query.refetch()} class="ml-2 underline">Retry</button>
    </div>
  {:else if filtered().length === 0}
    <div class="rounded-2xl border border-dashed border-[var(--border)] p-10 text-center">
      <p class="text-sm text-[var(--fg-muted)]">
        {search ? 'No staff match your search.' : 'No staff on record yet.'}
      </p>
    </div>
  {:else}
    <div class="overflow-hidden rounded-2xl border border-[var(--border)] bg-[var(--card)]">
      <table class="w-full text-sm">
        <thead>
          <tr class="border-b border-[var(--border)] text-left">
            <th class="px-5 py-3 text-xs font-semibold uppercase tracking-widest text-[var(--fg-muted)]">Staff</th>
            <th class="hidden px-5 py-3 text-xs font-semibold uppercase tracking-widest text-[var(--fg-muted)] md:table-cell">Position</th>
            <th class="hidden px-5 py-3 text-xs font-semibold uppercase tracking-widest text-[var(--fg-muted)] lg:table-cell">Contact</th>
            <th class="px-5 py-3 text-xs font-semibold uppercase tracking-widest text-[var(--fg-muted)]">Status</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-[var(--border)]">
          {#each filtered() as s (s.id)}
            <tr
              onclick={() => goto(`/admin/staff/${s.id}`)}
              class="group cursor-pointer transition hover:bg-[var(--bg)]"
            >
              <td class="px-5 py-3.5">
                <div class="flex items-center gap-3">
                  <div class="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl text-xs font-bold text-white"
                       style="background-color: {GENDER_COLORS[s.gender ?? ''] ?? 'var(--brand)'}">
                    {initials(s)}
                  </div>
                  <div>
                    <p class="font-semibold text-[var(--fg)]">{s.display_name}</p>
                    <p class="text-xs text-[var(--fg-muted)]">{s.staff_number}{s.department ? ' · ' + s.department : ''}</p>
                  </div>
                </div>
              </td>
              <td class="hidden px-5 py-3.5 text-[var(--fg-muted)] md:table-cell">
                {s.position_name ?? '—'}
              </td>
              <td class="hidden px-5 py-3.5 lg:table-cell">
                <p class="text-[var(--fg-muted)]">{s.phone ?? s.email ?? '—'}</p>
              </td>
              <td class="px-5 py-3.5">
                <span class="rounded-full px-2 py-0.5 text-[10px] font-semibold
                             {s.is_active
                               ? 'bg-green-100 dark:bg-green-950/50 text-green-700 dark:text-green-400'
                               : 'bg-gray-100 dark:bg-gray-800 text-gray-500'}">
                  {s.is_active ? 'Active' : 'Inactive'}
                </span>
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  {/if}
</div>
