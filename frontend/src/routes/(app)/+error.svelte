<script lang="ts">
  import { page } from '$app/stores';

  const META = {
    404: {
      label:   'Not found',
      heading: 'Page not found',
      body:    "The page you're looking for doesn't exist or may have been moved. Double-check the URL or head back to the dashboard.",
      color:   'var(--brand)',
      icon: `
        <circle cx="21" cy="21" r="13" stroke-width="2.5"/>
        <path stroke-linecap="round" stroke-width="2.5" d="M30 30 L41 41"/>
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M17 17l7 7m0-7-7 7"/>
      `,
    },
    403: {
      label:   'Access denied',
      heading: "You can't access this",
      body:    "Your account doesn't have permission to view this page. If you think this is a mistake, contact your school administrator.",
      color:   '#f59e0b',
      icon: `
        <rect x="10" y="22" width="28" height="20" rx="5" stroke-width="2.5"/>
        <path stroke-linecap="round" stroke-width="2.5" d="M16 22v-7a8 8 0 0116 0v7"/>
        <circle cx="24" cy="33" r="3" fill="currentColor"/>
        <path stroke-linecap="round" stroke-width="2.5" d="M24 34v5"/>
      `,
    },
    500: {
      label:   'Server error',
      heading: 'Something went wrong',
      body:    "An unexpected error occurred on our end. Our team has been notified. Please try again in a moment or return to the dashboard.",
      color:   '#ef4444',
      icon: `
        <circle cx="24" cy="24" r="18" stroke-width="2.5" stroke-dasharray="4 3"/>
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M27 10 19 26h8L21 42l12-22h-8z"/>
      `,
    },
    503: {
      label:   'Unavailable',
      heading: 'Service unavailable',
      body:    'The service is temporarily unavailable. We are working to restore it. Please try again shortly.',
      color:   '#8b5cf6',
      icon: `
        <rect x="8" y="10" width="32" height="10" rx="4" stroke-width="2.5"/>
        <rect x="8" y="24" width="32" height="10" rx="4" stroke-width="2.5"/>
        <circle cx="14" cy="15" r="2.5" fill="currentColor"/>
        <circle cx="14" cy="29" r="2.5" fill="currentColor"/>
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M24 38v6m-3-3 3 3 3-3"/>
      `,
    },
  } as const;

  type StatusKey = keyof typeof META;

  const status  = $derived($page.status);
  const meta    = $derived(
    META[status as StatusKey] ?? {
      label:   'Unexpected error',
      heading: 'Something went wrong',
      body:    $page.error?.message ?? 'An unexpected error occurred. Please try refreshing the page.',
      color:   'var(--brand)',
      icon:    `
        <circle cx="24" cy="24" r="18" stroke-width="2.5"/>
        <path stroke-linecap="round" stroke-width="2.5" d="M24 15v12"/>
        <circle cx="24" cy="33" r="2" fill="currentColor"/>
      `,
    }
  );
</script>

<div class="flex min-h-[72vh] flex-col items-center justify-center py-16 text-center page-enter">
  <div class="relative flex flex-col items-center">

    <!-- Icon ring -->
    <div class="relative z-10 mb-6 flex h-20 w-20 items-center justify-center rounded-2xl shadow-sm ring-1"
         style="background: color-mix(in oklab, {meta.color} 10%, transparent);
                ring-color: color-mix(in oklab, {meta.color} 22%, transparent);">
      <svg class="h-10 w-10" style="color: {meta.color}"
           fill="none" stroke="currentColor" viewBox="0 0 48 48" aria-hidden="true">
        {@html meta.icon}
      </svg>
    </div>

    <!-- Status badge -->
    <span class="relative z-10 mb-4 inline-flex items-center rounded-full px-3 py-1 text-xs font-semibold tracking-wide"
          style="background: color-mix(in oklab, {meta.color} 10%, transparent); color: {meta.color};">
      {status} &middot; {meta.label}
    </span>

    <!-- Heading -->
    <h1 class="relative z-10 mb-3 text-3xl font-bold tracking-tight text-[var(--fg)]">
      {meta.heading}
    </h1>

    <!-- Body -->
    <p class="relative z-10 mb-8 max-w-md text-balance leading-relaxed text-[var(--fg-muted)]">
      {meta.body}
    </p>

    <!-- Actions -->
    <div class="relative z-10 flex flex-wrap items-center justify-center gap-3">
      <a href="/dashboard" class="btn-primary">
        <svg class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24" aria-hidden="true">
          <path stroke-linecap="round" stroke-linejoin="round"
                d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6"/>
        </svg>
        Dashboard
      </a>
      <button onclick={() => history.back()} class="btn-ghost">
        <svg class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24" aria-hidden="true">
          <path stroke-linecap="round" stroke-linejoin="round" d="M10 19l-7-7m0 0l7-7m-7 7h18"/>
        </svg>
        Go back
      </button>
    </div>

  </div>
</div>
