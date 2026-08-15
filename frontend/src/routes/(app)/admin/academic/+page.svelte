<script lang="ts">
  import { createQuery } from '@tanstack/svelte-query';
  import { listYears, listClasses } from '$lib/api/academic';
  import { setPageTitle } from '$lib/stores/title';
  import { findCurrentYear, findCurrentTerm } from '$lib/academicPeriod';

  setPageTitle('Academic');

  const yearsQ   = createQuery({ queryKey: ['academic-years'], queryFn: listYears,   staleTime: 5 * 60_000 });
  const classesQ = createQuery({ queryKey: ['classes'],        queryFn: listClasses, staleTime: 2 * 60_000 });

  const currentYear   = $derived(findCurrentYear($yearsQ.data ?? []) ?? null);
  const currentTerm   = $derived(currentYear ? findCurrentTerm(currentYear.terms) ?? null : null);
  const totalYears    = $derived($yearsQ.data?.length ?? 0);
  const activeClasses = $derived(($classesQ.data ?? []).filter(c => c.is_active).length);

  function fmtDate(d: string) {
    return new Date(d).toLocaleDateString('en-GH', { day: 'numeric', month: 'short' });
  }

  function daysLeft(end: string) {
    return Math.ceil((new Date(end).getTime() - Date.now()) / 86_400_000);
  }
</script>

