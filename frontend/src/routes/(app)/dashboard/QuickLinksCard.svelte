<script lang="ts">
  // Same icon-row list pattern as MySubjectsCard.svelte/MyHousesCard.svelte —
  // only ever shown alongside MyClassesCard, so its two links are the
  // class-teacher-specific ones (My Students/Reports).
  const students = `<path stroke-linecap="round" stroke-linejoin="round" d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z"/>`;
  const reports = `<path stroke-linecap="round" stroke-linejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/>`;
  const arrow = `<path stroke-linecap="round" stroke-linejoin="round" d="M7 17L17 7M17 7H7M17 7v10"/>`;

  const links = [
    { href: '/students', label: 'My Students', sub: 'View & register', icon: students },
    { href: '/reports',  label: 'Reports',      sub: 'View & download', icon: reports },
  ];
</script>

<div>
  <p class="mb-2.5 text-[0.6875rem] font-semibold uppercase tracking-widest text-[var(--fg-muted)]">Quick Links</p>
  <div class="overflow-hidden rounded-[1.25rem] border border-[var(--border)] bg-[var(--card)] divide-y divide-[var(--border)]"
       style="box-shadow: var(--shadow-sm);">
    {#each links as link}
      <a href={link.href} class="group flex items-center gap-3.5 px-4 py-3.5 transition hover:bg-[var(--hover)]">
        <div class="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-[var(--hover)] transition group-hover:bg-[var(--card)]">
          <svg class="h-4 w-4 text-[var(--fg-muted)]" fill="none" stroke="currentColor" stroke-width="1.6" viewBox="0 0 24 24">{@html link.icon}</svg>
        </div>
        <div class="min-w-0 flex-1">
          <p class="text-[0.8125rem] font-semibold text-[var(--fg)]">{link.label}</p>
          <p class="text-[0.6875rem] text-[var(--fg-muted)]">{link.sub}</p>
        </div>
        <svg class="h-4 w-4 shrink-0 text-[var(--fg-subtle)] transition-transform group-hover:translate-x-0.5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">{@html arrow}</svg>
      </a>
    {/each}
  </div>
</div>
