<script lang="ts">
  import { page } from '$app/stores';
  import Sidebar from '$lib/components/Sidebar.svelte';
  import TopBar from '$lib/components/TopBar.svelte';
  import BottomNav from '$lib/components/BottomNav.svelte';

  const { children } = $props();

  let sidebarOpen = $state(false);
</script>

<div class="flex h-screen overflow-hidden bg-[var(--bg)]">
  <Sidebar open={sidebarOpen} onclose={() => sidebarOpen = false} />

  <div class="flex flex-1 flex-col overflow-hidden">
    <TopBar toggleSidebar={() => sidebarOpen = !sidebarOpen} />

    <main class="flex-1 overflow-y-auto">
      <div class="mx-auto max-w-7xl px-4 py-7 pb-24 lg:px-8 lg:pb-8">
        {#key $page.url.pathname}
          <div class="page-enter">
            {@render children()}
          </div>
        {/key}
      </div>
    </main>
  </div>
</div>

<BottomNav onmore={() => sidebarOpen = !sidebarOpen} />
