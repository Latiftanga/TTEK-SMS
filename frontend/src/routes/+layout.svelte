<script lang="ts">
  import '../app.css';
  import { QueryClient, QueryClientProvider } from '@tanstack/svelte-query';
  import { onMount } from 'svelte';
  import { get } from 'svelte/store';
  import { auth } from '$lib/stores/auth';
  import { getMe } from '$lib/api/auth';
  import { theme } from '$lib/stores/theme';
  import { school } from '$lib/stores/school';
  import { getMySchoolBranding, applyBranding } from '$lib/api/schools';
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
    theme.init();

    // CSS vars reset on every page load — reapply brand colour from persisted store
    const stored = get(school);
    if (stored?.brandColor) {
      applyBranding({
        school_name: stored.name,
        short_name: stored.shortName,
        school_type: stored.schoolType ?? 'BASIC',
        motto: stored.motto ?? null,
        logo_url: stored.logoUrl ?? null,
        brand_color: stored.brandColor,
        school_code: stored.schoolCode,
      });
    }

    const storedToken = localStorage.getItem('access_token');
    if (storedToken) {
      auth.hydrate(storedToken);
      try {
        const user = await getMe();
        auth.setUser(user);

        // Fetch branding if store is empty, schoolType is missing, or logoUrl
        // looks like the old root-relative "/uploads/..." shape a prior bug
        // persisted (rather than the absolute URL the API returns today) —
        // without this, a browser that cached the broken value before the
        // fix shipped would keep showing it forever, since nothing else
        // here ever re-fetches once schoolType alone looks present.
        const logoUrlStale = !!stored?.logoUrl && !stored.logoUrl.startsWith('http');
        if ((!stored || !stored.schoolType || logoUrlStale) && !user.is_superadmin) {
          try {
            const branding = await getMySchoolBranding();
            applyBranding(branding);
            school.set({
              name: branding.school_name,
              shortName: branding.short_name ?? branding.school_name,
              subdomain: '',
              schoolCode: branding.school_code,
              schoolType: branding.school_type,
              brandColor: branding.brand_color,
              logoUrl: branding.logo_url,
              motto: branding.motto,
            });
          } catch { /* non-critical — sidebar falls back gracefully */ }
        }
      } catch {
        // getMe failed — clear the stale token so we don't loop
        auth.clearAuth();
      }
    }
  });
</script>

<QueryClientProvider client={queryClient}>
  <OfflineBanner />
  {@render children()}
</QueryClientProvider>
