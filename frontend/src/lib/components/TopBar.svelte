<script lang="ts">
  import { goto } from '$app/navigation';
  import { createQuery } from '@tanstack/svelte-query';
  import ThemeToggle from './ThemeToggle.svelte';
  import { school } from '$lib/stores/school';
  import { auth, currentUser } from '$lib/stores/auth';
  import { logout } from '$lib/api/auth';
  import { getCurrentYear } from '$lib/api/academic';

  interface Props { toggleSidebar: () => void; }
  const { toggleSidebar }: Props = $props();

  const today = new Date().toLocaleDateString('en-GH', {
    weekday: 'short', day: 'numeric', month: 'short', year: 'numeric',
  });

  const schoolInitials = $derived.by(() => {
    const n = $school?.name ?? 'S';
    const words = n.split(' ').filter((w: string) => w.length > 1);
    return (words.length >= 2 ? words[0][0] + words[1][0] : n.slice(0, 2)).toUpperCase();
  });

  const userInitials = $derived.by(() => {
    const name = $currentUser?.display_name;
    if (name) {
      const parts = name.trim().split(' ').filter(Boolean);
      return parts.length >= 2
        ? (parts[0][0] + parts[parts.length - 1][0]).toUpperCase()
        : name.slice(0, 2).toUpperCase();
    }
    const email = $currentUser?.email;
    if (email) return email[0].toUpperCase();
    return 'U';
  });

  const displayLabel = $derived.by(() =>
    $currentUser?.display_name
    ?? $currentUser?.email
    ?? $currentUser?.phone
    ?? 'Account'
  );

  const subLabel = $derived.by(() => {
    if ($currentUser?.is_superadmin) return 'Platform Admin';
    return $school?.name ?? null;
  });

  const yearQ = createQuery({ queryKey: ['current-year'], queryFn: getCurrentYear, staleTime: 5 * 60_000 });
  const currentTerm = $derived(($yearQ.data?.terms ?? []).find(t => t.is_current));

  let menuOpen = $state(false);

  function toggleMenu() { menuOpen = !menuOpen; }

  function closeMenu() { menuOpen = false; }

  async function handleLogout() {
    closeMenu();
    const refreshToken = localStorage.getItem('refresh_token') ?? '';
    await logout(refreshToken);
    auth.clearAuth();
    school.clear();
    goto('/');
  }

  function handleKey(e: KeyboardEvent) {
    if (e.key === 'Escape') closeMenu();
  }
</script>

<svelte:window onkeydown={handleKey} />

