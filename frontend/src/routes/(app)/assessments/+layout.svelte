<script lang="ts">
  import { page } from '$app/stores';
  import { userRole } from '$lib/stores/permissions';
  import PageHeader from '$lib/components/PageHeader.svelte';

  const { children } = $props();

  const canManage = $derived($userRole === 'admin' || $userRole === 'approver');

  const tabs = $derived([
    { href: '/assessments',         label: 'Assessments'    },
    ...(canManage ? [
      { href: '/assessments/types',  label: 'Types'          },
      { href: '/assessments/scales', label: 'Grading Scales' },
    ] : []),
  ]);

  function isActive(href: string) {
    const p = $page.url.pathname;
    if (href === '/assessments') {
      return p === '/assessments'
        || (p.startsWith('/assessments/') && !p.startsWith('/assessments/types') && !p.startsWith('/assessments/scales'));
    }
    return p.startsWith(href);
  }
</script>

<PageHeader title="Assessments" description="Enter scores, approve, and publish assessment results." />

<nav class="-mb-px mb-6 flex gap-1 border-b border-[var(--border)]" aria-label="Assessments sections">
  {#each tabs as tab}
    {@const active = isActive(tab.href)}
    <a href={tab.href}
      aria-current={active ? 'page' : undefined}
      class="relative pb-2.5 pt-0.5 px-3 text-sm font-medium transition-colors
             {active ? 'text-[var(--brand)]' : 'text-[var(--fg-muted)] hover:text-[var(--fg)]'}">
      {tab.label}
      {#if active}
        <span class="absolute bottom-0 left-0 right-0 h-0.5 rounded-t-sm bg-[var(--brand)]"></span>
      {/if}
    </a>
  {/each}
</nav>

{@render children()}
