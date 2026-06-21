<script lang="ts">
  import { createQuery, createMutation, useQueryClient } from '@tanstack/svelte-query';
  import { updateStudent, type StudentDetail, type Gender, type OrphanStatus } from '$lib/api/students';
  import { listYears } from '$lib/api/academic';
  import {
    listHouses, getStudentAssignment, createAssignment, vacateAssignment,
  } from '$lib/api/housing';
  import { toast } from '$lib/stores/toast';

  interface Props { student: StudentDetail; studentId: string; }
  const { student, studentId }: Props = $props();

  const qc = useQueryClient();
  let editing      = $state(false);
  let form         = $state({ ...student });
  let editHouseId  = $state('');
  let editRoomId   = $state('');
  let error        = $state('');

  // ── Housing queries (enabled for boarding students / edit mode) ───────────────
  const yearsQ = createQuery({
    queryKey: ['academic-years'],
    queryFn: listYears,
    staleTime: 5 * 60_000,
    enabled: () => student.is_boarding || form.is_boarding,
  });
  const currentYearId = $derived(($yearsQ.data ?? []).find(y => y.is_current)?.id ?? '');

  const housesQ = createQuery({
    queryKey: ['houses'],
    queryFn: listHouses,
    staleTime: 5 * 60_000,
    enabled: () => student.is_boarding || form.is_boarding,
  });
  const houseMap = $derived(new Map(($housesQ.data ?? []).map(h => [h.id, h])));

  const assignmentQ = createQuery({
    queryKey: () => ['student-assignment', studentId, currentYearId],
    queryFn: () => getStudentAssignment(studentId, currentYearId),
    enabled: () => !!currentYearId && student.is_boarding,
    staleTime: 60_000,
  });

  // ── Mutations ─────────────────────────────────────────────────────────────────
  const mut = createMutation({
    mutationFn: (data: Partial<StudentDetail>) => updateStudent(studentId, data),
    onError: (e: unknown) => {
      error = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? 'Could not save.';
    },
  });

  function startEdit() {
    form = { ...student };
    editHouseId = ($assignmentQ.data && !$assignmentQ.data.vacated_at)
      ? $assignmentQ.data.house_id : '';
    editRoomId = ($assignmentQ.data && !$assignmentQ.data.vacated_at)
      ? ($assignmentQ.data.room_id ?? '') : '';
    editing = true;
    error = '';
  }
  function cancel() { editing = false; error = ''; }

  async function save() {
    error = '';
    if (!form.first_name?.trim()) { error = 'First name is required.'; return; }
    if (!form.last_name?.trim())  { error = 'Last name is required.'; return; }

    try {
      await $mut.mutateAsync({
        first_name:          form.first_name?.trim(),
        middle_name:         form.middle_name?.trim()         || null,
        last_name:           form.last_name?.trim(),
        date_of_birth:       form.date_of_birth               || null,
        gender:              form.gender,
        nationality:         form.nationality?.trim()         || null,
        religion:            form.religion?.trim()            || null,
        hometown:            form.hometown?.trim()            || null,
        residential_address: form.residential_address?.trim() || null,
        nhis_number:         form.nhis_number?.trim()         || null,
        ghana_card_number:   form.ghana_card_number?.trim()   || null,
        orphan_status:       form.orphan_status,
        is_boarding:         form.is_boarding,
        disability:          form.disability?.trim()          || null,
      });
    } catch { return; }

    // Housing assignment — update if house changed
    if (form.is_boarding && editHouseId && currentYearId) {
      const current = $assignmentQ.data;
      const changed = !current || current.vacated_at
        || current.house_id !== editHouseId
        || (current.room_id ?? '') !== editRoomId;
      if (changed) {
        try {
          if (current && !current.vacated_at)
            await vacateAssignment(current.id, new Date().toISOString().slice(0, 10));
          await createAssignment({
            student_id: studentId, house_id: editHouseId,
            room_id: editRoomId || null,
            academic_year_id: currentYearId,
            assigned_at: new Date().toISOString().slice(0, 10),
          });
        } catch { /* non-fatal */ }
        qc.invalidateQueries({ queryKey: ['student-assignment', studentId] });
      }
    }

    qc.invalidateQueries({ queryKey: ['student', studentId] });
    editing = false;
    toast.success('Profile updated.');
  }

  const GENDERS: { value: Gender; label: string }[] = [{ value: 'MALE', label: 'Male' }, { value: 'FEMALE', label: 'Female' }];
  const ORPHAN_STATUSES: { value: OrphanStatus; label: string }[] = [
    { value: 'NONE', label: 'None' }, { value: 'HALF_ORPHAN', label: 'Half orphan' }, { value: 'FULL_ORPHAN', label: 'Full orphan' },
  ];
  function orphanLabel(v: string | null | undefined) {
    if (v === 'HALF_ORPHAN') return 'Half orphan';
    if (v === 'FULL_ORPHAN') return 'Full orphan';
    return 'None';
  }
</script>

