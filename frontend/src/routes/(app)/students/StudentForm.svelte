<script lang="ts">
  import { createMutation, createQuery, useQueryClient } from '@tanstack/svelte-query';
  import { goto } from '$app/navigation';
  import { createStudent, assignStudentToClass, type StudentCreate, type Gender, type OrphanStatus } from '$lib/api/students';
  import { listClasses, listYears } from '$lib/api/academic';
  import { listHouses, createAssignment } from '$lib/api/housing';
  import { portal } from '$lib/actions/portal';

  interface Props { open: boolean; onClose: () => void; }
  const { open, onClose }: Props = $props();

  const qc = useQueryClient();

  // ── Reference data ────────────────────────────────────────────────────────────
  const classesQ = createQuery({ queryKey: ['classes'], queryFn: listClasses, staleTime: 5 * 60_000 });
  const yearsQ   = createQuery({ queryKey: ['years'],   queryFn: listYears,   staleTime: 5 * 60_000 });
  const housesQ  = createQuery({ queryKey: ['houses'],  queryFn: listHouses,  staleTime: 5 * 60_000 });

  // Current academic year — used silently when a class is chosen
  const currentYearId = $derived(
    ($yearsQ.data ?? []).find(y => y.is_current)?.id
    ?? ($yearsQ.data ?? []).sort((a, b) => b.start_date.localeCompare(a.start_date))[0]?.id
  );

  // ── Form state ────────────────────────────────────────────────────────────────
  const blankStudent = (): StudentCreate => ({
    admission_number: '', first_name: '', middle_name: '', last_name: '',
    date_of_birth: '', gender: undefined, nationality: 'Ghanaian',
    religion: '', hometown: '', residential_address: '',
    nhis_number: '', ghana_card_number: '',
    is_boarding: false, orphan_status: 'NONE', disability: '',
  });

  let form    = $state(blankStudent());
  let classId = $state('');
  let houseId = $state('');
  let roomId  = $state('');
  let error   = $state('');

  const pickedHouseRooms = $derived(
    houseId ? (($housesQ.data ?? []).find(h => h.id === houseId)?.rooms ?? []) : []
  );
  $effect(() => { if (houseId) roomId = ''; });

  const GENDERS: { value: Gender; label: string }[] = [
    { value: 'MALE', label: 'Male' }, { value: 'FEMALE', label: 'Female' },
  ];
  const ORPHAN_STATUSES: { value: OrphanStatus; label: string }[] = [
    { value: 'NONE', label: 'None' },
    { value: 'HALF_ORPHAN', label: 'Half orphan' },
    { value: 'FULL_ORPHAN', label: 'Full orphan' },
  ];

  const INPUT = 'w-full rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--fg)] placeholder:text-[var(--fg-subtle)] focus:border-[var(--brand)] focus:outline-none transition';
  const LABEL = 'mb-1 block text-xs font-medium text-[var(--fg-muted)]';

  // ── Mutations ─────────────────────────────────────────────────────────────────
  const mut = createMutation({
    mutationFn: createStudent,
    onSuccess: async (s) => {
      if (classId && currentYearId) {
        try {
          await assignStudentToClass({ student_id: s.id, class_id: classId, academic_year_id: currentYearId });
        } catch { /* non-fatal */ }
      }
      if (form.is_boarding && houseId && currentYearId) {
        try {
          await createAssignment({
            student_id: s.id, house_id: houseId, room_id: roomId || null,
            academic_year_id: currentYearId, assigned_at: new Date().toISOString().slice(0, 10),
          });
        } catch { /* non-fatal */ }
      }
      qc.invalidateQueries({ queryKey: ['students'] });
      onClose();
      reset();
      goto(`/students/${s.id}`);
    },
    onError: (e: unknown) => {
      error = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? 'Could not save student.';
    },
  });

  function reset() {
    form = blankStudent(); classId = ''; houseId = ''; roomId = ''; error = '';
  }
  function close() { onClose(); reset(); }
  function onKeydown(e: KeyboardEvent) { if (e.key === 'Escape') close(); }

  function handleSubmit() {
    error = '';
    if (!form.admission_number.trim()) { error = 'Admission number is required.'; return; }
    if (!form.first_name.trim())       { error = 'First name is required.'; return; }
    if (!form.last_name.trim())        { error = 'Last name is required.'; return; }
    $mut.mutate({
      ...form,
      middle_name:         form.middle_name?.trim()         || undefined,
      date_of_birth:       form.date_of_birth?.trim()       || undefined,
      nationality:         form.nationality?.trim()         || undefined,
      religion:            form.religion?.trim()            || undefined,
      hometown:            form.hometown?.trim()            || undefined,
      residential_address: form.residential_address?.trim() || undefined,
      nhis_number:         form.nhis_number?.trim()         || undefined,
      ghana_card_number:   form.ghana_card_number?.trim()   || undefined,
      disability:          form.disability?.trim()          || undefined,
    });
  }
