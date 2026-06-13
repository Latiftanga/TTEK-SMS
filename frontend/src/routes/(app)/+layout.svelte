<script lang="ts">
  import Sidebar from '$lib/components/Sidebar.svelte';
  import TopBar from '$lib/components/TopBar.svelte';

  const { children } = $props();

  let sidebarOpen = $state(false);
</script>

<div class="flex h-screen overflow-hidden bg-surface">
  <Sidebar open={sidebarOpen} onclose={() => sidebarOpen = false} />

  <div class="flex flex-1 flex-col overflow-hidden">
    <TopBar toggleSidebar={() => sidebarOpen = !sidebarOpen} />

    <main class="flex-1 overflow-y-auto">
      <div class="mx-auto max-w-5xl px-4 py-6 lg:px-8">
        {@render children()}
      </div>
    </main>
  </div>
</div>
