<script lang="ts">
  interface ClassOption { id: string; display_name: string; level: string; year_group: number }
  interface YearOption { key: string; label: string }

  interface Props {
    searchInput: string;
    onSearchInput: (value: string) => void;
    yearKey: string;
    classId: string;
    gender: 'MALE' | 'FEMALE' | '';
    activeOnly: boolean;
    graduated: boolean;
    yearOptions: YearOption[];
    filteredClasses: ClassOption[];
    total: number;
    isPending: boolean;
    hasFilters: boolean;
    setFilter: (key: string, value: string) => void;
    onToggleGraduated: () => void;
    onClearFilters: () => void;
  }
  const {
    searchInput, onSearchInput, yearKey, classId, gender, activeOnly, graduated,
    yearOptions, filteredClasses, total, isPending, hasFilters, setFilter,
    onToggleGraduated, onClearFilters,
  }: Props = $props();

  const selClass = 'min-w-[7rem] rounded-xl border border-[var(--border)] bg-[var(--card)] px-3 py-2 text-sm text-[var(--fg)] focus:border-[var(--brand)] focus:outline-none transition';
</script>

<div class="mb-4 flex flex-wrap items-center gap-2">
  <div class="relative min-w-48 flex-1">
    <svg class="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--fg-muted)]"
         fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
      <path stroke-linecap="round" stroke-linejoin="round" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 15.803a7.5 7.5 0 0010.607 10.607z"/>
    </svg>
    <input value={searchInput} oninput={(e) => onSearchInput(e.currentTarget.value)} placeholder="Search name or admission no…"
      class="w-full rounded-xl border border-[var(--border)] bg-[var(--card)] py-2 pl-9 pr-4
             text-sm text-[var(--fg)] placeholder:text-[var(--fg-muted)]
             focus:border-[var(--brand)] focus:outline-none transition" />
  </div>

  <select value={yearKey} onchange={(e) => setFilter('year', e.currentTarget.value)} class={selClass}>
    <option value="">All years</option>
    {#each yearOptions as opt}<option value={opt.key}>{opt.label}</option>{/each}
  </select>

  <select value={classId} onchange={(e) => setFilter('class', e.currentTarget.value)} class={selClass}>
    <option value="">{yearKey ? 'All streams' : 'All classes'}</option>
    {#each filteredClasses as c}<option value={c.id}>{c.display_name}</option>{/each}
  </select>

  <div class="flex gap-1 rounded-xl border border-[var(--border)] bg-[var(--card)] p-1">
    {#each [['', 'All'], ['MALE', 'Boys'], ['FEMALE', 'Girls']] as [val, label]}
      <button onclick={() => setFilter('gender', val === gender ? '' : val as string)}
        class="rounded-lg px-3 py-1 text-xs font-semibold transition
               {gender === val ? 'bg-[var(--brand)] text-white' : 'text-[var(--fg-muted)] hover:bg-[var(--hover)]'}">
        {label}
      </button>
    {/each}
  </div>

  <label class="flex cursor-pointer items-center gap-2 rounded-xl border border-[var(--border)] bg-[var(--card)] px-3 py-2 text-sm text-[var(--fg-muted)] hover:bg-[var(--hover)] transition">
    <input type="checkbox" checked={activeOnly} onchange={(e) => setFilter('active', e.currentTarget.checked ? '' : 'false')} class="accent-[var(--brand)]" />
    Active only
  </label>

  <button onclick={onToggleGraduated}
    class="rounded-xl border border-[var(--border)] px-3 py-2 text-xs font-semibold transition
           {graduated ? 'bg-[var(--brand)] text-white' : 'bg-[var(--card)] text-[var(--fg-muted)] hover:bg-[var(--hover)]'}">
    Graduated
  </button>

  <!-- Result count — live, near filters so users see impact immediately -->
  {#if !isPending}
    <span class="rounded-lg border border-[var(--border)] bg-[var(--hover)] px-2.5 py-1.5 text-xs font-semibold tabular-nums text-[var(--fg-muted)]">
      {total} student{total !== 1 ? 's' : ''}
    </span>
  {/if}

  {#if hasFilters}
    <button onclick={onClearFilters} class="text-xs text-[var(--fg-muted)] underline hover:text-[var(--fg)] transition">
      Clear filters
    </button>
  {/if}
</div>
