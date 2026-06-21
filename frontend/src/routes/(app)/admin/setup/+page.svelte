<script lang="ts">
  import { page } from '$app/stores';
  import { goto } from '$app/navigation';
  import ProfileTab       from './ProfileTab.svelte';
  import CommunicationTab from './CommunicationTab.svelte';
  import AiTab            from './AiTab.svelte';

  type Tab = 'profile' | 'communication' | 'ai';

  const tabs: { id: Tab; label: string }[] = [
    { id: 'profile',       label: 'Profile'        },
    { id: 'communication', label: 'Communication'  },
    { id: 'ai',            label: 'AI Assistant'   },
  ];

  const activeTab = $derived<Tab>(
    ($page.url.searchParams.get('tab') as Tab | null) ?? 'profile'
  );

  function setTab(id: Tab) {
    goto(`?tab=${id}`, { replaceState: true, noScroll: true });
  }
</script>

<div class="mb-6">
  <h1 class="text-2xl font-bold tracking-tight text-[var(--fg)]">School Setup</h1>
  <p class="mt-1 text-sm text-[var(--fg-muted)]">Manage your school's profile and communication channels.</p>
</div>

<div class="mb-6 border-b border-[var(--border)]">
  <nav class="-mb-px flex gap-1" aria-label="Setup sections">
    {#each tabs as tab}
      <button
        onclick={() => setTab(tab.id)}
        class="relative px-4 pb-3 pt-1 text-sm font-medium transition-colors
               {activeTab === tab.id ? 'text-[var(--brand)]' : 'text-[var(--fg-muted)] hover:text-[var(--fg)]'}"
      >
        {tab.label}
        <span class="pointer-events-none absolute bottom-0 left-0 right-0 h-0.5 rounded-t-sm
                     {activeTab === tab.id ? 'bg-[var(--brand)]' : 'bg-transparent'}"></span>
      </button>
    {/each}
  </nav>
</div>

{#if activeTab === 'profile'}
  <ProfileTab />
{:else if activeTab === 'communication'}
  <CommunicationTab />
{:else if activeTab === 'ai'}
  <AiTab />
{/if}
