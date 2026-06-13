<script lang="ts">
  import '../app.css';
  import { QueryClient, QueryClientProvider } from '@tanstack/svelte-query';
  import { onMount } from 'svelte';
  import { auth } from '$lib/stores/auth';
  import { getMe } from '$lib/api/auth';
  import OfflineBanner from '$lib/components/OfflineBanner.svelte';

  const { children } = $props();

  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 60_000,
        retry: 1,
        refetchOnWindowFocus: false,
      },
    },
  });

  onMount(async () => {
    // Restore token from localStorage (set during login)
    const storedToken = localStorage.getItem('access_token');
    if (storedToken) {
      auth.hydrate(storedToken);
      // Silently fetch user profile — updates the store for the rest of the app
      try {
        const user = await getMe();
        auth.setUser(user);
      } catch {
        // Token may be expired — interceptor will handle refresh or redirect
      }
    }
  });
</script>

<QueryClientProvider client={queryClient}>
  <OfflineBanner />
  {@render children()}
</QueryClientProvider>
