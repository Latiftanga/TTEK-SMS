<script lang="ts">
  import { page } from '$app/stores';
  import { school } from '$lib/stores/school';

  const { children } = $props();

  const isSHS = $derived($school?.schoolType === 'SHS');

  const tabs = $derived([
    { href: '/admin/academic',             label: 'Calendar',    exact: true },
    { href: '/admin/academic/subjects',    label: 'Subjects'                },
    ...(isSHS ? [{ href: '/admin/academic/programmes', label: 'Programmes' }] : []),
    { href: '/admin/academic/classes',     label: 'Classes'                 },
  ]);

  function isActive(href: string, exact = false) {
    return exact
      ? $page.url.pathname === href
      : $page.url.pathname.startsWith(href);
  }
</script>

<div class="mb-6">
  <h1 class="text-2xl font-bold tracking-tight text-[var(--fg)]">Academic</h1>
  <p class="mt-1 text-sm text-[var(--fg-muted)]">Manage the school calendar, subjects, programmes, and classes.</p>
</div>

<div class="mb-6 border-b border-[var(--border)]">
  <nav class="-mb-px flex gap-1" aria-label="Academic sections">
    {#each tabs as tab}
      {@const active = isActive(tab.href, tab.exact)}
      <a
        href={tab.href}
        class="relative px-4 pb-3 pt-1 text-sm font-medium transition-colors
               {active ? 'text-[var(--brand)]' : 'text-[var(--fg-muted)] hover:text-[var(--fg)]'}"
      >
        {tab.label}
        <span class="pointer-events-none absolute bottom-0 left-0 right-0 h-0.5 rounded-t-sm
                     {active ? 'bg-[var(--brand)]' : 'bg-transparent'}"></span>
      </a>
    {/each}
  </nav>
</div>

{@render children()}
