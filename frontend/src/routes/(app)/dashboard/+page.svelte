<script lang="ts">
  import { createQuery } from '@tanstack/svelte-query';
  import { getDashboard } from '$lib/api/dashboard';
  import { userRole } from '$lib/stores/permissions';
  import SkeletonCard from '$lib/components/SkeletonCard.svelte';
  import TeacherView      from './TeacherView.svelte';
  import AdminView        from './AdminView.svelte';
  import ApproverView     from './ApproverView.svelte';
  import FinanceView      from './FinanceView.svelte';
  import HousemasterView  from './HousemasterView.svelte';
  import { setPageTitle } from '$lib/stores/title';
  setPageTitle('Dashboard');

  const query = createQuery({
    queryKey: ['dashboard'],
    queryFn: getDashboard,
    staleTime: 2 * 60_000,
    refetchOnWindowFocus: false,
  });

  // Populate the permissions store so the sidebar can adapt
  $effect(() => {
    if ($query.data) userRole.set($query.data.view);
  });
</script>

{#if $query.isPending}
  <div class="space-y-4">
    <SkeletonCard height="h-16" lines={1} />
    <div class="grid grid-cols-2 gap-3 lg:grid-cols-4">
      <SkeletonCard /><SkeletonCard /><SkeletonCard /><SkeletonCard />
    </div>
    <SkeletonCard height="h-48" />
  </div>

{:else if $query.isError}
  <div class="rounded-2xl border border-red-100 dark:border-red-900 bg-red-50 dark:bg-red-950/40 p-6 text-sm text-red-700 dark:text-red-400">
    Could not load dashboard.
    <button onclick={() => $query.refetch()} class="ml-2 underline">Retry</button>
  </div>

{:else if $query.data}
  {@const data = $query.data}
  {#if data.view === 'teacher'}
    <TeacherView {data} />
  {:else if data.view === 'admin'}
    <AdminView {data} />
  {:else if data.view === 'approver'}
    <ApproverView {data} />
  {:else if data.view === 'finance'}
    <FinanceView {data} />
  {:else if data.view === 'housemaster'}
    <HousemasterView {data} />
  {/if}
{/if}