<!-- svelte-ignore a11y_no_static_element_interactions -->
{#if menuOpen}
  <div class="fixed inset-0 z-30" onclick={closeMenu} role="none"></div>
{/if}

<header class="sticky top-0 z-40 flex h-14 items-center justify-between
               bg-[var(--card)] px-4 lg:px-6"
        style="padding-top: env(safe-area-inset-top); box-shadow: 0 1px 0 var(--border), 0 4px 16px rgba(0,0,0,0.06);">

  <!-- Mobile: school identity -->
  <div class="flex items-center gap-2.5 lg:hidden">
    {#if $school?.logoUrl}
      <img src={$school.logoUrl} alt={$school.name}
           class="h-8 w-8 rounded-lg object-contain ring-1 ring-[var(--border)]" />
    {:else}
      <div class="flex h-8 w-8 items-center justify-center rounded-lg text-xs font-bold text-white"
           style="background-color: var(--brand)">
        {schoolInitials}
      </div>
    {/if}
    <p class="truncate text-sm font-bold text-[var(--fg)] max-w-[160px]"
       title={$school?.name}>
      {$school?.shortName ?? $school?.name ?? 'My School'}
    </p>
  </div>

  <!-- Desktop: academic context + date -->
  <div class="hidden items-center gap-3 lg:flex">
    {#if $yearQ.data && currentTerm}
      <div class="flex items-center gap-2 rounded-lg border border-[var(--border)] px-3 py-1.5">
        <svg class="h-3.5 w-3.5 shrink-0" fill="none" stroke="currentColor" stroke-width="2"
             viewBox="0 0 24 24" style="color: var(--brand)">
          <path stroke-linecap="round" stroke-linejoin="round"
            d="M6.75 3v2.25M17.25 3v2.25M3 18.75V7.5a2.25 2.25 0 012.25-2.25h13.5A2.25
               2.25 0 0121 7.5v11.25m-18 0A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0
               0021 18.75m-18 0v-7.5A2.25 2.25 0 015.25 9h13.5A2.25 2.25 0 0121 11.25v7.5"/>
        </svg>
        <span class="text-xs font-semibold text-[var(--fg)]">{currentTerm.name}</span>
        <span class="text-[var(--fg-subtle)]">·</span>
        <span class="text-xs text-[var(--fg-muted)]">{$yearQ.data.name}</span>
      </div>
    {/if}
    <span class="text-sm text-[var(--fg-muted)]">{today}</span>
  </div>

  <!-- Mobile: term chip -->
  {#if $yearQ.data && currentTerm}
    <div class="flex items-center gap-1.5 rounded-lg border border-[var(--border)] px-2.5 py-1 lg:hidden">
      <svg class="h-3 w-3 shrink-0" fill="none" stroke="currentColor" stroke-width="2"
           viewBox="0 0 24 24" style="color: var(--brand)">
        <path stroke-linecap="round" stroke-linejoin="round"
          d="M6.75 3v2.25M17.25 3v2.25M3 18.75V7.5a2.25 2.25 0 012.25-2.25h13.5A2.25
             2.25 0 0121 7.5v11.25m-18 0A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0
             0021 18.75m-18 0v-7.5A2.25 2.25 0 015.25 9h13.5A2.25 2.25 0 0121 11.25v7.5"/>
      </svg>
      <span class="text-[11px] font-semibold text-[var(--fg)]">{currentTerm.name}</span>
      <span class="text-[10px] text-[var(--fg-muted)]">{$yearQ.data.name}</span>
    </div>
  {/if}

  <!-- Right side -->
  <div class="ml-auto flex items-center gap-2">
    <ThemeToggle />

    <!-- User menu -->
    <div class="relative">
      <button
        onclick={toggleMenu}
        class="flex items-center gap-2 rounded-xl px-2 py-1.5 transition
               hover:bg-[var(--hover)] cursor-pointer"
        aria-expanded={menuOpen}
        aria-haspopup="true"
      >
        <!-- Avatar -->
        <div class="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl
                    text-xs font-bold text-white select-none"
             style="background: linear-gradient(135deg, var(--brand) 0%, color-mix(in oklab, var(--brand) 60%, #7c3aed) 100%)">
          {userInitials}
        </div>
        <!-- Name — desktop only -->
        <div class="hidden lg:block text-left">
          <p class="text-sm font-medium text-[var(--fg)] leading-tight max-w-[140px] truncate">
            {displayLabel}
          </p>
          {#if subLabel}
            <p class="text-xs text-[var(--fg-muted)] leading-tight truncate max-w-[140px]">
              {subLabel}
            </p>
          {/if}
        </div>
        <!-- Chevron — desktop only -->
        <svg class="hidden lg:block h-4 w-4 text-[var(--fg-muted)] transition-transform duration-200
                    {menuOpen ? 'rotate-180' : ''}"
             fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
          <path stroke-linecap="round" stroke-linejoin="round" d="M19 9l-7 7-7-7"/>
        </svg>
      </button>

      <!-- Dropdown -->
      {#if menuOpen}
        <div class="absolute right-0 top-full mt-1.5 w-56 rounded-xl border border-[var(--border)]
                    bg-[var(--card)] overflow-hidden z-50"
             style="box-shadow: var(--shadow-xl);">

          <!-- User identity header -->
          <div class="px-4 py-3 border-b border-[var(--border)]">
            <p class="text-sm font-semibold text-[var(--fg)] truncate">{displayLabel}</p>
            {#if $currentUser?.email && $currentUser.display_name}
              <p class="text-xs text-[var(--fg-muted)] truncate mt-0.5">{$currentUser.email}</p>
            {/if}
          </div>

          <!-- Menu items -->
          <div class="py-1">
            <a href="/profile"
               onclick={closeMenu}
               class="flex items-center gap-3 px-4 py-2.5 text-sm text-[var(--fg)]
                      hover:bg-[var(--hover)] transition cursor-pointer">
              <svg class="h-4 w-4 text-[var(--fg-muted)]" fill="none" viewBox="0 0 24 24"
                   stroke="currentColor" stroke-width="2">
                <path stroke-linecap="round" stroke-linejoin="round"
                  d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"/>
              </svg>
              My Profile
            </a>

            <a href="/change-password"
               onclick={closeMenu}
               class="flex items-center gap-3 px-4 py-2.5 text-sm text-[var(--fg)]
                      hover:bg-[var(--hover)] transition cursor-pointer">
              <svg class="h-4 w-4 text-[var(--fg-muted)]" fill="none" viewBox="0 0 24 24"
                   stroke="currentColor" stroke-width="2">
                <path stroke-linecap="round" stroke-linejoin="round"
                  d="M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0
                     01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1121 9z"/>
              </svg>
              Change Password
            </a>
          </div>

          <div class="border-t border-[var(--border)] py-1">
            <button
              onclick={handleLogout}
              class="flex w-full items-center gap-3 px-4 py-2.5 text-sm text-red-500
                     hover:bg-[var(--hover)] transition cursor-pointer"
            >
              <svg class="h-4 w-4" fill="none" viewBox="0 0 24 24"
                   stroke="currentColor" stroke-width="2">
                <path stroke-linecap="round" stroke-linejoin="round"
                  d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0
                     01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1"/>
              </svg>
              Sign out
            </button>
          </div>
        </div>
      {/if}
    </div>
  </div>
</header>
