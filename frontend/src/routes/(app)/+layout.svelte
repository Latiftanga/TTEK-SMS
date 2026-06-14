<script lang="ts">
  import Sidebar from '$lib/components/Sidebar.svelte';
  import TopBar from '$lib/components/TopBar.svelte';
  import BottomNav from '$lib/components/BottomNav.svelte';

  const { children } = $props();

  let sidebarOpen = $state(false);
</script>

<div class="flex h-screen overflow-hidden bg-[var(--bg)]">
  <!-- Sidebar: hidden on mobile, always visible on desktop -->
  <Sidebar open={sidebarOpen} onclose={() => sidebarOpen = false} />

  <div class="flex flex-1 flex-col overflow-hidden">
    <TopBar toggleSidebar={() => sidebarOpen = !sidebarOpen} />

    <main class="flex-1 overflow-y-auto">
      <!-- pb-20 on mobile clears the fixed bottom nav bar -->
      <div class="mx-auto max-w-7xl px-4 py-6 pb-24 lg:px-8 lg:pb-6">
        {@render children()}
      </div>
    </main>
  </div>
</div>

<!-- Mobile bottom navigation — replaces sidebar on small screens -->
<BottomNav onmore={() => sidebarOpen = !sidebarOpen} />
