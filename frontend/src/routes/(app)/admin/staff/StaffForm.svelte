<script lang="ts">
  import { createMutation, createQuery, useQueryClient } from '@tanstack/svelte-query';
  import { createStaff, listPositions, type StaffCategory, type StaffDetail } from '$lib/api/staff';

  interface Props {
    open: boolean;
    onSuccess: (staff: StaffDetail) => void;
    onCancel: () => void;
  }
  const { open, onSuccess, onCancel }: Props = $props();

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

  const teacherPositionId = $derived(() =>
    ($positionsQuery.data ?? []).find(p => p.name === 'Teacher')?.id ?? null
  );

  $effect(() => {
    const tid = teacherPositionId();
    if (!tid) return;
    if (form.staff_category === 'TEACHING' && !form.position_ids.includes(tid))
      form.position_ids = [...form.position_ids, tid];
  });

  const createMut = createMutation({
    mutationFn: createStaff,
    onSuccess: (data: StaffDetail) => {
      qc.invalidateQueries({ queryKey: ['staff'] });
      form = {
        staff_number: '', first_name: '', last_name: '', middle_name: '',
        gender: '', staff_category: '', employment_type: '',
        position_ids: [], phone: '', email: '', joined_date: '',
      };
      formError = '';
      onSuccess(data);
    },
    onError: (e: unknown) => {
      formError = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
        ?? 'Failed to create staff member.';
    },
  });

  function submit() {
    formError = '';
    if (!form.staff_number || !form.first_name || !form.last_name) {
      formError = 'Staff number, first name, and last name are required.'; return;
    }
    if (!form.staff_category) { formError = 'Please select Teaching or Non-Teaching.'; return; }
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

  const manualPositions = $derived(() =>
    ($positionsQuery.data ?? []).filter(p =>
      !['Teacher', 'House Master / Mistress', 'Class Teacher'].includes(p.name)
    )
  );
</script>

{#if open}
  <div class="fixed inset-0 z-40 bg-black/40 backdrop-blur-sm" onclick={onCancel} role="none"></div>

  <div class="fixed inset-y-0 right-0 z-50 flex w-full max-w-[440px] flex-col
              border-l border-[var(--border)] bg-[var(--card)]"
       style="box-shadow: -8px 0 40px rgba(0,0,0,0.14);">

    <!-- Drawer header -->
    <div class="flex shrink-0 items-center justify-between border-b border-[var(--border)] px-6 py-4">
      <div>
        <h2 class="text-sm font-semibold text-[var(--fg)]">New staff member</h2>
        <p class="mt-0.5 text-xs text-[var(--fg-muted)]">Fill in the details below to add to the directory.</p>
      </div>
      <button onclick={onCancel} aria-label="Close"
        class="flex h-8 w-8 items-center justify-center rounded-lg text-[var(--fg-muted)]
               transition hover:bg-[var(--hover)] hover:text-[var(--fg)]">
        <svg class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12"/>
        </svg>
      </button>
    </div>

    <!-- Scrollable body -->
    <div class="flex-1 space-y-6 overflow-y-auto px-6 py-5">

      <!-- Category -->
      <div>
        <p class="mb-2 text-[10px] font-semibold uppercase tracking-widest text-[var(--fg-muted)]">Staff category *</p>
        <div class="grid grid-cols-2 gap-2">
          {#each [
            ['TEACHING',     'Teaching',     'Classroom & subject teachers'],
            ['NON_TEACHING', 'Non-Teaching', 'Admin, finance, support staff'],
          ] as [val, label, sub]}
            <button type="button"
              onclick={() => form.staff_category = val as StaffCategory}
              class="flex flex-col items-start rounded-xl border p-3 text-left transition
                     {form.staff_category === val
                       ? 'border-[var(--brand)] bg-[var(--brand-dim)]'
                       : 'border-[var(--border)] hover:bg-[var(--hover)]'}">
              <span class="text-sm font-semibold leading-snug
                           {form.staff_category === val ? 'text-[var(--brand)]' : 'text-[var(--fg)]'}">{label}</span>
              <span class="mt-0.5 text-[10px] text-[var(--fg-muted)]">{sub}</span>
            </button>
          {/each}
        </div>
      </div>

      <!-- Identity -->
      <div>
        <p class="mb-3 text-[10px] font-semibold uppercase tracking-widest text-[var(--fg-muted)]">Identity</p>
        <div class="space-y-3">
          <div>
            <label class="mb-1 block text-xs font-medium text-[var(--fg-muted)]">Staff number *</label>
            <input bind:value={form.staff_number} placeholder="e.g. T001"
              class="w-full rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm
                     text-[var(--fg)] placeholder:text-[var(--fg-muted)] focus:border-[var(--brand)] focus:outline-none" />
          </div>
          <div class="grid grid-cols-2 gap-3">
            {#each [
              { label: 'First name *', key: 'first_name',  placeholder: 'First name'  },
              { label: 'Last name *',  key: 'last_name',   placeholder: 'Last name'   },
              { label: 'Middle name',  key: 'middle_name', placeholder: 'Middle name' },
            ] as f}
              <div class="{f.key === 'middle_name' ? 'col-span-2' : ''}">
                <label class="mb-1 block text-xs font-medium text-[var(--fg-muted)]">{f.label}</label>
                <input bind:value={form[f.key as keyof typeof form] as string} placeholder={f.placeholder}
                  class="w-full rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm
                         text-[var(--fg)] placeholder:text-[var(--fg-muted)] focus:border-[var(--brand)] focus:outline-none" />
              </div>
            {/each}
          </div>
          <div>
            <label class="mb-1 block text-xs font-medium text-[var(--fg-muted)]">Gender</label>
            <select bind:value={form.gender}
              class="w-full rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm
                     text-[var(--fg)] focus:border-[var(--brand)] focus:outline-none">
              <option value="">Not specified</option>
              <option value="MALE">Male</option>
              <option value="FEMALE">Female</option>
            </select>
          </div>
        </div>
      </div>

      <!-- Employment -->
      <div>
        <p class="mb-3 text-[10px] font-semibold uppercase tracking-widest text-[var(--fg-muted)]">Employment</p>
        <div class="grid grid-cols-2 gap-3">
          <div>
            <label class="mb-1 block text-xs font-medium text-[var(--fg-muted)]">Employment type</label>
            <select bind:value={form.employment_type}
              class="w-full rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm
                     text-[var(--fg)] focus:border-[var(--brand)] focus:outline-none">
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
              class="w-full rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm
                     text-[var(--fg)] focus:border-[var(--brand)] focus:outline-none" />
          </div>
        </div>
      </div>

      <!-- Contact -->
      <div>
        <p class="mb-3 text-[10px] font-semibold uppercase tracking-widest text-[var(--fg-muted)]">Contact</p>
        <div class="space-y-3">
          {#each [
            { label: 'Phone', key: 'phone', placeholder: '0XX XXX XXXX' },
            { label: 'Email', key: 'email', placeholder: 'staff@school.edu.gh' },
          ] as f}
            <div>
              <label class="mb-1 block text-xs font-medium text-[var(--fg-muted)]">{f.label}</label>
              <input bind:value={form[f.key as keyof typeof form] as string} placeholder={f.placeholder}
                class="w-full rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm
                       text-[var(--fg)] placeholder:text-[var(--fg-muted)] focus:border-[var(--brand)] focus:outline-none" />
            </div>
          {/each}
        </div>
      </div>

      <!-- Positions -->
      {#if manualPositions().length > 0}
        <div>
          <p class="mb-1 text-[10px] font-semibold uppercase tracking-widest text-[var(--fg-muted)]">
            Additional positions
            {#if form.staff_category === 'TEACHING'}
              <span class="ml-1 normal-case font-normal" style="color: var(--brand)">— Teacher auto-assigned</span>
            {/if}
          </p>
          <p class="mb-3 text-[10px] text-[var(--fg-muted)]">
            Functional roles (Teacher, Class Teacher, House Master) are assigned via their respective modules.
          </p>
          <div class="flex flex-wrap gap-2">
            {#each manualPositions() as p (p.id)}
              <label class="flex cursor-pointer items-center gap-1.5 rounded-xl border px-3 py-1.5 text-xs font-medium transition
                            {form.position_ids.includes(p.id)
                              ? 'border-[var(--brand)] bg-[var(--brand-dim)] text-[var(--brand)]'
                              : 'border-[var(--border)] text-[var(--fg-muted)] hover:bg-[var(--hover)]'}">
                <input type="checkbox" class="accent-[var(--brand)] h-3 w-3"
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
      {/if}

    </div>

    <!-- Footer -->
    <div class="shrink-0 border-t border-[var(--border)] px-6 py-4">
      {#if formError}
        <p class="mb-3 text-xs text-red-500">{formError}</p>
      {/if}
      <div class="flex gap-2">
        <button onclick={submit} disabled={$createMut.isPending}
          class="flex-1 rounded-xl py-2.5 text-sm font-semibold text-white transition
                 hover:opacity-90 disabled:opacity-50"
          style="background-color: var(--brand)">
          {$createMut.isPending ? 'Creating…' : 'Create and open profile'}
        </button>
        <button onclick={onCancel}
          class="rounded-xl border border-[var(--border)] px-4 py-2 text-sm font-medium
                 text-[var(--fg-muted)] transition hover:bg-[var(--hover)]">
          Cancel
        </button>
      </div>
    </div>

  </div>
{/if}
