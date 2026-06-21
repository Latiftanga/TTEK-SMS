<script lang="ts">
  import { page } from '$app/stores';
  import { goto } from '$app/navigation';
  import PageHeader       from '$lib/components/PageHeader.svelte';
  import TabBar           from '$lib/components/TabBar.svelte';
  import ProfileTab       from './ProfileTab.svelte';
  import CommunicationTab from './CommunicationTab.svelte';
  import AiTab            from './AiTab.svelte';
  import HousingTab       from './HousingTab.svelte';

  type Tab = 'profile' | 'communication' | 'ai' | 'housing';

  const tabs = [
    { id: 'profile',       label: 'Profile'        },
    { id: 'communication', label: 'Communication'  },
    { id: 'ai',            label: 'AI Assistant'   },
    { id: 'housing',       label: 'Housing'        },
  ];

  const activeTab = $derived<Tab>(
    ($page.url.searchParams.get('tab') as Tab | null) ?? 'profile'
  );

  function setTab(id: string) {
    goto(`?tab=${id}`, { replaceState: true, noScroll: true });
  }
</script>

<PageHeader title="School Setup" description="Profile, communication channels, AI features, and boarding configuration." />

<div class="mb-6">
  <TabBar {tabs} active={activeTab} onchange={setTab} />
</div>

{#if activeTab === 'profile'}
  <ProfileTab />
{:else if activeTab === 'communication'}
  <CommunicationTab />
{:else if activeTab === 'ai'}
  <AiTab />
{:else if activeTab === 'housing'}
  <HousingTab />
{/if}
