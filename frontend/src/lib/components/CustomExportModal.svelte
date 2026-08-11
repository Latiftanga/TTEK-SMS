<script lang="ts">
  import { portal } from '$lib/actions/portal';
  import { toast } from '$lib/stores/toast';

  type EntityType = 'students' | 'staff';
  type Fmt = 'csv' | 'excel' | 'pdf';
  const FMT_LABEL: Record<Fmt, string> = { excel: 'Excel', csv: 'CSV', pdf: 'PDF' };

  interface FieldDef  { key: string; label: string; }
  interface FieldGroup { heading: string; fields: FieldDef[]; }

  interface Props {
    entityType: EntityType;
    filterParams: Record<string, string | number | boolean | undefined>;
    onClose: () => void;
  }
  const { entityType, filterParams, onClose }: Props = $props();

  // ── Field group definitions ───────────────────────────────────────────────

  const STUDENT_GROUPS: FieldGroup[] = [
    { heading: 'Basic Info', fields: [
      { key: 'admission_number', label: 'Admission No.' },
      { key: 'full_name',        label: 'Full Name'     },
      { key: 'first_name',       label: 'First Name'    },
      { key: 'last_name',        label: 'Last Name'     },
      { key: 'middle_name',      label: 'Middle Name'   },
      { key: 'gender',           label: 'Gender'        },
      { key: 'date_of_birth',    label: 'Date of Birth' },
      { key: 'status',           label: 'Status'        },
    ]},
    { heading: 'Academic', fields: [
      { key: 'current_class', label: 'Current Class' },
      { key: 'level',         label: 'Level'         },
      { key: 'boarding',      label: 'Boarding'      },
    ]},
    { heading: 'Welfare', fields: [
      { key: 'nationality',       label: 'Nationality'    },
      { key: 'religion',          label: 'Religion'       },
      { key: 'hometown',          label: 'Hometown'       },
      { key: 'nhis_number',       label: 'NHIS No.'       },
      { key: 'ghana_card_number', label: 'Ghana Card No.' },
      { key: 'orphan_status',     label: 'Orphan Status'  },
      { key: 'disability',        label: 'Disability'     },
    ]},
    { heading: 'Contact', fields: [
      { key: 'guardian_name',  label: 'Guardian Name'  },
      { key: 'guardian_phone', label: 'Guardian Phone' },
    ]},
  ];

  const STAFF_GROUPS: FieldGroup[] = [
    { heading: 'Basic Info', fields: [
      { key: 'staff_number',  label: 'Staff No.'      },
      { key: 'full_name',     label: 'Full Name'      },
      { key: 'first_name',    label: 'First Name'     },
      { key: 'last_name',     label: 'Last Name'      },
      { key: 'gender',        label: 'Gender'         },
      { key: 'date_of_birth', label: 'Date of Birth'  },
      { key: 'status',        label: 'Status'         },
    ]},
    { heading: 'Employment', fields: [
      { key: 'category',        label: 'Job Class'       },
      { key: 'positions',       label: 'Position(s)'     },
      { key: 'employment_type', label: 'Employment Type' },
      { key: 'joined_date',     label: 'Date Joined'     },
      { key: 'current_rank',    label: 'Current Rank'    },
    ]},
    { heading: 'Government IDs', fields: [
      { key: 'ssnit_number', label: 'SSNIT No.'      },
      { key: 'national_id',  label: 'Ghana Card No.' },
    ]},
    { heading: 'Contact', fields: [
      { key: 'phone', label: 'Phone' },
      { key: 'email', label: 'Email' },
    ]},
  ];

  const DEFAULTS: Record<EntityType, string[]> = {
    students: ['admission_number', 'full_name', 'gender', 'current_class', 'boarding', 'guardian_name', 'guardian_phone'],
    staff:    ['staff_number', 'full_name', 'gender', 'category', 'employment_type', 'ssnit_number', 'national_id', 'joined_date'],
  };

  const LS_KEY = `ttek_export_fields_${entityType}`;
  const groups = entityType === 'students' ? STUDENT_GROUPS : STAFF_GROUPS;

  // Load saved selection or fall back to defaults
  function loadSelection(): Set<string> {
    try {
      const saved = localStorage.getItem(LS_KEY);
      if (saved) return new Set(JSON.parse(saved));
    } catch { /* ignore */ }
    return new Set(DEFAULTS[entityType]);
  }

  let selected = $state<Set<string>>(loadSelection());
  let fmt      = $state<Fmt>('excel');
  let busy     = $state(false);

  function toggle(key: string) {
    const next = new Set(selected);
    next.has(key) ? next.delete(key) : next.add(key);
    selected = next;
  }

  function selectGroup(g: FieldGroup, on: boolean) {
    const next = new Set(selected);
    g.fields.forEach(f => on ? next.add(f.key) : next.delete(f.key));
    selected = next;
  }

  const allKeys = $derived(groups.flatMap(g => g.fields.map(f => f.key)));
  function selectAll(on: boolean) {
    selected = on ? new Set(allKeys) : new Set<string>();
  }

  async function doExport() {
    if (selected.size === 0) { toast.error('Select at least one field.'); return; }
    busy = true;
    try {
      localStorage.setItem(LS_KEY, JSON.stringify([...selected]));
      const fieldsParam = [...selected].join(',');
      const ext = fmt === 'excel' ? 'xlsx' : fmt === 'pdf' ? 'pdf' : 'csv';

      const blob = entityType === 'students'
        ? await (await import('$lib/api/students')).customExportStudents({ ...filterParams as any, fields: fieldsParam, fmt })
        : await (await import('$lib/api/staff')).customExportStaff({ ...filterParams as any, fields: fieldsParam, fmt });

      const url = URL.createObjectURL(blob);
      Object.assign(document.createElement('a'), { href: url, download: `${entityType}.${ext}` }).click();
      URL.revokeObjectURL(url);
      onClose();
    } catch { toast.error('Export failed.'); }
    finally { busy = false; }
  }
