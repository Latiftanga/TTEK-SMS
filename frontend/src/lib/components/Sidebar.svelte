<script lang="ts">
  import { browser } from '$app/environment';
  import { page } from '$app/stores';
  import { goto } from '$app/navigation';
  import { currentUser, auth } from '$lib/stores/auth';
  import { school } from '$lib/stores/school';
  import { userRole } from '$lib/stores/permissions';
  import { logout } from '$lib/api/auth';
  import { NAV_GROUPS, ROLE_LABELS, IC, type NavRole } from '$lib/nav';

  interface Props { open: boolean; onclose: () => void; }
  const { open, onclose }: Props = $props();

  let collapsed = $state(browser ? localStorage.getItem('sidebar_collapsed') === 'true' : false);

  function toggleCollapse() {
    collapsed = !collapsed;
    if (browser) localStorage.setItem('sidebar_collapsed', String(collapsed));
  }

  // ── Role resolution ──────────────────────────────────────────────────────────
  const isSuperadmin = $derived($currentUser?.is_superadmin ?? false);
  const role         = $derived($userRole as NavRole | null);
  const isAdmin      = $derived(isSuperadmin || role === 'admin');

  function canSee(roles?: NavRole[]): boolean {
    if (isSuperadmin || !roles) return true;
    if (!role) return false;
    return roles.includes(role);
  }

  // ── Filtered groups ──────────────────────────────────────────────────────────
  const visibleGroups = $derived(
    NAV_GROUPS
      .map(g => ({ ...g, items: g.items.filter(i => canSee(i.roles)) }))
      .filter(g => {
        if (g.heading && !isAdmin) return false; // admin-only section
        return g.items.length > 0;
      })
  );

  // ── Helpers ──────────────────────────────────────────────────────────────────
  function isActive(href: string, exact?: boolean) {
    const p = $page.url.pathname;
    return exact ? p === href : p.startsWith(href);
  }

  const schoolInitials = $derived(() => {
    const n = $school?.name ?? 'S';
    const words = n.split(' ').filter((w: string) => w.length > 1);
    return (words.length >= 2 ? words[0][0] + words[1][0] : n.slice(0, 2)).toUpperCase();
  });

  const userLabel  = $derived($currentUser?.display_name ?? $currentUser?.email ?? $currentUser?.phone ?? '—');
  const roleLabel  = $derived(
    isSuperadmin ? 'Platform Admin'
    : role ? (ROLE_LABELS[role] ?? 'Staff member')
    : 'Staff member'
  );

  async function handleLogout() {
    const rt = localStorage.getItem('refresh_token') ?? '';
    await logout(rt);
    auth.clearAuth();
    school.clear();
    userRole.reset();
    goto('/login');
  }

  const linkClass = (active: boolean) =>
    `group flex items-center rounded-lg transition-all duration-150 text-sm
     ${collapsed ? 'justify-center p-2.5' : 'gap-3 px-3 py-2'}
     ${active ? 'font-semibold' : 'font-medium text-[var(--fg-muted)] hover:bg-[var(--hover)] hover:text-[var(--fg)]'}`;

  const iconClass = (active: boolean) =>
    `h-[18px] w-[18px] shrink-0 transition-transform duration-150 ${active ? '' : 'group-hover:scale-110'}`;
</script>

