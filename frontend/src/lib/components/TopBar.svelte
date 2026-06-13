<script lang="ts">
  import { currentUser } from '$lib/stores/auth';
  import { logout } from '$lib/api/auth';
  import { auth } from '$lib/stores/auth';
  import { goto } from '$app/navigation';

  interface Props { toggleSidebar: () => void; }
  const { toggleSidebar }: Props = $props();

  let menuOpen = $state(false);

  const today = new Date().toLocaleDateString('en-GH', {
    weekday: 'short', day: 'numeric', month: 'short', year: 'numeric',
  });

  async function handleLogout() {
    const refreshToken = localStorage.getItem('refresh_token') ?? '';
    await logout(refreshToken);
    auth.clearAuth();
    goto('/login');
  }

  const initials = $derived(() => {
    const u = $currentUser;
    if (!u) return 'U';
    return (u.email ?? u.phone ?? 'U').slice(0, 2).toUpperCase();
  });
</script>

<header class="sticky top-0 z-30 flex h-14 items-center justify-between border-b border-gray-100 bg-white/80 backdrop-blur px-4 lg:px-6">
  <!-- Mobile hamburger -->
  <button
    onclick={toggleSidebar}
    aria-label="Toggle navigation"
    class="flex h-9 w-9 items-center justify-center rounded-lg text-gray-500 hover:bg-gray-100 lg:hidden"
  >
    <svg class="h-5 w-5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
      <path stroke-linecap="round" stroke-linejoin="round" d="M4 6h16M4 12h16M4 18h16" />
    </svg>
  </button>

  <span class="hidden text-sm text-gray-400 lg:block">{today}</span>

  <div class="relative ml-auto">
    <button
      onclick={() => menuOpen = !menuOpen}
      class="flex h-9 w-9 items-center justify-center rounded-full text-sm font-bold text-white"
      style="background-color: var(--brand)"
      aria-label="User menu"
    >
      {initials()}
    </button>

    {#if menuOpen}
      <!-- svelte-ignore a11y_no_static_element_interactions -->
      <div
        class="absolute right-0 mt-2 w-44 rounded-xl border border-gray-100 bg-white shadow-lg py-1 text-sm"
        onmouseleave={() => menuOpen = false}
      >
        {#if $currentUser?.email}
          <p class="truncate px-4 py-2 text-xs text-gray-400">{$currentUser.email}</p>
          <hr class="border-gray-100" />
        {/if}
        <a href="/profile" class="block px-4 py-2 text-gray-700 hover:bg-gray-50">My profile</a>
        <button onclick={handleLogout} class="w-full text-left px-4 py-2 text-red-600 hover:bg-red-50">
          Sign out
        </button>
      </div>
    {/if}
  </div>
</header>
