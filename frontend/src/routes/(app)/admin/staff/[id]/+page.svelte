<script lang="ts">
  import { page } from '$app/stores';
  import { createQuery, createMutation, useQueryClient } from '@tanstack/svelte-query';
  import {
    getStaff,
    updateStaff,
    addQualification,
    deleteQualification,
    addEmergencyContact,
    deleteEmergencyContact,
    listLeave,
    submitLeave,
    type StaffDetail,
    type Leave,
  } from '$lib/api/staff';

  const qc = useQueryClient();
  const staffId = $derived(() => $page.params.id);

  const query = createQuery({
    queryKey: ['staff', staffId()],
    queryFn: () => getStaff(staffId()),
    staleTime: 2 * 60_000,
  });

  const leaveQuery = createQuery({
    queryKey: ['staff-leave', staffId()],
    queryFn: () => listLeave(staffId()),
    staleTime: 60_000,
  });

  let tab = $state<'profile' | 'qualifications' | 'leave'>('profile');

  // Qualification form
  let showQualForm = $state(false);
  let qualForm = $state({ institution: '', qualification_type: '', field_of_study: '', year_obtained: '' });
  let qualError = $state('');

  // Emergency contact form
  let showContactForm = $state(false);
  let contactForm = $state({ name: '', contact_type: '', phone: '', email: '' });
  let contactError = $state('');

  // Leave form
  let showLeaveForm = $state(false);
  let leaveForm = $state({ leave_type: '', start_date: '', end_date: '', days_count: '', reason: '' });
  let leaveError = $state('');

  const addQualMut = createMutation({
    mutationFn: ({ staffId, req }: { staffId: string; req: typeof qualForm }) =>
      addQualification(staffId, {
        institution: req.institution,
        qualification_type: req.qualification_type,
        field_of_study: req.field_of_study || undefined,
        year_obtained: req.year_obtained ? Number(req.year_obtained) : undefined,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['staff', staffId()] });
      showQualForm = false;
      qualForm = { institution: '', qualification_type: '', field_of_study: '', year_obtained: '' };
      qualError = '';
    },
    onError: (e: unknown) => {
      qualError = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? 'Failed.';
    },
  });

  const delQualMut = createMutation({
    mutationFn: ({ staffId, qualId }: { staffId: string; qualId: string }) =>
      deleteQualification(staffId, qualId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['staff', staffId()] }),
  });

  const addContactMut = createMutation({
    mutationFn: ({ staffId, req }: { staffId: string; req: typeof contactForm }) =>
      addEmergencyContact(staffId, {
        name: req.name,
        contact_type: req.contact_type,
        phone: req.phone,
        email: req.email || undefined,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['staff', staffId()] });
      showContactForm = false;
      contactForm = { name: '', contact_type: '', phone: '', email: '' };
      contactError = '';
    },
    onError: (e: unknown) => {
      contactError = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? 'Failed.';
    },
  });

  const delContactMut = createMutation({
    mutationFn: ({ staffId, contactId }: { staffId: string; contactId: string }) =>
      deleteEmergencyContact(staffId, contactId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['staff', staffId()] }),
  });

  const leaveMut = createMutation({
    mutationFn: ({ staffId, req }: { staffId: string; req: typeof leaveForm }) =>
      submitLeave(staffId, {
        leave_type: req.leave_type,
        start_date: req.start_date,
        end_date: req.end_date,
        days_count: Number(req.days_count),
        reason: req.reason || undefined,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['staff-leave', staffId()] });
      showLeaveForm = false;
      leaveForm = { leave_type: '', start_date: '', end_date: '', days_count: '', reason: '' };
      leaveError = '';
    },
    onError: (e: unknown) => {
      leaveError = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? 'Failed.';
    },
  });

  function fmtDate(d: string | null) {
    if (!d) return '—';
    return new Date(d).toLocaleDateString('en-GH', { day: 'numeric', month: 'short', year: 'numeric' });
  }

  const LEAVE_TYPES = ['Annual', 'Sick', 'Maternity', 'Paternity', 'Study', 'Emergency', 'Unpaid'];

  const STATUS_STYLE: Record<string, string> = {
    PENDING: 'bg-amber-100 dark:bg-amber-950/50 text-amber-700 dark:text-amber-400',
    APPROVED: 'bg-green-100 dark:bg-green-950/50 text-green-700 dark:text-green-400',
    REJECTED: 'bg-red-100 dark:bg-red-950/50 text-red-700 dark:text-red-400',
    CANCELLED: 'bg-gray-100 dark:bg-gray-800 text-gray-500',
  };
