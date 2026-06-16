<script lang="ts">
  import { school as schoolStore } from '$lib/stores/school';
  import ProfileTab    from './ProfileTab.svelte';
  import YearsTab      from '../academic/YearsTab.svelte';
  import SubjectsTab   from '../academic/SubjectsTab.svelte';
  import ProgrammesTab from '../academic/ProgrammesTab.svelte';
  import SmsTab        from './SmsTab.svelte';
  import EmailTab      from './EmailTab.svelte';

  type Tab = 'profile' | 'calendar' | 'subjects' | 'programmes' | 'sms' | 'email';
  let activeTab = $state<Tab>('profile');

  const isSHS = $derived($schoolStore?.schoolType === 'SHS');

  const tabs = $derived([
    { id: 'profile'    as Tab, label: 'Profile'            },
    { id: 'calendar'   as Tab, label: 'Academic Calendar'  },
    { id: 'subjects'   as Tab, label: 'Subjects'           },
    ...(isSHS ? [{ id: 'programmes' as Tab, label: 'Programmes' }] : []),
    { id: 'sms'        as Tab, label: 'SMS'                },
    { id: 'email'      as Tab, label: 'Email'              },
  ]);
</script>

<div class="mb-6">
  <h1 class="text-2xl font-bold tracking-tight text-[var(--fg)]">School Setup</h1>
  <p class="mt-1 text-sm text-[var(--fg-muted)]">Manage your school's profile, curriculum, and communication channels.</p>
</div>

<!-- Tab nav -->
<div class="mb-6 border-b border-[var(--border)]">
  <nav class="-mb-px flex gap-1" aria-label="Setup sections">
    {#each tabs as tab}
      <button
        onclick={() => activeTab = tab.id}
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
{:else if activeTab === 'calendar'}
  <YearsTab />
{:else if activeTab === 'subjects'}
  <SubjectsTab />
{:else if activeTab === 'programmes'}
  <ProgrammesTab />
{:else if activeTab === 'sms'}
  <SmsTab />
{:else if activeTab === 'email'}
  <EmailTab />
{/if}
