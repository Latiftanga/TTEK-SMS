<script lang="ts">
  import { createQuery } from '@tanstack/svelte-query';
  import { getDashboard } from '$lib/api/dashboard';
  import SkeletonCard from '$lib/components/SkeletonCard.svelte';
  import StaffView        from './StaffView.svelte';
  import AdminView        from './AdminView.svelte';
  import ApproverView     from './ApproverView.svelte';
  import FinanceView      from './FinanceView.svelte';
  import OtherRolesStrip  from './OtherRolesStrip.svelte';
  import { setPageTitle } from '$lib/stores/title';
  setPageTitle('Dashboard');

  // refetchOnMount: 'always' — a role/responsibility change (e.g. a staff
  // member is assigned as housemaster/class teacher elsewhere in the app)
  // must show up the moment this page is landed on, not just after
  // staleTime expires. staleTime still avoids a duplicate fetch if this
  // component remounts rapidly (e.g. a quick tab switch); it's the "was
  // this data ever refreshed for THIS visit" question that refetchOnMount
  // answers, and both `view` and the nav-gating booleans below depend on
  // getting that answer right every time.
  // Same ['dashboard'] cache key + refetchOnMount as the root (app) layout's
  // own copy of this query (which owns populating the userRole/is*Teacher/
  // isHousemaster nav-gating stores now — see its comment) — TanStack Query
  // dedupes same-key queries, so landing here doesn't trigger a second
  // network request, just reads/refreshes the shared cache entry.
  const query = createQuery({
    queryKey: ['dashboard'],
    queryFn: getDashboard,
    staleTime: 2 * 60_000,
    refetchOnMount: 'always',
    refetchOnWindowFocus: false,
  });
</script>

{#if $query.isPending}
  <div class="space-y-5">
    <SkeletonCard height="h-16" lines={1} />
    <div class="grid grid-cols-2 gap-4 lg:grid-cols-4">
      <SkeletonCard /><SkeletonCard /><SkeletonCard /><SkeletonCard />
    </div>
    <SkeletonCard height="h-48" />
  </div>

{:else if $query.isError}
  <div class="rounded-[1.25rem] border border-red-100 dark:border-red-900 bg-red-50 dark:bg-red-950/40 p-6 text-sm text-red-700 dark:text-red-400">
    Could not load dashboard.
    <button onclick={() => $query.refetch()} class="ml-2 underline">Retry</button>
  </div>

{:else if $query.data}
  {@const data = $query.data}
  {#if data.view === 'staff'}
    <StaffView {data} />
  {:else if data.view === 'admin'}
    <AdminView {data} />
  {:else if data.view === 'approver'}
    <ApproverView {data} />
  {:else if data.view === 'finance'}
    <FinanceView {data} />
  {/if}
  <OtherRolesStrip roles={data.other_roles} />
{/if}