<!-- Mobile backdrop -->
{#if open}
  <button
    type="button"
    class="fixed inset-0 z-30 w-full bg-black/40 backdrop-blur-sm lg:hidden border-0"
    onclick={onclose}
    aria-label="Close navigation"
  ></button>
{/if}

<aside
  class="fixed inset-y-0 left-0 z-40 flex flex-col border-r border-[var(--border)] bg-[var(--sidebar)]
         transition-all duration-200 ease-out
         {collapsed ? 'w-[64px]' : 'w-[240px]'}
         {open ? 'translate-x-0' : '-translate-x-full'}
         lg:translate-x-0 lg:static lg:z-auto"
  style="box-shadow: 1px 0 0 var(--border), 2px 0 12px rgba(0,0,0,0.04);"
>
  <!-- School header -->
  <div class="flex h-14 shrink-0 items-center border-b border-[var(--border)]
              {collapsed ? 'justify-center px-0' : 'gap-3 px-4'}">
    {#if $school?.logoUrl}
      <img src={$school.logoUrl} alt={$school.name}
           class="h-9 w-9 shrink-0 rounded-xl object-contain ring-1 ring-[var(--border)]" />
    {:else}
      <div class="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl text-sm font-bold text-white shadow-sm"
           style="background: linear-gradient(135deg, var(--brand) 0%, color-mix(in oklab, var(--brand) 70%, #7c3aed) 100%)">
        {schoolInitials()}
      </div>
    {/if}

    {#if !collapsed}
      <div class="min-w-0 flex-1">
        <p class="truncate text-[0.8125rem] font-semibold text-[var(--fg)] leading-snug" title={$school?.name}>
          {$school?.shortName ?? $school?.name ?? 'My School'}
        </p>
        <p class="truncate text-[10px] text-[var(--fg-muted)]">
          {$school?.motto ?? ($school ? 'School Management' : 'TTEK-SMS')}
        </p>
      </div>
      <button onclick={toggleCollapse} title="Collapse" aria-label="Collapse sidebar"
        class="hidden lg:flex h-6 w-6 shrink-0 items-center justify-center rounded-md transition-colors
               text-[var(--fg-subtle)] hover:bg-[var(--hover)] hover:text-[var(--fg-muted)]">
        <svg class="h-3.5 w-3.5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
          {@html IC.chevronL}
        </svg>
      </button>
    {:else}
      <button onclick={toggleCollapse} title="Expand" aria-label="Expand sidebar"
        class="hidden lg:flex h-6 w-6 shrink-0 items-center justify-center rounded-md transition-colors
               text-[var(--fg-subtle)] hover:bg-[var(--hover)] hover:text-[var(--fg-muted)]">
        <svg class="h-3.5 w-3.5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
          {@html IC.chevronR}
        </svg>
      </button>
    {/if}
  </div>

  <!-- Navigation -->
  <nav class="flex-1 overflow-y-auto py-3 {collapsed ? 'px-2' : 'px-3'}" aria-label="Main navigation">
    {#each visibleGroups as group, gi}
      {#if group.heading}
        {#if !collapsed}
          <div class="px-3 pb-1 {gi > 0 ? 'pt-5' : 'pt-3'}">
            <p class="text-[10px] font-semibold uppercase tracking-widest text-[var(--fg-subtle)]">
              {group.heading}
            </p>
          </div>
        {:else}
          <hr class="my-2 border-[var(--border)]" />
        {/if}
      {/if}

      <ul class="space-y-0.5 {gi > 0 && !group.heading ? 'mt-1' : ''}">
        {#each group.items as item}
          {@const active = isActive(item.href, item.exact)}
          <li>
            <a
              href={item.href}
              onclick={onclose}
              title={collapsed ? item.label : undefined}
              aria-current={active ? 'page' : undefined}
              class={linkClass(active)}
              style={active ? 'background-color: var(--nav-active-bg); color: var(--nav-active-color);' : ''}
            >
              <svg class={iconClass(active)}
                   fill="none" stroke="currentColor"
                   stroke-width={active ? '2.1' : '1.6'}
                   viewBox="0 0 24 24"
                   aria-hidden="true">
                {@html item.icon}
              </svg>
              {#if !collapsed}
                <span class="truncate">{item.label}</span>
              {/if}
            </a>
          </li>
        {/each}
      </ul>
    {/each}
  </nav>

  <!-- User strip -->
  <div class="shrink-0 border-t border-[var(--border)] p-2">
    {#if collapsed}
      <div class="flex flex-col items-center gap-1">
        <a href="/profile" onclick={onclose} title={userLabel}
           class="flex h-8 w-8 items-center justify-center rounded-lg text-[11px] font-bold
                  text-white transition-opacity hover:opacity-80"
           style="background: linear-gradient(135deg, var(--brand) 0%, color-mix(in oklab, var(--brand) 60%, #7c3aed) 100%)">
          {userLabel.slice(0, 2).toUpperCase()}
        </a>
        <button onclick={handleLogout} title="Sign out"
          class="flex h-8 w-8 items-center justify-center rounded-lg transition-colors
                 text-[var(--fg-muted)] hover:bg-red-50 dark:hover:bg-red-950/40 hover:text-red-500">
          <svg class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="1.6" viewBox="0 0 24 24">
            {@html IC.signOut}
          </svg>
        </button>
      </div>
    {:else}
      <div class="flex items-center gap-1.5">
        <a href="/profile" onclick={onclose}
           class="group flex min-w-0 flex-1 items-center gap-2.5 rounded-lg px-2 py-1.5
                  transition-colors hover:bg-[var(--hover)]">
          <div class="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg
                      text-[11px] font-bold text-white"
               style="background: linear-gradient(135deg, var(--brand) 0%, color-mix(in oklab, var(--brand) 60%, #7c3aed) 100%)">
            {userLabel.slice(0, 2).toUpperCase()}
          </div>
          <div class="min-w-0">
            <p class="truncate text-xs font-semibold text-[var(--fg)]">{userLabel}</p>
            <p class="text-[10px] text-[var(--fg-muted)]">{roleLabel}</p>
          </div>
        </a>
        <button onclick={handleLogout} title="Sign out"
          class="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg transition-colors
                 text-[var(--fg-muted)] hover:bg-red-50 dark:hover:bg-red-950/40 hover:text-red-500">
          <svg class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="1.6" viewBox="0 0 24 24">
            {@html IC.signOut}
          </svg>
        </button>
      </div>
    {/if}
  </div>
</aside>
