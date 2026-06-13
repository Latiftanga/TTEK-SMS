<script lang="ts">
  import { createQuery } from '@tanstack/svelte-query';
  import { getDashboard } from '$lib/api/dashboard';
  import SkeletonCard from '$lib/components/SkeletonCard.svelte';
  import TeacherView from './TeacherView.svelte';
  import AdminView from './AdminView.svelte';
  import HodView from './HodView.svelte';
  import FinanceView from './FinanceView.svelte';

  const query = createQuery({
    queryKey: ['dashboard'],
    queryFn: getDashboard,
    staleTime: 2 * 60_000,
    refetchOnWindowFocus: true,
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
  <div class="rounded-2xl border border-red-100 bg-red-50 p-6 text-sm text-red-700">
    Could not load dashboard.
    <button onclick={() => $query.refetch()} class="ml-2 underline">Retry</button>
  </div>

{:else if $query.data}
  {@const data = $query.data}
  {#if data.view === 'teacher'}
    <TeacherView {data} />
  {:else if data.view === 'admin'}
    <AdminView {data} />
  {:else if data.view === 'hod'}
    <HodView {data} />
  {:else if data.view === 'finance'}
    <FinanceView {data} />
  {/if}
{/if}