</script>

<!-- Back link -->
<div class="mb-5">
  <a href="/admin/staff"
     class="inline-flex items-center gap-1.5 text-sm text-[var(--fg-muted)] transition hover:text-[var(--fg)]">
    <svg class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
      <path stroke-linecap="round" stroke-linejoin="round" d="M15 19l-7-7 7-7"/>
    </svg>
    All staff
  </a>
</div>

{#if $query.isPending}
  <div class="space-y-4">
    <div class="h-32 animate-pulse rounded-2xl bg-[var(--card)]"></div>
    <div class="h-48 animate-pulse rounded-2xl bg-[var(--card)]"></div>
  </div>
{:else if $query.isError}
  <div class="rounded-2xl border border-red-100 dark:border-red-900 bg-red-50 dark:bg-red-950/40 p-5 text-sm text-red-600 dark:text-red-400">
    Could not load staff member.
    <button onclick={() => $query.refetch()} class="ml-2 underline">Retry</button>
  </div>
{:else if $query.data}
  {@const s = $query.data}

  <!-- Profile hero -->
  <div class="mb-6 overflow-hidden rounded-2xl border border-[var(--border)] bg-[var(--card)]">
    <div class="flex flex-wrap items-start gap-5 p-6">
      <div class="flex h-16 w-16 shrink-0 items-center justify-center rounded-2xl text-2xl font-bold text-white shadow-sm"
           style="background-color: {s.gender === 'FEMALE' ? '#EC4899' : 'var(--brand)'}">
        {s.first_name[0]}{s.last_name[0]}
      </div>
      <div class="flex-1 min-w-0">
        <div class="flex flex-wrap items-center gap-2">
          <h1 class="text-xl font-bold text-[var(--fg)]">{s.display_name}</h1>
          <span class="rounded-full px-2.5 py-0.5 text-xs font-semibold
                       {s.is_active
                         ? 'bg-green-100 dark:bg-green-950/50 text-green-700 dark:text-green-400'
                         : 'bg-gray-100 dark:bg-gray-800 text-gray-500'}">
            {s.is_active ? 'Active' : 'Inactive'}
          </span>
        </div>
        <p class="mt-0.5 text-sm text-[var(--fg-muted)]">
          {s.staff_number}{s.position_name ? ' · ' + s.position_name : ''}{s.department ? ' · ' + s.department : ''}
        </p>
        <div class="mt-3 flex flex-wrap gap-4 text-xs text-[var(--fg-muted)]">
          {#if s.phone}
            <span>📞 {s.phone}</span>
          {/if}
          {#if s.email}
            <span>✉ {s.email}</span>
          {/if}
          {#if s.joined_date}
            <span>📅 Joined {fmtDate(s.joined_date)}</span>
          {/if}
          {#if s.gender}
            <span>{s.gender === 'MALE' ? '♂' : '♀'} {s.gender.charAt(0) + s.gender.slice(1).toLowerCase()}</span>
          {/if}
        </div>
      </div>
    </div>
  </div>

  <!-- Tabs -->
  <div class="mb-5 flex gap-1 rounded-xl bg-[var(--bg)] p-1 w-fit border border-[var(--border)]">
    {#each (['profile', 'qualifications', 'leave'] as const) as t}
      <button
        onclick={() => tab = t}
        class="rounded-lg px-4 py-2 text-sm font-medium transition capitalize
               {tab === t ? 'bg-[var(--card)] text-[var(--fg)] shadow-sm' : 'text-[var(--fg-muted)] hover:text-[var(--fg)]'}"
      >
        {t === 'qualifications' ? 'Qualifications' : t === 'leave' ? 'Leave' : 'Profile'}
      </button>
    {/each}
  </div>

  <!-- PROFILE tab -->
  {#if tab === 'profile'}
    <div class="space-y-5">
      <!-- Personal details -->
      <div class="rounded-2xl border border-[var(--border)] bg-[var(--card)] p-5">
        <h2 class="mb-4 text-xs font-semibold uppercase tracking-widest text-[var(--fg-muted)]">Personal details</h2>
        <dl class="grid gap-x-6 gap-y-3 sm:grid-cols-2">
          {#each [
            ['Full name', s.display_name],
            ['Staff number', s.staff_number],
            ['Date of birth', fmtDate(s.date_of_birth)],
            ['National ID', s.national_id ?? '—'],
            ['Gender', s.gender ? s.gender.charAt(0) + s.gender.slice(1).toLowerCase() : '—'],
            ['Phone', s.phone ?? '—'],
            ['Email', s.email ?? '—'],
            ['Position', s.position_name ?? '—'],
            ['Department', s.department ?? '—'],
            ['Date joined', fmtDate(s.joined_date)],
          ] as [label, value]}
            <div>
              <dt class="text-[10px] font-semibold uppercase tracking-widest text-[var(--fg-muted)]">{label}</dt>
              <dd class="mt-0.5 text-sm text-[var(--fg)]">{value}</dd>
            </div>
          {/each}
        </dl>
      </div>

      <!-- Emergency contacts -->
      <div class="rounded-2xl border border-[var(--border)] bg-[var(--card)] p-5">
        <div class="mb-4 flex items-center justify-between">
          <h2 class="text-xs font-semibold uppercase tracking-widest text-[var(--fg-muted)]">Emergency contacts</h2>
          {#if !showContactForm}
            <button onclick={() => showContactForm = true}
              class="text-xs font-semibold transition hover:underline" style="color: var(--brand)">
              + Add
            </button>
          {/if}
        </div>

        {#if showContactForm}
          <div class="mb-4 rounded-xl border border-[var(--border)] bg-[var(--bg)] p-4 space-y-3">
            <div class="grid gap-3 sm:grid-cols-2">
              <div>
                <label class="mb-1 block text-xs font-medium text-[var(--fg-muted)]">Name</label>
                <input bind:value={contactForm.name}
                  class="w-full rounded-xl border border-[var(--border)] bg-[var(--card)] px-3 py-2 text-sm text-[var(--fg)] focus:border-[var(--brand)] focus:outline-none" />
              </div>
              <div>
                <label class="mb-1 block text-xs font-medium text-[var(--fg-muted)]">Relationship</label>
                <input bind:value={contactForm.contact_type} placeholder="e.g. Spouse, Parent"
                  class="w-full rounded-xl border border-[var(--border)] bg-[var(--card)] px-3 py-2 text-sm text-[var(--fg)] focus:border-[var(--brand)] focus:outline-none" />
              </div>
              <div>
                <label class="mb-1 block text-xs font-medium text-[var(--fg-muted)]">Phone</label>
                <input bind:value={contactForm.phone}
                  class="w-full rounded-xl border border-[var(--border)] bg-[var(--card)] px-3 py-2 text-sm text-[var(--fg)] focus:border-[var(--brand)] focus:outline-none" />
              </div>
              <div>
                <label class="mb-1 block text-xs font-medium text-[var(--fg-muted)]">Email (optional)</label>
                <input type="email" bind:value={contactForm.email}
                  class="w-full rounded-xl border border-[var(--border)] bg-[var(--card)] px-3 py-2 text-sm text-[var(--fg)] focus:border-[var(--brand)] focus:outline-none" />
              </div>
            </div>
            {#if contactError}<p class="text-xs text-red-500">{contactError}</p>{/if}
            <div class="flex gap-2">
              <button onclick={() => $addContactMut.mutate({ staffId: staffId(), req: contactForm })}
                disabled={$addContactMut.isPending}
                class="rounded-xl px-4 py-1.5 text-xs font-semibold text-white transition hover:opacity-90 disabled:opacity-50"
                style="background-color: var(--brand)">
                {$addContactMut.isPending ? 'Saving…' : 'Save'}
              </button>
              <button onclick={() => { showContactForm = false; contactError = ''; }}
                class="rounded-xl border border-[var(--border)] px-4 py-1.5 text-xs font-medium text-[var(--fg-muted)] transition hover:bg-[var(--card)]">
                Cancel
              </button>
            </div>
          </div>
        {/if}

        {#if s.emergency_contacts.length === 0}
          <p class="text-sm text-[var(--fg-muted)]">No emergency contacts on file.</p>
        {:else}
          <div class="space-y-2">
            {#each s.emergency_contacts as c (c.id)}
              <div class="flex items-center justify-between rounded-xl border border-[var(--border)] bg-[var(--bg)] px-4 py-3">
                <div>
                  <p class="text-sm font-medium text-[var(--fg)]">{c.name} <span class="text-xs text-[var(--fg-muted)]">({c.contact_type})</span></p>
                  <p class="text-xs text-[var(--fg-muted)]">{c.phone}{c.email ? ' · ' + c.email : ''}</p>
                </div>
                <button onclick={() => $delContactMut.mutate({ staffId: staffId(), contactId: c.id })}
                  class="text-xs text-[var(--fg-muted)] transition hover:text-red-500">
                  Remove
                </button>
              </div>
            {/each}
          </div>
        {/if}
      </div>
    </div>

  <!-- QUALIFICATIONS tab -->
  {:else if tab === 'qualifications'}
    <div class="space-y-4">
      <div class="flex justify-end">
        <button onclick={() => { showQualForm = !showQualForm; qualError = ''; }}
          class="flex items-center gap-2 rounded-xl px-4 py-2 text-sm font-semibold text-white transition hover:opacity-90"
          style="background-color: var(--brand)">
          <svg class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" d="M12 4v16m8-8H4"/>
          </svg>
          Add qualification
        </button>
      </div>

      {#if showQualForm}
        <div class="rounded-2xl border border-[var(--border)] bg-[var(--card)] p-5">
          <div class="grid gap-4 sm:grid-cols-2">
            <div>
              <label class="mb-1 block text-xs font-medium text-[var(--fg-muted)]">Institution</label>
              <input bind:value={qualForm.institution} placeholder="e.g. University of Ghana"
                class="w-full rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2.5 text-sm text-[var(--fg)] focus:border-[var(--brand)] focus:outline-none" />
            </div>
            <div>
              <label class="mb-1 block text-xs font-medium text-[var(--fg-muted)]">Qualification</label>
              <input bind:value={qualForm.qualification_type} placeholder="e.g. Bachelor's, PGCE, PhD"
                class="w-full rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2.5 text-sm text-[var(--fg)] focus:border-[var(--brand)] focus:outline-none" />
            </div>
            <div>
              <label class="mb-1 block text-xs font-medium text-[var(--fg-muted)]">Field of study</label>
              <input bind:value={qualForm.field_of_study} placeholder="e.g. Mathematics Education"
                class="w-full rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2.5 text-sm text-[var(--fg)] focus:border-[var(--brand)] focus:outline-none" />
            </div>
            <div>
              <label class="mb-1 block text-xs font-medium text-[var(--fg-muted)]">Year obtained</label>
              <input type="number" bind:value={qualForm.year_obtained} placeholder="e.g. 2018"
                class="w-full rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2.5 text-sm text-[var(--fg)] focus:border-[var(--brand)] focus:outline-none" />
            </div>
          </div>
          {#if qualError}<p class="mt-2 text-xs text-red-500">{qualError}</p>{/if}
          <div class="mt-4 flex gap-2">
            <button onclick={() => $addQualMut.mutate({ staffId: staffId(), req: qualForm })}
              disabled={$addQualMut.isPending}
              class="rounded-xl px-4 py-2 text-sm font-semibold text-white transition hover:opacity-90 disabled:opacity-50"
              style="background-color: var(--brand)">
              {$addQualMut.isPending ? 'Saving…' : 'Add'}
            </button>
            <button onclick={() => { showQualForm = false; qualError = ''; }}
              class="rounded-xl border border-[var(--border)] px-4 py-2 text-sm font-medium text-[var(--fg-muted)] transition hover:bg-[var(--bg)]">
              Cancel
            </button>
          </div>
        </div>
      {/if}

      {#if s.qualifications.length === 0}
        <div class="rounded-2xl border border-dashed border-[var(--border)] p-10 text-center">
          <p class="text-sm text-[var(--fg-muted)]">No qualifications recorded.</p>
        </div>
      {:else}
        <div class="overflow-hidden rounded-2xl border border-[var(--border)] bg-[var(--card)]">
          {#each s.qualifications as q, i (q.id)}
            <div class="flex items-start gap-4 px-5 py-4 {i > 0 ? 'border-t border-[var(--border)]' : ''}">
              <div class="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-[var(--bg)] text-lg">🎓</div>
              <div class="flex-1 min-w-0">
                <p class="font-semibold text-[var(--fg)]">{q.qualification_type}</p>
                <p class="text-sm text-[var(--fg-muted)]">{q.institution}{q.field_of_study ? ' · ' + q.field_of_study : ''}</p>
                {#if q.year_obtained}
                  <p class="text-xs text-[var(--fg-muted)]">{q.year_obtained}</p>
                {/if}
              </div>
              <button onclick={() => $delQualMut.mutate({ staffId: staffId(), qualId: q.id })}
                class="shrink-0 text-xs text-[var(--fg-muted)] transition hover:text-red-500">
                Remove
              </button>
            </div>
          {/each}
        </div>
      {/if}
    </div>

  <!-- LEAVE tab -->
  {:else if tab === 'leave'}
    <div class="space-y-4">
      <div class="flex justify-end">
        <button onclick={() => { showLeaveForm = !showLeaveForm; leaveError = ''; }}
          class="flex items-center gap-2 rounded-xl px-4 py-2 text-sm font-semibold text-white transition hover:opacity-90"
          style="background-color: var(--brand)">
          <svg class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" d="M12 4v16m8-8H4"/>
          </svg>
          Submit leave
        </button>
      </div>

      {#if showLeaveForm}
        <div class="rounded-2xl border border-[var(--border)] bg-[var(--card)] p-5">
          <div class="grid gap-4 sm:grid-cols-2">
            <div>
              <label class="mb-1 block text-xs font-medium text-[var(--fg-muted)]">Leave type</label>
              <select bind:value={leaveForm.leave_type}
                class="w-full rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2.5 text-sm text-[var(--fg)] focus:border-[var(--brand)] focus:outline-none">
                <option value="">Select…</option>
                {#each LEAVE_TYPES as lt}
                  <option value={lt}>{lt}</option>
                {/each}
              </select>
            </div>
            <div>
              <label class="mb-1 block text-xs font-medium text-[var(--fg-muted)]">Days count</label>
              <input type="number" bind:value={leaveForm.days_count} placeholder="Number of days"
                class="w-full rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2.5 text-sm text-[var(--fg)] focus:border-[var(--brand)] focus:outline-none" />
            </div>
            <div>
              <label class="mb-1 block text-xs font-medium text-[var(--fg-muted)]">Start date</label>
              <input type="date" bind:value={leaveForm.start_date}
                class="w-full rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2.5 text-sm text-[var(--fg)] focus:border-[var(--brand)] focus:outline-none" />
            </div>
            <div>
              <label class="mb-1 block text-xs font-medium text-[var(--fg-muted)]">End date</label>
              <input type="date" bind:value={leaveForm.end_date}
                class="w-full rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2.5 text-sm text-[var(--fg)] focus:border-[var(--brand)] focus:outline-none" />
            </div>
            <div class="sm:col-span-2">
              <label class="mb-1 block text-xs font-medium text-[var(--fg-muted)]">Reason (optional)</label>
              <textarea bind:value={leaveForm.reason} rows="2" placeholder="Reason for leave…"
                class="w-full resize-none rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2.5 text-sm text-[var(--fg)] placeholder:text-[var(--fg-muted)] focus:border-[var(--brand)] focus:outline-none">
              </textarea>
            </div>
          </div>
          {#if leaveError}<p class="mt-2 text-xs text-red-500">{leaveError}</p>{/if}
          <div class="mt-4 flex gap-2">
            <button onclick={() => $leaveMut.mutate({ staffId: staffId(), req: leaveForm })}
              disabled={$leaveMut.isPending}
              class="rounded-xl px-4 py-2 text-sm font-semibold text-white transition hover:opacity-90 disabled:opacity-50"
              style="background-color: var(--brand)">
              {$leaveMut.isPending ? 'Submitting…' : 'Submit leave request'}
            </button>
            <button onclick={() => { showLeaveForm = false; leaveError = ''; }}
              class="rounded-xl border border-[var(--border)] px-4 py-2 text-sm font-medium text-[var(--fg-muted)] transition hover:bg-[var(--bg)]">
              Cancel
            </button>
          </div>
        </div>
      {/if}

      {#if $leaveQuery.isPending}
        <div class="space-y-2">
          {#each [1,2,3] as _}
            <div class="h-14 animate-pulse rounded-xl bg-[var(--card)]"></div>
          {/each}
        </div>
      {:else if ($leaveQuery.data ?? []).length === 0}
        <div class="rounded-2xl border border-dashed border-[var(--border)] p-10 text-center">
          <p class="text-sm text-[var(--fg-muted)]">No leave requests on record.</p>
        </div>
      {:else}
        <div class="overflow-hidden rounded-2xl border border-[var(--border)] bg-[var(--card)]">
          <table class="w-full text-sm">
            <thead>
              <tr class="border-b border-[var(--border)] text-left">
                <th class="px-5 py-3 text-xs font-semibold uppercase tracking-widest text-[var(--fg-muted)]">Type</th>
                <th class="hidden px-5 py-3 text-xs font-semibold uppercase tracking-widest text-[var(--fg-muted)] sm:table-cell">Dates</th>
                <th class="px-5 py-3 text-xs font-semibold uppercase tracking-widest text-[var(--fg-muted)]">Days</th>
                <th class="px-5 py-3 text-xs font-semibold uppercase tracking-widest text-[var(--fg-muted)]">Status</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-[var(--border)]">
              {#each ($leaveQuery.data ?? []) as l (l.id)}
                <tr class="transition hover:bg-[var(--bg)]">
                  <td class="px-5 py-3.5 font-medium text-[var(--fg)]">{l.leave_type}</td>
                  <td class="hidden px-5 py-3.5 text-[var(--fg-muted)] sm:table-cell">
                    {fmtDate(l.start_date)} – {fmtDate(l.end_date)}
                  </td>
                  <td class="px-5 py-3.5 text-[var(--fg-muted)]">{l.days_count}</td>
                  <td class="px-5 py-3.5">
                    <span class="rounded-full px-2 py-0.5 text-[10px] font-semibold {STATUS_STYLE[l.status] ?? ''}">
                      {l.status}
                    </span>
                  </td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
      {/if}
    </div>
  {/if}
{/if}