<div class="space-y-4">
  <div class="flex items-center justify-between">
    <p class="text-sm font-semibold text-[var(--fg)]">Profile</p>
    {#if !editing}
      <button onclick={startEdit}
        class="flex items-center gap-1.5 rounded-xl border border-[var(--border)] px-3 py-1.5 text-xs font-medium text-[var(--fg-muted)] transition hover:bg-[var(--hover)]">
        <svg class="h-3.5 w-3.5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" d="M16.862 4.487l1.687-1.688a1.875 1.875 0 112.652 2.652L10.582 16.07a4.5 4.5 0 01-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 011.13-1.897l8.932-8.931zm0 0L19.5 7.125"/>
        </svg>
        Edit
      </button>
    {/if}
  </div>

  {#if editing}
    <div class="rounded-2xl border border-[var(--border)] bg-[var(--card)] p-5 space-y-5">

      <section>
        <p class="mb-3 text-[10px] font-semibold uppercase tracking-widest text-[var(--fg-subtle)]">Personal details</p>
        <div class="grid gap-3 sm:grid-cols-2">
          <div><label for="pt-first" class="label">First name <span class="text-red-500">*</span></label><input id="pt-first" bind:value={form.first_name} class="input" /></div>
          <div><label for="pt-last" class="label">Last name <span class="text-red-500">*</span></label><input id="pt-last" bind:value={form.last_name} class="input" /></div>
          <div class="sm:col-span-2"><label for="pt-middle" class="label">Middle name</label><input id="pt-middle" bind:value={form.middle_name} class="input" /></div>
          <div><label for="pt-dob" class="label">Date of birth</label><input id="pt-dob" type="date" bind:value={form.date_of_birth} class="input" /></div>
          <div>
            <label for="pt-gender" class="label">Gender</label>
            <select id="pt-gender" bind:value={form.gender} class="input">
              <option value={null}>Not specified</option>
              {#each GENDERS as g}<option value={g.value}>{g.label}</option>{/each}
            </select>
          </div>
          <div><label for="pt-nationality" class="label">Nationality</label><input id="pt-nationality" bind:value={form.nationality} placeholder="Ghanaian" class="input" /></div>
          <div><label for="pt-religion" class="label">Religion</label><input id="pt-religion" bind:value={form.religion} class="input" /></div>
          <div><label for="pt-hometown" class="label">Hometown</label><input id="pt-hometown" bind:value={form.hometown} class="input" /></div>
          <div class="sm:col-span-2"><label for="pt-address" class="label">Residential address</label><input id="pt-address" bind:value={form.residential_address} class="input" /></div>
        </div>
      </section>

      <hr class="border-[var(--border)]" />

      <section>
        <p class="mb-3 text-[10px] font-semibold uppercase tracking-widest text-[var(--fg-subtle)]">Health & welfare</p>
        <div class="grid gap-3 sm:grid-cols-2">
          <div><label for="pt-nhis" class="label">NHIS number</label><input id="pt-nhis" bind:value={form.nhis_number} placeholder="Optional" class="input" /></div>
          <div><label for="pt-card" class="label">Ghana Card no.</label><input id="pt-card" bind:value={form.ghana_card_number} placeholder="Optional" class="input" /></div>
          <div>
            <label for="pt-orphan" class="label">Orphan status</label>
            <select id="pt-orphan" bind:value={form.orphan_status} class="input">
              {#each ORPHAN_STATUSES as o}<option value={o.value}>{o.label}</option>{/each}
            </select>
          </div>
          <div class="sm:col-span-2"><label for="pt-disability" class="label">Disability / special needs</label><input id="pt-disability" bind:value={form.disability} placeholder="Describe if any" class="input" /></div>
          <div class="sm:col-span-2 flex items-center gap-3">
            <input type="checkbox" id="pt-boarding" bind:checked={form.is_boarding} class="accent-[var(--brand)] h-4 w-4 shrink-0" />
            <label for="pt-boarding" class="text-sm text-[var(--fg)]">Boarding student</label>
          </div>
          {#if form.is_boarding}
            <div>
              <label for="pt-house" class="label">House</label>
              {#if ($housesQ.data ?? []).length === 0}
                <p class="text-xs text-amber-600 dark:text-amber-400">No houses configured — add them in Setup → Housing.</p>
              {:else}
                <select id="pt-house" bind:value={editHouseId} class="input">
                  <option value="">Select house</option>
                  {#each $housesQ.data ?? [] as h}<option value={h.id}>{h.name}</option>{/each}
                </select>
              {/if}
            </div>
            {#if editHouseId}
              {@const rooms = houseMap.get(editHouseId)?.rooms ?? []}
              {#if rooms.length > 0}
                <div>
                  <label for="pt-room" class="label">Room <span class="font-normal text-[var(--fg-subtle)]">(optional)</span></label>
                  <select id="pt-room" bind:value={editRoomId} class="input">
                    <option value="">No room</option>
                    {#each rooms as r}<option value={r.id}>Room {r.room_number}</option>{/each}
                  </select>
                </div>
              {/if}
            {/if}
          {/if}
        </div>
      </section>

      {#if error}<p class="text-xs text-red-500">{error}</p>{/if}
      <div class="flex gap-2">
        <button onclick={save} disabled={$mut.isPending} class="btn-primary">{$mut.isPending ? 'Saving…' : 'Save changes'}</button>
        <button onclick={cancel} class="btn-ghost">Cancel</button>
      </div>
    </div>

  {:else}
    <div class="rounded-2xl border border-[var(--border)] bg-[var(--card)] p-5">
      <p class="mb-3 text-[10px] font-semibold uppercase tracking-widest text-[var(--fg-subtle)]">Personal details</p>
      <dl class="grid gap-x-6 gap-y-3 sm:grid-cols-2">
        {#each [
          { label: 'First name',    val: student.first_name    },
          { label: 'Last name',     val: student.last_name     },
          { label: 'Middle name',   val: student.middle_name   },
          { label: 'Date of birth', val: student.date_of_birth },
          { label: 'Gender',        val: student.gender        },
          { label: 'Nationality',   val: student.nationality   },
          { label: 'Religion',      val: student.religion      },
          { label: 'Hometown',      val: student.hometown      },
        ] as f}
          <div>
            <dt class="text-[10px] font-semibold uppercase tracking-widest text-[var(--fg-subtle)]">{f.label}</dt>
            <dd class="mt-0.5 text-sm text-[var(--fg)]">{f.val ?? '—'}</dd>
          </div>
        {/each}
        <div class="sm:col-span-2">
          <dt class="text-[10px] font-semibold uppercase tracking-widest text-[var(--fg-subtle)]">Address</dt>
          <dd class="mt-0.5 text-sm text-[var(--fg)]">{student.residential_address ?? '—'}</dd>
        </div>
      </dl>
    </div>

    <div class="rounded-2xl border border-[var(--border)] bg-[var(--card)] p-5">
      <p class="mb-3 text-[10px] font-semibold uppercase tracking-widest text-[var(--fg-subtle)]">Health & welfare</p>
      <dl class="grid gap-x-6 gap-y-3 sm:grid-cols-2">
        <div>
          <dt class="text-[10px] font-semibold uppercase tracking-widest text-[var(--fg-subtle)]">NHIS number</dt>
          <dd class="mt-0.5 text-sm font-mono text-[var(--fg)]">{student.nhis_number ?? '—'}</dd>
        </div>
        <div>
          <dt class="text-[10px] font-semibold uppercase tracking-widest text-[var(--fg-subtle)]">Ghana Card</dt>
          <dd class="mt-0.5 text-sm font-mono text-[var(--fg)]">{student.ghana_card_number ?? '—'}</dd>
        </div>
        <div>
          <dt class="text-[10px] font-semibold uppercase tracking-widest text-[var(--fg-subtle)]">Orphan status</dt>
          <dd class="mt-0.5 text-sm text-[var(--fg)]">{orphanLabel(student.orphan_status)}</dd>
        </div>
        <div>
          <dt class="text-[10px] font-semibold uppercase tracking-widest text-[var(--fg-subtle)]">Boarding</dt>
          <dd class="mt-0.5">
            <span class="rounded-full px-2 py-0.5 text-[10px] font-bold
                         {student.is_boarding
                           ? 'bg-amber-50 text-amber-700 ring-1 ring-inset ring-amber-600/20 dark:bg-amber-950/30 dark:text-amber-400'
                           : 'bg-[var(--hover)] text-[var(--fg-muted)]'}">
              {student.is_boarding ? 'Yes — boarding' : 'Day student'}
            </span>
          </dd>
        </div>
        {#if student.is_boarding}
          <div class="sm:col-span-2">
            <dt class="text-[10px] font-semibold uppercase tracking-widest text-[var(--fg-subtle)]">House assignment</dt>
            <dd class="mt-0.5 text-sm text-[var(--fg)]">
              {#if $assignmentQ.isPending}
                <span class="text-[var(--fg-muted)]">Loading…</span>
              {:else if $assignmentQ.data && !$assignmentQ.data.vacated_at}
                {@const h = houseMap.get($assignmentQ.data.house_id)}
                {@const r = h?.rooms.find(rm => rm.id === $assignmentQ.data!.room_id)}
                {h?.name ?? '—'}{r ? ` · Room ${r.room_number}` : ''}
              {:else}
                <span class="text-[var(--fg-muted)]">Not assigned</span>
              {/if}
            </dd>
          </div>
        {/if}
        {#if student.disability}
          <div class="sm:col-span-2">
            <dt class="text-[10px] font-semibold uppercase tracking-widest text-[var(--fg-subtle)]">Disability / special needs</dt>
            <dd class="mt-0.5 text-sm text-[var(--fg)]">{student.disability}</dd>
          </div>
        {/if}
      </dl>
    </div>
  {/if}
</div>

<style>
  @reference "tailwindcss";
  .label { @apply block text-xs font-medium text-[var(--fg-muted)] mb-1; }
  .input  { @apply w-full rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--fg)] placeholder:text-[var(--fg-subtle)] focus:border-[var(--brand)] focus:outline-none transition; }
</style>