</script>

<div use:portal class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
  <div class="flex w-full max-w-lg flex-col rounded-2xl border border-[var(--border)] bg-[var(--card)] shadow-2xl"
       style="max-height: 90vh">

    <!-- Header -->
    <div class="flex shrink-0 items-center justify-between border-b border-[var(--border)] px-6 py-4">
      <div>
        <h2 class="text-base font-semibold text-[var(--fg)]">Custom Export</h2>
        <p class="text-xs text-[var(--fg-muted)]">Choose fields — your selection is remembered.</p>
      </div>
      <button onclick={onClose}
        class="rounded-lg p-1.5 text-[var(--fg-muted)] transition hover:bg-[var(--hover)]">
        <svg class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12"/>
        </svg>
      </button>
    </div>

    <!-- Quick-select bar -->
    <div class="flex shrink-0 items-center gap-3 border-b border-[var(--border)] px-6 py-2.5">
      <span class="text-xs text-[var(--fg-muted)]">{selected.size} of {allKeys.length} fields</span>
      <button onclick={() => selectAll(true)}
        class="text-xs font-medium text-[var(--brand)] transition hover:underline">All</button>
      <button onclick={() => selectAll(false)}
        class="text-xs font-medium text-[var(--fg-muted)] transition hover:underline">None</button>
    </div>

    <!-- Field groups — scrollable -->
    <div class="min-h-0 flex-1 overflow-y-auto px-6 py-4 space-y-5">
      {#each groups as g}
        {@const groupSelected = g.fields.every(f => selected.has(f.key))}
        {@const groupPartial  = !groupSelected && g.fields.some(f => selected.has(f.key))}
        <div>
          <div class="mb-2 flex items-center gap-2">
            <input type="checkbox" checked={groupSelected} indeterminate={groupPartial}
              onchange={(e) => selectGroup(g, (e.target as HTMLInputElement).checked)}
              class="h-3.5 w-3.5 rounded border-[var(--border)] accent-[var(--brand)]" />
            <span class="text-xs font-semibold uppercase tracking-wider text-[var(--fg-muted)]">{g.heading}</span>
          </div>
          <div class="grid grid-cols-2 gap-x-6 gap-y-1.5 sm:grid-cols-3">
            {#each g.fields as f}
              <label class="flex cursor-pointer items-center gap-2 text-sm text-[var(--fg)]">
                <input type="checkbox" checked={selected.has(f.key)}
                  onchange={() => toggle(f.key)}
                  class="h-3.5 w-3.5 rounded border-[var(--border)] accent-[var(--brand)]" />
                {f.label}
              </label>
            {/each}
          </div>
        </div>
      {/each}
    </div>

    <!-- Footer -->
    <div class="flex shrink-0 items-center justify-between gap-4 border-t border-[var(--border)] px-6 py-4">
      <!-- Format toggle -->
      <div class="flex items-center gap-1 rounded-xl border border-[var(--border)] p-0.5">
        {#each (['excel', 'csv', 'pdf'] as Fmt[]) as f}
          <button onclick={() => fmt = f}
            class="rounded-lg px-3 py-1.5 text-xs font-medium transition
                   {fmt === f ? 'bg-[var(--brand)] text-white' : 'text-[var(--fg-muted)] hover:bg-[var(--hover)]'}">
            {FMT_LABEL[f]}
          </button>
        {/each}
      </div>

      <div class="flex gap-2">
        <button onclick={onClose}
          class="rounded-xl border border-[var(--border)] px-4 py-2 text-sm font-medium
                 text-[var(--fg-muted)] transition hover:bg-[var(--hover)]">
          Cancel
        </button>
        <button onclick={doExport} disabled={busy || selected.size === 0}
          class="rounded-xl px-5 py-2 text-sm font-semibold text-white transition
                 hover:opacity-90 disabled:opacity-50"
          style="background: var(--brand)">
          {busy ? 'Exporting…' : `Export ${FMT_LABEL[fmt]}`}
        </button>
      </div>
    </div>
  </div>
</div>
