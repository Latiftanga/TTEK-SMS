<script lang="ts">
  import { createMutation, createQuery, useQueryClient } from '@tanstack/svelte-query';
  import { createStaff, listCategories, type StaffDetail } from '$lib/api/staff';
  import { toast } from '$lib/stores/toast';
  import { portal } from '$lib/actions/portal';
  import { apiError } from '$lib/utils';
  import ConfirmModal from '$lib/components/ConfirmModal.svelte';

  interface Props {
    open: boolean;
    onSuccess: (staff: StaffDetail) => void;
    onCancel: () => void;
  }
  const { open, onSuccess, onCancel }: Props = $props();

  const qc = useQueryClient();

  const categoriesQuery = createQuery({
    queryKey: ['staff-categories'],
    queryFn: listCategories,
    staleTime: 10 * 60_000,
  });

  let form = $state({
    staff_number: '', first_name: '', last_name: '', middle_name: '',
    gender: '' as '' | 'MALE' | 'FEMALE',
    category_id: '' as string,
    employment_type: '' as '' | 'PERMANENT' | 'CONTRACT' | 'NATIONAL_SERVICE' | 'INTERN',
    phone: '', email: '', joined_date: '',
  });
  let formError = $state('');

  // A ~10-field drawer, longer than most modals in this app — a stray
  // backdrop tap or Cancel shouldn't silently discard everything typed.
  const hasUnsaved = $derived(Object.values(form).some(v => v !== ''));
  let confirmDiscard = $state(false);

  function requestClose() {
    if (hasUnsaved) confirmDiscard = true;
    else onCancel();
  }

  const createMut = createMutation({
    mutationFn: createStaff,
    onSuccess: (data: StaffDetail) => {
      qc.invalidateQueries({ queryKey: ['staff'] });
      form = {
        staff_number: '', first_name: '', last_name: '', middle_name: '',
        gender: '', category_id: '', employment_type: '',
        phone: '', email: '', joined_date: '',
      };
      formError = '';
      onSuccess(data);
    },
    onError: (e) => {
      formError = apiError(e, 'Failed to create staff member.');
      toast.error(formError);
    },
  });

  function submit() {
    formError = '';
    if (!form.staff_number || !form.first_name || !form.last_name) {
      formError = 'Staff number, first name, and last name are required.'; return;
    }
    $createMut.mutate({
      staff_number:    form.staff_number,
      first_name:      form.first_name,
      last_name:       form.last_name,
      middle_name:     form.middle_name     || undefined,
      gender:          (form.gender         || undefined) as 'MALE' | 'FEMALE' | undefined,
      category_id:     form.category_id     || undefined,
      employment_type: (form.employment_type || undefined) as 'PERMANENT' | 'CONTRACT' | 'NATIONAL_SERVICE' | 'INTERN' | undefined,
      phone:           form.phone           || undefined,
      email:           form.email           || undefined,
      joined_date:     form.joined_date     || undefined,
    });
  }
</script>

