<script lang="ts">
  import { page } from '$app/stores';
  import { goto } from '$app/navigation';
  import PageHeader     from '$lib/components/PageHeader.svelte';
  import { setPageTitle } from '$lib/stores/title';
  setPageTitle('School Setup');
  import TabBar         from '$lib/components/TabBar.svelte';
  import ProfileTab     from './ProfileTab.svelte';
  import CommunicationTab from './CommunicationTab.svelte';
  import AiTab          from './AiTab.svelte';
  import PermissionsTab from './PermissionsTab.svelte';

  type Tab = 'profile' | 'communication' | 'ai' | 'permissions';

  const tabs = [
    { id: 'profile',       label: 'Profile',       icon: `<path stroke-linecap="round" stroke-linejoin="round" d="M3.75 21h16.5M4.5 3h15M5.25 3v18m13.5-18v18M9 6.75h1.5m-1.5 3h1.5m-1.5 3h1.5m3-6H15m-1.5 3H15m-1.5 3H15M9 21v-3.375c0-.621.504-1.125 1.125-1.125h3.75c.621 0 1.125.504 1.125 1.125V21"/>` },
    { id: 'communication', label: 'Communication', icon: `<path stroke-linecap="round" stroke-linejoin="round" d="M8.625 12a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0H8.25m4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0H12m4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0h-.375M21 12c0 4.556-4.03 8.25-9 8.25a9.764 9.764 0 01-2.555-.337A5.972 5.972 0 015.41 20.97a5.969 5.969 0 01-.474-.065 4.48 4.48 0 00.978-2.025c.09-.457-.133-.901-.467-1.226C3.93 16.178 3 14.189 3 12c0-4.556 4.03-8.25 9-8.25s9 3.694 9 8.25z"/>` },
    { id: 'ai',            label: 'AI Assistant',  icon: `<path stroke-linecap="round" stroke-linejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09zM18.259 8.715L18 9.75l-.259-1.035a3.375 3.375 0 00-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 002.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 002.456 2.456L21.75 6l-1.035.259a3.375 3.375 0 00-2.456 2.456zM16.894 20.567L16.5 21.75l-.394-1.183a2.25 2.25 0 00-1.423-1.423L13.5 18.75l1.183-.394a2.25 2.25 0 001.423-1.423l.394-1.183.394 1.183a2.25 2.25 0 001.423 1.423l1.183.394-1.183.394a2.25 2.25 0 00-1.423 1.423z"/>` },
    { id: 'permissions',   label: 'Permissions',   icon: `<path stroke-linecap="round" stroke-linejoin="round" d="M9 12.75L11.25 15 15 9.75m-3-7.036A11.959 11.959 0 013.598 6 11.99 11.99 0 003 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285z"/>` },
  ];

  const activeTab = $derived<Tab>(
    ($page.url.searchParams.get('tab') as Tab | null) ?? 'profile'
  );

  function setTab(id: string) {
    goto(`?tab=${id}`, { replaceState: true, noScroll: true });
  }
</script>

<PageHeader title="School Setup" description="School identity, SMS and email configuration, AI features, and role permissions." />

<div class="mb-6">
  <TabBar {tabs} active={activeTab} onchange={setTab} />
</div>

{#if activeTab === 'profile'}
  <ProfileTab />
{:else if activeTab === 'communication'}
  <CommunicationTab />
{:else if activeTab === 'ai'}
  <AiTab />
{:else if activeTab === 'permissions'}
  <PermissionsTab />
{/if}
