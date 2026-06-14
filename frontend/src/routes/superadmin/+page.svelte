<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import { auth, currentUser } from '$lib/stores/auth';
  import { logout } from '$lib/api/auth';
  import { get } from 'svelte/store';

  onMount(() => {
    const user = get(currentUser);
    if (!user) goto('/');
  });

  async function handleLogout() {
    const rt = localStorage.getItem('refresh_token') ?? '';
    await logout(rt);
    auth.clearAuth();
    goto('/');
  }
</script>

<svelte:head><title>TTEK-SMS — Platform Admin</title></svelte:head>

<div class="min-h-screen bg-[var(--bg)] flex flex-col items-center justify-center p-8 text-center">
  <div class="mx-auto h-16 w-16 rounded-2xl bg-gray-900 dark:bg-gray-800 flex items-center
              justify-center text-white text-2xl font-black mb-6 shadow-lg">
    T
  </div>

  <h1 class="text-2xl font-bold text-[var(--fg)] mb-2">Platform Administration</h1>
  <p class="text-[var(--fg-muted)] text-sm mb-8 max-w-sm">
    The platform admin dashboard is coming soon. You can manage schools,
    users, and platform settings here.
  </p>

  <div class="flex flex-col gap-3 w-full max-w-xs">
    <div class="rounded-xl border border-[var(--border)] bg-[var(--card)] px-4 py-3 text-left">
      <p class="text-xs text-[var(--fg-muted)] mb-1">Signed in as</p>
      <p class="text-sm font-medium text-[var(--fg)]">{$currentUser?.email ?? '—'}</p>
    </div>

    <button
      onclick={handleLogout}
      class="w-full rounded-xl border border-red-200 dark:border-red-800 py-3 text-sm font-medium
             text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20 transition"
    >
      Sign out
    </button>
  </div>

  <p class="mt-12 text-xs text-[var(--fg-muted)]">TTEK-SMS by Tagnatek</p>
</div>
