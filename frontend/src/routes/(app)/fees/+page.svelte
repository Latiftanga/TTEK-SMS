<script lang="ts">
  import { createQuery } from '@tanstack/svelte-query';
  import { listAllTerms, type AcademicTerm } from '$lib/api/academic';
  import { isSchoolAdmin } from '$lib/stores/permissions';
  import { currentUser } from '$lib/stores/auth';
  import PaymentsTab from './PaymentsTab.svelte';
  import SetupTab    from './SetupTab.svelte';

  const isAdmin = $derived($isSchoolAdmin || !!$currentUser?.is_superadmin);

  type Tab = 'payments' | 'setup';
  let activeTab = $state<Tab>('payments');

  const termsQ = createQuery({ queryKey: ['all-terms'], queryFn: listAllTerms, staleTime: 5 * 60_000 });
  const terms  = $derived<AcademicTerm[]>([...($termsQ.data ?? [])].sort((a, b) => b.start_date.localeCompare(a.start_date)));
  let termId   = $state('');
  $effect(() => {
    if (!termId && terms.length) termId = terms.find(t => t.is_current)?.id ?? terms[0]?.id ?? '';
  });

  const termName = $derived(terms.find(t => t.id === termId)?.name ?? '');
</script>

<svelte:head><title>Fees</title></svelte:head>

<div class="space-y-6">
  <div class="flex flex-wrap items-center justify-between gap-3">
    <h1 class="text-xl font-bold text-[var(--fg)]">Fees</h1>
    {#if terms.length}
      <select bind:value={termId} class="sel max-w-xs">
        {#each terms as t}<option value={t.id}>{t.name}{t.is_current ? ' (current)' : ''}</option>{/each}
      </select>
    {/if}
  </div>

  {#if isAdmin}
    <div class="border-b border-[var(--border)]">
      <nav class="-mb-px flex gap-1">
        {#each ([['payments', 'Payments'], ['setup', 'Fee Setup']] as const) as [key, label]}
          <button onclick={() => activeTab = key}
            class="relative px-4 pb-3 pt-1 text-sm font-medium transition-colors
                   {activeTab === key ? 'text-[var(--brand)]' : 'text-[var(--fg-muted)] hover:text-[var(--fg)]'}">
            {label}
            <span class="pointer-events-none absolute bottom-0 left-0 right-0 h-0.5 rounded-t-sm
                         {activeTab === key ? 'bg-[var(--brand)]' : 'bg-transparent'}"></span>
          </button>
        {/each}
      </nav>
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
</div>

<style>
  @reference "tailwindcss";
  .sel { @apply rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--fg)] focus:border-[var(--brand)] focus:outline-none transition; }
</style>
