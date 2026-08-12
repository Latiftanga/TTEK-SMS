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

  // Starts open if a filter is already active (e.g. a bookmarked/shared
  // filtered URL) so the active selection is never hidden from view — but
  // only reads hasFilters once at mount, not reactively, so the user can
  // still collapse the panel afterwards without it snapping back open on
  // every filter change.
  let filtersOpen = $state(hasFilters);

  const selClass = 'w-full sm:w-auto min-w-[7rem] rounded-xl border border-[var(--border)] bg-[var(--card)] px-3 py-2 text-sm text-[var(--fg)] focus:border-[var(--brand)] focus:outline-none transition';
</script>

<div class="mb-4 space-y-2">
  <!-- Search + filter icon + live count — one compact row -->
  <div class="flex items-center gap-2">
    <div class="relative min-w-0 flex-1">
      <svg class="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--fg-muted)]"
           fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 15.803a7.5 7.5 0 0010.607 10.607z"/>
      </svg>
      <input value={searchInput} oninput={(e) => onSearchInput(e.currentTarget.value)} placeholder="Search name or admission no…"
        class="w-full rounded-xl border border-[var(--border)] bg-[var(--card)] py-2 pl-9 pr-4
               text-sm text-[var(--fg)] placeholder:text-[var(--fg-muted)]
               focus:border-[var(--brand)] focus:outline-none transition" />
    </div>

    <button onclick={() => filtersOpen = !filtersOpen} aria-label="Filters" aria-expanded={filtersOpen}
      class="relative flex h-11 w-11 shrink-0 items-center justify-center rounded-xl border border-[var(--border)]
             bg-[var(--card)] text-[var(--fg-muted)] transition hover:bg-[var(--hover)]
             {filtersOpen ? 'border-[var(--brand)] text-[var(--brand)]' : ''}">
      <svg class="h-4.5 w-4.5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" d="M12 3c2.755 0 5.455.232 8.083.678.533.09.917.556.917 1.096v1.044a2.25 2.25 0 01-.659 1.591l-5.432 5.432a2.25 2.25 0 00-.659 1.591v2.927a2.25 2.25 0 01-1.244 2.013L9.75 21v-6.568a2.25 2.25 0 00-.659-1.591L3.659 7.409A2.25 2.25 0 013 5.818V4.774c0-.54.384-1.006.917-1.096A48.32 48.32 0 0112 3z"/>
      </svg>
      {#if hasFilters}<span class="absolute right-1.5 top-1.5 h-1.5 w-1.5 rounded-full bg-[var(--brand)]"></span>{/if}
    </button>

    {#if !isPending}
      <span class="shrink-0 rounded-lg border border-[var(--border)] bg-[var(--hover)] px-2.5 py-2 text-xs font-semibold tabular-nums text-[var(--fg-muted)]">
        {total}
      </span>
    {/if}
  </div>

  {#if filtersOpen}
    <div class="grid grid-cols-2 gap-2 sm:flex sm:flex-wrap sm:items-center">
      <select value={yearKey} onchange={(e) => setFilter('year', e.currentTarget.value)} class={selClass}>
        <option value="">All years</option>
        {#each yearOptions as opt}<option value={opt.key}>{opt.label}</option>{/each}
      </select>

      <select value={classId} onchange={(e) => setFilter('class', e.currentTarget.value)} class={selClass}>
        <option value="">{yearKey ? 'All streams' : 'All classes'}</option>
        {#each filteredClasses as c}<option value={c.id}>{c.display_name}</option>{/each}
      </select>

      <div class="col-span-2 flex gap-1 rounded-xl border border-[var(--border)] bg-[var(--card)] p-1 sm:col-span-1">
        {#each [['', 'All'], ['MALE', 'Boys'], ['FEMALE', 'Girls']] as [val, label]}
          <button onclick={() => setFilter('gender', val === gender ? '' : val as string)}
            class="flex-1 rounded-lg px-3 py-1 text-xs font-semibold transition sm:flex-initial
                   {gender === val ? 'bg-[var(--brand)] text-white' : 'text-[var(--fg-muted)] hover:bg-[var(--hover)]'}">
            {label}
          </button>
        {/each}
      </div>

      <label class="col-span-2 flex cursor-pointer items-center gap-2 rounded-xl border border-[var(--border)] bg-[var(--card)] px-3 py-2 text-sm text-[var(--fg-muted)] transition hover:bg-[var(--hover)] sm:col-span-1">
        <input type="checkbox" checked={activeOnly} onchange={(e) => setFilter('active', e.currentTarget.checked ? '' : 'false')} class="accent-[var(--brand)]" />
        Active only
      </label>

      <button onclick={onToggleGraduated}
        class="col-span-2 rounded-xl border border-[var(--border)] px-3 py-2 text-xs font-semibold transition sm:col-span-1
               {graduated ? 'bg-[var(--brand)] text-white' : 'bg-[var(--card)] text-[var(--fg-muted)] hover:bg-[var(--hover)]'}">
        Graduated
      </button>

      {#if hasFilters}
        <button onclick={onClearFilters}
          class="col-span-2 text-left text-xs text-[var(--fg-muted)] underline hover:text-[var(--fg)] transition sm:col-span-1 sm:text-center">
          Clear filters
        </button>
      {/if}
    </div>
  {/if}
</div>
