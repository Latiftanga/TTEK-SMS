<script lang="ts">
  import { createQuery } from '@tanstack/svelte-query';
  import { page } from '$app/stores';
  import { goto } from '$app/navigation';
  import { listAllTerms, type AcademicTerm } from '$lib/api/academic';
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

  const termsQ = createQuery({ queryKey: ['all-terms'], queryFn: listAllTerms, staleTime: 5 * 60_000 });
  const terms  = $derived<AcademicTerm[]>([...($termsQ.data ?? [])].sort((a, b) => b.start_date.localeCompare(a.start_date)));
  let termId   = $state('');
  $effect(() => {
    if (!termId && terms.length) termId = terms.find(t => t.is_current)?.id ?? terms[0]?.id ?? '';
  });

  const termName = $derived(terms.find(t => t.id === termId)?.name ?? '');
</script>


<PageHeader title="Fees" description="Record payments, manage fee structures, and apply discounts.">
  {#if terms.length}
    <select bind:value={termId}
      class="rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--fg)] focus:border-[var(--brand)] focus:outline-none transition max-w-xs">
      {#each terms as t}<option value={t.id}>{t.name}{t.is_current ? ' (current)' : ''}</option>{/each}
    </select>
  {/if}
</PageHeader>

{#if isAdmin}
  <div class="mb-6">
    <TabBar tabs={adminTabs} active={activeTab} onchange={setTab} />
  </div>
{/if}

{#if termId}
  {#if activeTab === 'payments' || !isAdmin}
    <PaymentsTab {termId} {termName} {isAdmin} />
  {:else}
    <SetupTab {termId} {termName} />
  {/if}
{:else}
  <div class="h-32 animate-pulse rounded-2xl bg-[var(--card)]"></div>
{/if}
