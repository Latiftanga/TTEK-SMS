<script lang="ts">
  import { page } from '$app/stores';
  import { school } from '$lib/stores/school';
  import PageHeader from '$lib/components/PageHeader.svelte';

  const { children } = $props();

  const isSHS = $derived($school?.schoolType === 'SHS');

  const tabs = $derived([
    { href: '/admin/academic',             label: 'Calendar',   exact: true },
    { href: '/admin/academic/subjects',    label: 'Subjects'               },
    ...(isSHS ? [{ href: '/admin/academic/programmes', label: 'Programmes' }] : []),
    { href: '/admin/academic/classes',     label: 'Classes'                },
    { href: '/admin/academic/promote',     label: 'Promotion'              },
  ]);

  function isActive(href: string, exact = false) {
    return exact
      ? $page.url.pathname === href
      : $page.url.pathname.startsWith(href);
  }
</script>

<PageHeader title="Academic" description="Manage the school calendar, subjects, programmes, and classes." />

<nav class="-mb-px mb-6 flex gap-1 border-b border-[var(--border)]" aria-label="Academic sections">
  {#each tabs as tab}
    {@const active = isActive(tab.href, tab.exact)}
    <a
      href={tab.href}
      aria-current={active ? 'page' : undefined}
      class="relative pb-2.5 pt-0.5 px-3 text-sm font-medium transition-colors
             {active ? 'text-[var(--brand)]' : 'text-[var(--fg-muted)] hover:text-[var(--fg)]'}"
    >
      {tab.label}
      {#if active}
        <span class="absolute bottom-0 left-0 right-0 h-0.5 rounded-t-sm bg-[var(--brand)]"></span>
      {/if}
    </a>
  {/each}
</nav>

{@render children()}
