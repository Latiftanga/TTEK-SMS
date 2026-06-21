<script lang="ts">
  import { createMutation, useQueryClient } from '@tanstack/svelte-query';
  import { createClass, type Programme } from '$lib/api/academic';

  const { schoolType, programmes, onClose } = $props<{
    schoolType: string;
    programmes: Programme[];
    onClose: () => void;
  }>();

  const qc = useQueryClient();

  const YEAR_OPTIONS: Record<string, number[]> = {
    Creche:  [1],
    Nursery: [1, 2],
    KG:      [1, 2],
    Basic:   [1, 2, 3, 4, 5, 6, 7, 8, 9],
    SHS:     [1, 2, 3],
  };

  const CLASS_LEVELS = $derived(
    schoolType === 'SHS' ? ['SHS'] : ['Creche', 'Nursery', 'KG', 'Basic']
  );

  let form = $state({ level: schoolType === 'SHS' ? 'SHS' : '', year_group: 1, programme_id: '', stream: '', capacity: '' });
  let formError = $state('');
  const yearOptions = $derived(YEAR_OPTIONS[form.level] ?? [1]);

  const createClassMut = createMutation({
    mutationFn: createClass,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['classes'] });
      form = { level: schoolType === 'SHS' ? 'SHS' : '', year_group: 1, programme_id: '', stream: '', capacity: '' };
      formError = '';
      onClose();
    },
    onError: (e: unknown) => {
      formError = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? 'Failed to create class.';
    },
  });

  function submit() {
    formError = '';
    if (schoolType !== 'SHS' && !form.level) { formError = 'Level is required.'; return; }
    if (schoolType === 'SHS' && !form.programme_id) { formError = 'Programme is required for SHS classes.'; return; }
    $createClassMut.mutate({
      level: form.level,
      year_group: Number(form.year_group),
      programme_id: form.programme_id || undefined,
      stream: form.stream || undefined,
      capacity: form.capacity ? Number(form.capacity) : undefined,
    });
  }
</script>

<div class="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
  <h2 class="mb-4 text-sm font-semibold text-[var(--fg)]">New Class</h2>
  <div class="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
    {#if schoolType !== 'SHS'}
      <div>
        <label class="mb-1 block text-xs font-medium text-[var(--fg-muted)]">Level</label>
        <select bind:value={form.level} onchange={() => { form.year_group = 1; }}
          class="w-full rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--fg)] focus:border-[var(--brand)] focus:outline-none">
          <option value="">Select level…</option>
          {#each CLASS_LEVELS as lvl}<option value={lvl}>{lvl}</option>{/each}
        </select>
      </div>
    {/if}
    <div>
      <label class="mb-1 block text-xs font-medium text-[var(--fg-muted)]">Year</label>
      <select bind:value={form.year_group} disabled={schoolType !== 'SHS' && !form.level}
        class="w-full rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--fg)] focus:border-[var(--brand)] focus:outline-none disabled:opacity-50">
        {#each yearOptions as yr}<option value={yr}>{yr}</option>{/each}
      </select>
    </div>
    {#if schoolType === 'SHS'}
      <div>
        <label class="mb-1 block text-xs font-medium text-[var(--fg-muted)]">Programme</label>
        <select bind:value={form.programme_id}
          class="w-full rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--fg)] focus:border-[var(--brand)] focus:outline-none">
          <option value="">Select programme…</option>
          {#each programmes.filter((p: Programme) => p.is_active) as prog (prog.id)}
            <option value={prog.id}>{prog.name}</option>
          {/each}
        </select>
        {#if programmes.length === 0}
          <p class="mt-1 text-[11px] text-amber-500">No programmes yet — add them in the Programmes tab first.</p>
        {/if}
      </div>
    {/if}
    <div>
      <label class="mb-1 block text-xs font-medium text-[var(--fg-muted)]">Stream (optional)</label>
      <input bind:value={form.stream} placeholder="e.g. A, Gold"
        class="w-full rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--fg)] placeholder:text-[var(--fg-muted)] focus:border-[var(--brand)] focus:outline-none" />
    </div>
    <div>
      <label class="mb-1 block text-xs font-medium text-[var(--fg-muted)]">Capacity (optional)</label>
      <input type="number" bind:value={form.capacity} placeholder="e.g. 40"
        class="w-full rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--fg)] placeholder:text-[var(--fg-muted)] focus:border-[var(--brand)] focus:outline-none" />
    </div>
  </div>
  {#if formError}<p class="mt-2 text-xs text-red-500">{formError}</p>{/if}
  <div class="mt-4 flex gap-2">
    <button onclick={submit} disabled={$createClassMut.isPending} class="btn-primary">
      {$createClassMut.isPending ? 'Creating…' : 'Create class'}
    </button>
    <button onclick={onClose} class="btn-ghost">Cancel</button>
  </div>
</div>