</script>

<svelte:window onkeydown={onKeydown} />

<div use:portal>
  {#if open}
    <div class="fixed inset-0 z-50 bg-black/30 backdrop-blur-sm"
         onclick={close} role="presentation" aria-hidden="true"></div>
  {/if}

  <div class="fixed inset-y-0 right-0 z-[60] flex w-full max-w-md flex-col border-l border-[var(--border)] bg-[var(--card)] shadow-2xl transition-transform duration-300"
       class:translate-x-full={!open}>

    <!-- Header -->
    <div class="flex shrink-0 items-center justify-between border-b border-[var(--border)] px-6 py-4">
      <div>
        <h2 class="text-base font-semibold text-[var(--fg)]">Add student</h2>
        <p class="mt-0.5 text-xs text-[var(--fg-muted)]">Required fields only — more can be added from the profile.</p>
      </div>
      <button onclick={close} class="rounded-xl p-2 text-[var(--fg-muted)] hover:bg-[var(--hover)] transition" aria-label="Close">
        <svg class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12"/>
        </svg>
      </button>
    </div>

    <!-- Body -->
    <div class="flex-1 overflow-y-auto px-6 py-5 space-y-6">

      <!-- Admission number — standalone, prominent -->
      <div>
        <label for="sf-admission" class={LABEL}>Admission number <span class="text-red-500">*</span></label>
        <input id="sf-admission" bind:value={form.admission_number}
          placeholder="e.g. PRESEC/2024/001" class={INPUT} />
      </div>

      <!-- ── Personal details ────────────────────────────────────────── -->
      <section>
        <p class="mb-3 text-[10px] font-semibold uppercase tracking-widest text-[var(--fg-subtle)]">Personal details</p>
        <div class="space-y-3">
          <div class="grid grid-cols-2 gap-3">
            <div>
              <label for="sf-first" class={LABEL}>First name <span class="text-red-500">*</span></label>
              <input id="sf-first" bind:value={form.first_name} placeholder="Kwame" class={INPUT} />
            </div>
            <div>
              <label for="sf-last" class={LABEL}>Last name <span class="text-red-500">*</span></label>
              <input id="sf-last" bind:value={form.last_name} placeholder="Mensah" class={INPUT} />
            </div>
          </div>
          <div>
            <label for="sf-middle" class={LABEL}>Middle name</label>
            <input id="sf-middle" bind:value={form.middle_name} placeholder="Optional" class={INPUT} />
          </div>
          <div class="grid grid-cols-2 gap-3">
            <div>
              <label for="sf-dob" class={LABEL}>Date of birth</label>
              <input id="sf-dob" type="date" bind:value={form.date_of_birth} class={INPUT} />
            </div>
            <div>
              <label for="sf-gender" class={LABEL}>Gender</label>
              <select id="sf-gender" bind:value={form.gender} class={INPUT}>
                <option value={undefined}>Select</option>
                {#each GENDERS as g}<option value={g.value}>{g.label}</option>{/each}
              </select>
            </div>
            <div>
              <label for="sf-nationality" class={LABEL}>Nationality</label>
              <input id="sf-nationality" bind:value={form.nationality} placeholder="Ghanaian" class={INPUT} />
            </div>
            <div>
              <label for="sf-religion" class={LABEL}>Religion</label>
              <input id="sf-religion" bind:value={form.religion} placeholder="Optional" class={INPUT} />
            </div>
          </div>
          <div>
            <label for="sf-hometown" class={LABEL}>Hometown</label>
            <input id="sf-hometown" bind:value={form.hometown} placeholder="e.g. Kumasi" class={INPUT} />
          </div>
          <div>
            <label for="sf-address" class={LABEL}>Residential address</label>
            <input id="sf-address" bind:value={form.residential_address} placeholder="Optional" class={INPUT} />
          </div>
        </div>
      </section>

      <!-- ── Health & welfare ───────────────────────────────────────── -->
      <section>
        <p class="mb-3 text-[10px] font-semibold uppercase tracking-widest text-[var(--fg-subtle)]">Health & welfare</p>
        <div class="space-y-3">
          <div class="grid grid-cols-2 gap-3">
            <div>
              <label for="sf-nhis" class={LABEL}>NHIS number</label>
              <input id="sf-nhis" bind:value={form.nhis_number} placeholder="Optional" class={INPUT} />
            </div>
            <div>
              <label for="sf-card" class={LABEL}>Ghana Card no.</label>
              <input id="sf-card" bind:value={form.ghana_card_number} placeholder="Optional" class={INPUT} />
            </div>
          </div>
          <div>
            <label for="sf-orphan" class={LABEL}>Orphan status</label>
            <select id="sf-orphan" bind:value={form.orphan_status} class={INPUT}>
              {#each ORPHAN_STATUSES as o}<option value={o.value}>{o.label}</option>{/each}
            </select>
          </div>
          <div>
            <label for="sf-disability" class={LABEL}>Disability / special needs</label>
            <input id="sf-disability" bind:value={form.disability} placeholder="Describe if any (optional)" class={INPUT} />
          </div>
        </div>
      </section>

      <!-- ── Enrolment & boarding ──────────────────────────────────── -->
      <section>
        <p class="mb-3 text-[10px] font-semibold uppercase tracking-widest text-[var(--fg-subtle)]">Enrolment & boarding</p>
        <div class="space-y-3">
          <div>
            <label for="sf-class" class={LABEL}>Class <span class="font-normal text-[var(--fg-subtle)]">(optional)</span></label>
            <select id="sf-class" bind:value={classId} class={INPUT}>
              <option value="">Not yet assigned</option>
              {#each $classesQ.data ?? [] as c}<option value={c.id}>{c.display_name}</option>{/each}
            </select>
            {#if classId}
              <p class="mt-1 text-[10px] text-[var(--fg-subtle)]">
                Student will be enrolled in this class for the current academic year. The class teacher registers them for each term.
              </p>
            {/if}
          </div>
          <label class="flex cursor-pointer items-center gap-3 rounded-xl border border-[var(--border)] px-4 py-3 transition hover:bg-[var(--hover)]">
            <input type="checkbox" id="sf-boarding" bind:checked={form.is_boarding} class="accent-[var(--brand)] h-4 w-4 shrink-0" />
            <div>
              <p class="text-sm font-medium text-[var(--fg)]">Boarding student</p>
              <p class="text-xs text-[var(--fg-muted)]">Student lives in a school house</p>
            </div>
          </label>

          {#if form.is_boarding}
            <div>
              <label for="sf-house" class={LABEL}>House</label>
              {#if $housesQ.isPending}
                <div class="h-10 animate-pulse rounded-xl bg-[var(--hover)]"></div>
              {:else if ($housesQ.data ?? []).length === 0}
                <p class="rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-700 dark:border-amber-900 dark:bg-amber-950/30 dark:text-amber-400">
                  No houses configured yet. Add houses under Housing settings.
                </p>
              {:else}
                <select id="sf-house" bind:value={houseId} class={INPUT}>
                  <option value="">Select house</option>
                  {#each $housesQ.data ?? [] as h}<option value={h.id}>{h.name}</option>{/each}
                </select>
              {/if}
            </div>
            {#if houseId && pickedHouseRooms.length > 0}
              <div>
                <label for="sf-room" class={LABEL}>Room <span class="font-normal text-[var(--fg-subtle)]">(optional)</span></label>
                <select id="sf-room" bind:value={roomId} class={INPUT}>
                  <option value="">No room</option>
                  {#each pickedHouseRooms as r}<option value={r.id}>Room {r.room_number}</option>{/each}
                </select>
              </div>
            {/if}
          {/if}
        </div>
      </section>

      {#if error}
        <p class="rounded-xl bg-red-50 px-4 py-3 text-sm text-red-600 dark:bg-red-950/30 dark:text-red-400">{error}</p>
      {/if}
    </div>

    <!-- Footer -->
    <div class="shrink-0 border-t border-[var(--border)] px-6 py-4">
      <button onclick={handleSubmit} disabled={$mut.isPending}
        class="w-full rounded-xl py-2.5 text-sm font-semibold text-white transition hover:opacity-90 disabled:opacity-60"
        style="background: var(--brand)">
        {$mut.isPending ? 'Saving…' : 'Add student & open profile'}
      </button>
      <button onclick={close}
        class="mt-2 w-full rounded-xl border border-[var(--border)] py-2.5 text-sm font-medium text-[var(--fg-muted)] transition hover:bg-[var(--hover)]">
        Cancel
      </button>
    </div>
  </div>
</div>
