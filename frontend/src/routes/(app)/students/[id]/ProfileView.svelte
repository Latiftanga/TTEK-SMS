<script lang="ts">
  import type { StudentDetail } from '$lib/api/students';

  interface HouseRoom { id: string; room_number: string; }
  interface House     { name: string; rooms: HouseRoom[]; }

  interface Props {
    student:          StudentDetail;
    assignment:       { house_id: string; room_id: string | null; vacated_at: string | null } | null | undefined;
    assignmentPending: boolean;
    houseMap:         Map<string, House>;
  }
  const { student, assignment, assignmentPending, houseMap }: Props = $props();

  function orphanLabel(v: string | null | undefined) {
    if (v === 'HALF_ORPHAN') return 'Half orphan';
    if (v === 'FULL_ORPHAN') return 'Full orphan';
    return 'None';
  }
</script>

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
          {#if assignmentPending}
            <span class="text-[var(--fg-muted)]">Loading…</span>
          {:else if assignment && !assignment.vacated_at}
            {@const h = houseMap.get(assignment.house_id)}
            {@const r = h?.rooms.find(rm => rm.id === assignment.room_id)}
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