<div class="space-y-7">
  <div>
    <h1 class="text-xl font-bold text-[var(--fg)]">Academic</h1>
    <p class="mt-0.5 text-sm text-[var(--fg-muted)]">Manage years, terms, classes, subjects, programmes, and year-end activities.</p>
  </div>

  <!-- Current academic context -->
  {#if $yearsQ.isPending}
    <div class="h-24 animate-pulse rounded-2xl bg-[var(--card)]"></div>
  {:else if !currentYear || !currentTerm}
    <div class="flex items-start gap-4 rounded-2xl border border-amber-300 bg-amber-50
                px-6 py-5 dark:border-amber-800/60 dark:bg-amber-950/20">
      <div class="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-xl
                  bg-amber-200/60 dark:bg-amber-800/40">
        <svg class="h-5 w-5 text-amber-700 dark:text-amber-400" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126z"/>
        </svg>
      </div>
      <div>
        <p class="font-semibold text-amber-800 dark:text-amber-300">
          {!currentYear ? 'No active academic year' : 'No active term'}
        </p>
        <p class="mt-0.5 text-sm text-amber-700/80 dark:text-amber-400/80">
          {!currentYear
            ? 'Create an academic year and mark it as current before recording attendance, scores, or fees.'
            : 'Set a term as current so attendance and assessment records are linked to the right period.'}
        </p>
        <a href="/admin/academic/years"
          class="mt-3 inline-flex items-center gap-1.5 rounded-lg bg-amber-200/60 px-3 py-1.5
                 text-xs font-semibold text-amber-800 transition hover:bg-amber-200
                 dark:bg-amber-800/40 dark:text-amber-300 dark:hover:bg-amber-800/60">
          {!currentYear ? 'Set up academic year' : 'Set current term'} →
        </a>
      </div>
    </div>
  {:else}
    {@const days = daysLeft(currentTerm.end_date)}
    <div class="overflow-hidden rounded-2xl border border-[var(--border)] bg-[var(--card)]">
      <div class="border-b border-[var(--border)] bg-[var(--hover)]/30 px-5 py-2.5">
        <p class="text-[10px] font-bold uppercase tracking-widest text-[var(--fg-subtle)]">
          Current academic context
        </p>
      </div>
      <div class="flex flex-wrap items-center justify-between gap-4 px-5 py-4">
        <div>
          <div class="flex items-center gap-2">
            <p class="text-lg font-bold text-[var(--fg)]">{currentYear.name}</p>
            <span class="badge badge-success">Active</span>
          </div>
          <p class="mt-1 text-sm text-[var(--fg-muted)]">
            {currentTerm.name} · {fmtDate(currentTerm.start_date)} – {fmtDate(currentTerm.end_date)}
          </p>
        </div>
        <div class="text-right">
          {#if days > 0}
            <p class="text-2xl font-bold leading-none {days <= 14 ? 'text-amber-600 dark:text-amber-400' : 'text-[var(--fg)]'}">{days}</p>
            <p class="mt-0.5 text-xs text-[var(--fg-muted)]">days left in term</p>
          {:else if days === 0}
            <p class="text-sm font-semibold text-amber-600 dark:text-amber-400">Term ends today</p>
          {:else}
            <p class="text-sm font-semibold text-red-500">Term ended {Math.abs(days)}d ago</p>
          {/if}
        </div>
      </div>
    </div>
  {/if}

  <!-- Section cards — 2×2 grid -->
  <div class="grid gap-4 sm:grid-cols-2">
    <!-- Years & Terms -->
    <a href="/admin/academic/years"
      class="group flex flex-col rounded-2xl border border-[var(--border)] bg-[var(--card)] p-5
             transition hover:border-[var(--brand)]/40 hover:shadow-sm">
      <div class="mb-3 flex items-center justify-between">
        <div class="flex h-10 w-10 items-center justify-center rounded-xl text-white"
             style="background-color: var(--brand)">
          <svg class="h-5 w-5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" d="M6.75 3v2.25M17.25 3v2.25M3 18.75V7.5a2.25 2.25 0 012.25-2.25h13.5A2.25 2.25 0 0121 7.5v11.25m-18 0A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75m-18 0v-7.5A2.25 2.25 0 015.25 9h13.5A2.25 2.25 0 0121 9v7.5m-9-6h.008v.008H12v-.008zM12 15h.008v.008H12V15z"/>
          </svg>
        </div>
        {#if totalYears > 0}
          <span class="text-xs font-semibold text-[var(--fg-muted)]">{totalYears} year{totalYears !== 1 ? 's' : ''}</span>
        {/if}
      </div>
      <p class="font-semibold text-[var(--fg)]">Years &amp; Terms</p>
      <p class="mt-1 flex-1 text-xs text-[var(--fg-muted)]">
        Configure academic years, set term dates, and mark the active term for the school.
      </p>
      <p class="mt-4 flex items-center gap-1 text-xs font-semibold transition group-hover:gap-2" style="color: var(--brand)">
        Manage <svg class="h-3 w-3" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M13.5 4.5L21 12m0 0l-7.5 7.5M21 12H3"/></svg>
      </p>
    </a>

    <!-- Classes -->
    <a href="/admin/academic/classes"
      class="group flex flex-col rounded-2xl border border-[var(--border)] bg-[var(--card)] p-5
             transition hover:border-[var(--brand)]/40 hover:shadow-sm">
      <div class="mb-3 flex items-center justify-between">
        <div class="flex h-10 w-10 items-center justify-center rounded-xl bg-blue-600 text-white">
          <svg class="h-5 w-5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" d="M3.75 6A2.25 2.25 0 016 3.75h2.25A2.25 2.25 0 0110.5 6v2.25a2.25 2.25 0 01-2.25 2.25H6a2.25 2.25 0 01-2.25-2.25V6zM3.75 15.75A2.25 2.25 0 016 13.5h2.25a2.25 2.25 0 012.25 2.25V18a2.25 2.25 0 01-2.25 2.25H6A2.25 2.25 0 013.75 18v-2.25zM13.5 6a2.25 2.25 0 012.25-2.25H18A2.25 2.25 0 0120.25 6v2.25A2.25 2.25 0 0118 10.5h-2.25a2.25 2.25 0 01-2.25-2.25V6zM13.5 15.75a2.25 2.25 0 012.25-2.25H18a2.25 2.25 0 012.25 2.25V18A2.25 2.25 0 0118 20.25h-2.25A2.25 2.25 0 0113.5 18v-2.25z"/>
          </svg>
        </div>
        {#if !$classesQ.isPending && activeClasses > 0}
          <span class="text-xs font-semibold text-[var(--fg-muted)]">{activeClasses} active</span>
        {/if}
      </div>
      <p class="font-semibold text-[var(--fg)]">Classes</p>
      <p class="mt-1 flex-1 text-xs text-[var(--fg-muted)]">
        Create and manage classes, assign class teachers, and view enrolled students.
      </p>
      <p class="mt-4 flex items-center gap-1 text-xs font-semibold transition group-hover:gap-2" style="color: var(--brand)">
        Manage <svg class="h-3 w-3" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M13.5 4.5L21 12m0 0l-7.5 7.5M21 12H3"/></svg>
      </p>
    </a>

    <!-- Subjects -->
    <a href="/admin/academic/subjects"
      class="group flex flex-col rounded-2xl border border-[var(--border)] bg-[var(--card)] p-5
             transition hover:border-[var(--brand)]/40 hover:shadow-sm">
      <div class="mb-3 flex h-10 w-10 items-center justify-center rounded-xl bg-indigo-600 text-white">
        <svg class="h-5 w-5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" d="M12 6.042A8.967 8.967 0 006 3.75c-1.052 0-2.062.18-3 .512v14.25A8.987 8.987 0 016 18c2.305 0 4.408.867 6 2.292m0-14.25a8.966 8.966 0 016-2.292c1.052 0 2.062.18 3 .512v14.25A8.987 8.987 0 0018 18a8.967 8.967 0 00-6 2.292m0-14.25v14.25"/>
        </svg>
      </div>
      <p class="font-semibold text-[var(--fg)]">Subjects</p>
      <p class="mt-1 flex-1 text-xs text-[var(--fg-muted)]">
        Define the subject catalogue available across all classes. Assign subjects to classes from the class detail page.
      </p>
      <p class="mt-4 flex items-center gap-1 text-xs font-semibold transition group-hover:gap-2" style="color: var(--brand)">
        Manage <svg class="h-3 w-3" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M13.5 4.5L21 12m0 0l-7.5 7.5M21 12H3"/></svg>
      </p>
    </a>

    <!-- Programmes -->
    <a href="/admin/academic/programmes"
      class="group flex flex-col rounded-2xl border border-[var(--border)] bg-[var(--card)] p-5
             transition hover:border-[var(--brand)]/40 hover:shadow-sm">
      <div class="mb-3 flex h-10 w-10 items-center justify-center rounded-xl bg-amber-600 text-white">
        <svg class="h-5 w-5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" d="M4.26 10.147a60.436 60.436 0 00-.491 6.347A48.627 48.627 0 0112 20.904a48.627 48.627 0 018.232-4.41 60.46 60.46 0 00-.491-6.347m-15.482 0a50.57 50.57 0 00-2.658-.813A59.905 59.905 0 0112 3.493a59.902 59.902 0 0110.399 5.84c-.896.248-1.783.52-2.658.814m-15.482 0A50.697 50.697 0 0112 13.489a50.702 50.702 0 017.74-3.342M6.75 15a.75.75 0 100-1.5.75.75 0 000 1.5zm0 0v-3.675A55.378 55.378 0 0112 8.443m-7.007 11.55A5.981 5.981 0 006.75 15.75v-1.5"/>
        </svg>
      </div>
      <p class="font-semibold text-[var(--fg)]">Programmes</p>
      <p class="mt-1 flex-1 text-xs text-[var(--fg-muted)]">
        Configure SHS programmes — Science, Arts, Business, etc. Used when placing students into specialised tracks.
      </p>
      <p class="mt-4 flex items-center gap-1 text-xs font-semibold transition group-hover:gap-2" style="color: var(--brand)">
        Manage <svg class="h-3 w-3" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M13.5 4.5L21 12m0 0l-7.5 7.5M21 12H3"/></svg>
      </p>
    </a>

    <!-- Promotion -->
    <a href="/admin/academic/promote"
      class="group flex flex-col rounded-2xl border border-[var(--border)] bg-[var(--card)] p-5
             transition hover:border-[var(--brand)]/40 hover:shadow-sm">
      <div class="mb-3 flex h-10 w-10 items-center justify-center rounded-xl bg-emerald-600 text-white">
        <svg class="h-5 w-5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" d="M4.5 10.5L12 3m0 0l7.5 7.5M12 3v18"/>
        </svg>
      </div>
      <p class="font-semibold text-[var(--fg)]">Class Promotion</p>
      <p class="mt-1 flex-1 text-xs text-[var(--fg-muted)]">
        Move students to the next year group at end of year. Automatically suggests the matching class.
      </p>
      <p class="mt-4 flex items-center gap-1 text-xs font-semibold transition group-hover:gap-2" style="color: var(--brand)">
        Run promotion <svg class="h-3 w-3" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M13.5 4.5L21 12m0 0l-7.5 7.5M21 12H3"/></svg>
      </p>
    </a>

    <!-- Graduation -->
    <a href="/admin/academic/graduation"
      class="group flex flex-col rounded-2xl border border-[var(--border)] bg-[var(--card)] p-5
             transition hover:border-[var(--brand)]/40 hover:shadow-sm">
      <div class="mb-3 flex h-10 w-10 items-center justify-center rounded-xl bg-violet-600 text-white">
        <svg class="h-5 w-5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" d="M4.26 10.147a60.438 60.438 0 00-.491 6.347A48.627 48.627 0 0112 20.904a48.627 48.627 0 018.232-4.41 60.46 60.46 0 00-.491-6.347m-15.482 0a50.636 50.636 0 00-2.658-.813A59.906 59.906 0 0112 3.493a59.903 59.903 0 0110.399 5.84c-.896.248-1.783.52-2.658.814m-15.482 0A50.717 50.717 0 0112 13.489a50.702 50.702 0 017.74-3.342"/>
        </svg>
      </div>
      <p class="font-semibold text-[var(--fg)]">Year-end Graduation</p>
      <p class="mt-1 flex-1 text-xs text-[var(--fg-muted)]">
        Record final outcomes for leaving students — graduated, withdrawn, or transferred.
      </p>
      <p class="mt-4 flex items-center gap-1 text-xs font-semibold transition group-hover:gap-2" style="color: var(--brand)">
        Run graduation <svg class="h-3 w-3" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M13.5 4.5L21 12m0 0l-7.5 7.5M21 12H3"/></svg>
      </p>
    </a>
  </div>
</div>
