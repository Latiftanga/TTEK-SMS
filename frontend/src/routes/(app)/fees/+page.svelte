<script lang="ts">
  import { page } from '$app/stores';
  import { goto } from '$app/navigation';
  import { useTermSelector } from '$lib/termSelector.svelte';
  import { isSchoolAdmin } from '$lib/stores/permissions';
  import { currentUser } from '$lib/stores/auth';
  import PaymentsTab from './PaymentsTab.svelte';
  import SetupTab    from './SetupTab.svelte';
  import TabBar      from '$lib/components/TabBar.svelte';
  import PageHeader  from '$lib/components/PageHeader.svelte';
  import { setPageTitle } from '$lib/stores/title';

  const isAdmin = $derived($isSchoolAdmin || !!$currentUser?.is_superadmin);
  setPageTitle('Fees');

  type Tab = 'payments' | 'setup';
  const activeTab = $derived<Tab>(($page.url.searchParams.get('tab') as Tab | null) ?? 'payments');

  const adminTabs = [
    { id: 'payments', label: 'Payments' },
    { id: 'setup',    label: 'Fee Setup' },
  ];

  function setTab(id: string) {
    goto(`?tab=${id}`, { replaceState: true, noScroll: true });
  }

  const term = useTermSelector();
  const termName = $derived(term.terms.find(t => t.id === term.termId)?.name ?? '');
</script>


<PageHeader title="Fees" description="Record payments, manage fee structures, and apply discounts.">
  {#if term.terms.length}
    <select bind:value={term.termId}
      class="rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--fg)] focus:border-[var(--brand)] focus:outline-none transition max-w-xs">
      {#each term.terms as t}<option value={t.id}>{t.name}{t.is_current ? ' (current)' : ''}</option>{/each}
    </select>
  {/if}
</PageHeader>

{#if isAdmin}
  <div class="mb-6">
    <TabBar tabs={adminTabs} active={activeTab} onchange={setTab} />
  </div>
{/if}

{#if term.termId}
  {#if activeTab === 'payments' || !isAdmin}
    <PaymentsTab termId={term.termId} {termName} {isAdmin} />
  {:else}
    <SetupTab termId={term.termId} {termName} />
  {/if}
{:else}
  <div class="h-32 animate-pulse rounded-2xl bg-[var(--card)]"></div>
{/if}