{#if open}
  <div use:portal class="contents">
  <div class="fixed inset-0 z-40 bg-black/40 backdrop-blur-sm" onclick={requestClose} role="none"></div>

  <div class="fixed inset-y-0 right-0 z-50 flex w-full max-w-[440px] flex-col
              border-l border-[var(--border)] bg-[var(--card)]"
       style="box-shadow: -8px 0 40px rgba(0,0,0,0.14);">

    <!-- Drawer header -->
    <div class="flex shrink-0 items-center justify-between border-b border-[var(--border)] px-6 py-4">
      <div>
        <h2 class="text-sm font-semibold text-[var(--fg)]">New staff member</h2>
        <p class="mt-0.5 text-xs text-[var(--fg-muted)]">Fill in the details below to add to the directory.</p>
      </div>
      <button onclick={requestClose} aria-label="Close"
        class="flex min-h-[44px] min-w-[44px] items-center justify-center rounded-lg text-[var(--fg-muted)]
               transition hover:bg-[var(--hover)] hover:text-[var(--fg)]">
        <svg class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12"/>
        </svg>
      </button>
    </div>

    <!-- Scrollable body -->
    <div class="flex-1 space-y-6 overflow-y-auto px-6 py-5">

      <!-- Identity -->
      <div>
        <p class="mb-3 text-[11px] font-semibold uppercase tracking-widest text-[var(--fg-muted)]">Identity</p>
        <div class="space-y-3">
          <div>
            <label class="mb-1 block text-xs font-medium text-[var(--fg-muted)]">Staff number *</label>
            <input bind:value={form.staff_number} placeholder="e.g. T001"
              class="w-full min-h-[44px] rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm
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
                  class="w-full min-h-[44px] rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm
                         text-[var(--fg)] placeholder:text-[var(--fg-muted)] focus:border-[var(--brand)] focus:outline-none" />
              </div>
            {/each}
          </div>
          <div>
            <label class="mb-1 block text-xs font-medium text-[var(--fg-muted)]">Gender</label>
            <select bind:value={form.gender}
              class="w-full min-h-[44px] rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm
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
        <p class="mb-3 text-[11px] font-semibold uppercase tracking-widest text-[var(--fg-muted)]">Employment</p>
        <div class="space-y-3">
          <div>
            <label class="mb-1 block text-xs font-medium text-[var(--fg-muted)]">Category</label>
            <select bind:value={form.category_id}
              class="w-full min-h-[44px] rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm
                     text-[var(--fg)] focus:border-[var(--brand)] focus:outline-none">
              <option value="">Select category…</option>
              {#each $categoriesQuery.data ?? [] as cat (cat.id)}
                <option value={cat.id}>{cat.name}</option>
              {/each}
            </select>
          </div>
          <div class="grid grid-cols-2 gap-3">
            <div>
              <label class="mb-1 block text-xs font-medium text-[var(--fg-muted)]">Employment type</label>
              <select bind:value={form.employment_type}
                class="w-full min-h-[44px] rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm
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
                class="w-full min-h-[44px] rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm
                       text-[var(--fg)] focus:border-[var(--brand)] focus:outline-none" />
            </div>
          </div>
        </div>
      </div>

      <!-- Contact -->
      <div>
        <p class="mb-3 text-[11px] font-semibold uppercase tracking-widest text-[var(--fg-muted)]">Contact</p>
        <div class="space-y-3">
          {#each [
            { label: 'Phone', key: 'phone', placeholder: '0XX XXX XXXX' },
            { label: 'Email', key: 'email', placeholder: 'staff@school.edu.gh' },
          ] as f}
            <div>
              <label class="mb-1 block text-xs font-medium text-[var(--fg-muted)]">{f.label}</label>
              <input bind:value={form[f.key as keyof typeof form] as string} placeholder={f.placeholder}
                class="w-full min-h-[44px] rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm
                       text-[var(--fg)] placeholder:text-[var(--fg-muted)] focus:border-[var(--brand)] focus:outline-none" />
            </div>
          {/each}
        </div>
      </div>

    </div>

    <!-- Footer -->
    <div class="shrink-0 border-t border-[var(--border)] px-6 py-4">
      {#if formError}
        <p class="mb-3 text-xs text-red-500">{formError}</p>
      {/if}
      <div class="flex gap-2">
        <button onclick={submit} disabled={$createMut.isPending}
          class="min-h-[44px] flex-1 rounded-xl py-2.5 text-sm font-semibold text-white transition
                 hover:opacity-90 disabled:opacity-50"
          style="background-color: var(--brand)">
          {$createMut.isPending ? 'Creating…' : 'Create and open profile'}
        </button>
        <button onclick={requestClose}
          class="min-h-[44px] rounded-xl border border-[var(--border)] px-4 py-2 text-sm font-medium
                 text-[var(--fg-muted)] transition hover:bg-[var(--hover)]">
          Cancel
        </button>
      </div>
    </div>

  </div>
  </div>

  <ConfirmModal
    open={confirmDiscard}
    title="Discard new staff member?"
    message="You've entered details that haven't been saved yet. Closing now will lose them."
    confirmLabel="Discard"
    variant="warning"
    onConfirm={() => { confirmDiscard = false; onCancel(); }}
    onCancel={() => confirmDiscard = false}
  />
{/if}
