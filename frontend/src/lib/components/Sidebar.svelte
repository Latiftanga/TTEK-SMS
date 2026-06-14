<script lang="ts">
  import { browser } from '$app/environment';
  import { page } from '$app/stores';
  import { goto } from '$app/navigation';
  import { currentUser, auth } from '$lib/stores/auth';
  import { school } from '$lib/stores/school';
  import { isSchoolAdmin } from '$lib/stores/permissions';
  import { logout } from '$lib/api/auth';

  interface Props { open: boolean; onclose: () => void; }
  const { open, onclose }: Props = $props();

  let collapsed = $state(browser ? localStorage.getItem('sidebar_collapsed') === 'true' : false);

  function toggleCollapse() {
    collapsed = !collapsed;
    if (browser) localStorage.setItem('sidebar_collapsed', String(collapsed));
  }

  // ── Icons (Heroicons outline, 24 × 24) ────────────────────────────────────
  const ic = {
    dashboard:   `<path stroke-linecap="round" stroke-linejoin="round" d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6"/>`,
    students:    `<path stroke-linecap="round" stroke-linejoin="round" d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z"/>`,
    attendance:  `<path stroke-linecap="round" stroke-linejoin="round" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4"/>`,
    scores:      `<path stroke-linecap="round" stroke-linejoin="round" d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z"/>`,
    fees:        `<path stroke-linecap="round" stroke-linejoin="round" d="M3 10h18M7 15h1m4 0h1m-7 4h12a3 3 0 003-3V8a3 3 0 00-3-3H6a3 3 0 00-3 3v8a3 3 0 003 3z"/>`,
    reports:     `<path stroke-linecap="round" stroke-linejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/>`,
    academic:    `<path stroke-linecap="round" stroke-linejoin="round" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"/>`,
    structure:   `<path stroke-linecap="round" stroke-linejoin="round" d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4"/>`,
    staff:       `<path stroke-linecap="round" stroke-linejoin="round" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z"/>`,
    grading:     `<path stroke-linecap="round" stroke-linejoin="round" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"/>`,
    feeSetup:    `<path stroke-linecap="round" stroke-linejoin="round" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"/><path stroke-linecap="round" stroke-linejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"/>`,
    sms:         `<path stroke-linecap="round" stroke-linejoin="round" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"/>`,
    signOut:     `<path stroke-linecap="round" stroke-linejoin="round" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1"/>`,
    chevronLeft: `<path stroke-linecap="round" stroke-linejoin="round" d="M15.75 19.5 8.25 12l7.5-7.5"/>`,
    chevronRight:`<path stroke-linecap="round" stroke-linejoin="round" d="M8.25 4.5l7.5 7.5-7.5 7.5"/>`,
  };

  const mainNav = [
    { href: '/dashboard', label: 'Dashboard',    icon: ic.dashboard,  exact: true },
    { href: '/students',  label: 'Students',     icon: ic.students  },
    { href: '/attendance',label: 'Attendance',   icon: ic.attendance},
    { href: '/scores',    label: 'Scores',       icon: ic.scores    },
    { href: '/fees',      label: 'Fees',         icon: ic.fees      },
    { href: '/reports',   label: 'Report Cards', icon: ic.reports   },
  ];

  const adminNav = [
    { href: '/admin/academic',   label: 'Academic Setup',     icon: ic.academic  },
    { href: '/admin/structure',  label: 'Classes & Subjects', icon: ic.structure },
    { href: '/admin/staff',      label: 'Staff',              icon: ic.staff     },
    { href: '/admin/grading',    label: 'Grading Scales',     icon: ic.grading   },
    { href: '/admin/fees-setup', label: 'Fee Structure',      icon: ic.feeSetup  },
    { href: '/admin/sms',        label: 'SMS Config',         icon: ic.sms       },
  ];

  const showAdmin = $derived(() => $isSchoolAdmin || ($currentUser?.is_superadmin ?? false));

  const schoolInitials = $derived(() => {
    const n = $school?.name ?? 'S';
    const words = n.split(' ').filter((w: string) => w.length > 1);
    return (words.length >= 2 ? words[0][0] + words[1][0] : n.slice(0, 2)).toUpperCase();
  });

  const userLabel = $derived(() => $currentUser?.email ?? $currentUser?.phone ?? '—');

  function isActive(href: string, exact?: boolean) {
    const p = $page.url.pathname;
    return exact ? p === href : p.startsWith(href);
  }

  async function handleLogout() {
    const rt = localStorage.getItem('refresh_token') ?? '';
    await logout(rt);
    auth.clearAuth();
    school.clear();
    goto('/login');
  }
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
  class="fixed inset-y-0 left-0 z-40 flex flex-col
         border-r border-[var(--border)] bg-[var(--card)]
         transition-all duration-200 ease-out
         {collapsed ? 'w-16' : 'w-64'}
         {open ? 'translate-x-0' : '-translate-x-full'}
         lg:translate-x-0 lg:static lg:z-auto"
  style="box-shadow: var(--shadow-md);"
>
  <!-- ── School header ──────────────────────────────────────────────────── -->
  <div class="flex h-14 shrink-0 items-center border-b border-[var(--border)]
              {collapsed ? 'flex-col justify-center gap-1 py-2' : 'gap-3 px-4'}">
    <!-- Logo / initials -->
    {#if $school?.logoUrl}
      <img src={$school.logoUrl} alt={$school.name}
           class="h-8 w-8 shrink-0 rounded-lg object-contain ring-1 ring-[var(--border)]" />
    {:else}
      <div class="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-sm font-bold text-white"
           style="background-color: var(--brand)">
        {schoolInitials()}
      </div>
    {/if}

    {#if !collapsed}
      <!-- School name + motto -->
      <div class="min-w-0 flex-1">
        <p class="truncate text-sm font-semibold text-[var(--fg)] leading-snug" title={$school?.name}>
          {$school?.shortName ?? $school?.name ?? 'My School'}
        </p>
        <p class="truncate text-[10px] text-[var(--fg-muted)]">
          {$school?.motto ?? ($school ? 'School Management' : 'TTEK-SMS')}
        </p>
      </div>
    {/if}

    <!-- Collapse / expand toggle -->
    <button
      onclick={toggleCollapse}
      title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
      aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
      class="flex h-6 w-6 shrink-0 cursor-pointer items-center justify-center rounded-md transition-colors
             text-[var(--fg-muted)] hover:bg-[var(--bg)] hover:text-[var(--fg)] lg:flex hidden"
    >
      <svg class="h-3.5 w-3.5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
        {@html collapsed ? ic.chevronRight : ic.chevronLeft}
      </svg>
    </button>
  </div>

  <!-- ── Navigation ─────────────────────────────────────────────────────── -->
  <nav class="flex-1 overflow-y-auto py-3 space-y-0.5
              {collapsed ? 'px-1.5' : 'px-2.5'}">

    {#each mainNav as item}
      {@const active = isActive(item.href, item.exact)}
      <a
        href={item.href}
        onclick={onclose}
        title={collapsed ? item.label : undefined}
        aria-current={active ? 'page' : undefined}
        class="group flex items-center rounded-lg transition-all duration-150
               {collapsed ? 'justify-center py-2' : 'gap-2.5 py-2 text-sm'}
               {active
                 ? 'font-semibold pl-2.5 pr-3 border-l-[3px]'
                 : 'font-medium pl-3 pr-3 border-l-[3px] border-transparent text-[var(--fg-muted)] hover:bg-[var(--bg)] hover:text-[var(--fg)]'}"
        style={active
          ? `background-color: var(--nav-active-bg); color: var(--nav-active-color); border-color: var(--nav-active-color)`
          : ''}
      >
        <svg class="h-[18px] w-[18px] shrink-0 transition-transform duration-150
                    {active ? '' : 'group-hover:scale-110'}"
             fill="none" stroke="currentColor" stroke-width={active ? '2' : '1.6'} viewBox="0 0 24 24">
          {@html item.icon}
        </svg>
        {#if !collapsed}
          <span class="truncate">{item.label}</span>
        {/if}
      </a>
    {/each}

    <!-- Admin section -->
    {#if showAdmin()}
      {#if collapsed}
        <hr class="my-2 border-[var(--border)]" />
      {:else}
        <div class="px-3 pb-1 pt-5">
          <p class="text-[10px] font-semibold uppercase tracking-widest text-[var(--fg-muted)]">
            Administration
          </p>
        </div>
      {/if}

      {#each adminNav as item}
        {@const active = isActive(item.href)}
        <a
          href={item.href}
          onclick={onclose}
          title={collapsed ? item.label : undefined}
          aria-current={active ? 'page' : undefined}
          class="group flex items-center rounded-xl transition-all duration-150
                 {collapsed ? 'justify-center py-2.5' : 'gap-3 py-2.5 text-sm'}
                 {active
                   ? 'font-semibold pl-2.5 pr-3 border-l-[3px]'
                   : 'font-medium pl-3 pr-3 border-l-[3px] border-transparent text-[var(--fg-muted)] hover:bg-[var(--bg)] hover:text-[var(--fg)]'}"
          style={active
            ? `background-color: var(--nav-active-bg); color: var(--nav-active-color); border-color: var(--nav-active-color)`
            : ''}
        >
          <svg class="h-[18px] w-[18px] shrink-0 transition-transform duration-150
                      {active ? '' : 'group-hover:scale-110'}"
               fill="none" stroke="currentColor" stroke-width={active ? '2' : '1.6'} viewBox="0 0 24 24">
            {@html item.icon}
          </svg>
          {#if !collapsed}
            <span class="truncate">{item.label}</span>
          {/if}
        </a>
      {/each}
    {/if}
  </nav>

  <!-- ── User strip ─────────────────────────────────────────────────────── -->
  <div class="shrink-0 border-t border-[var(--border)] p-2.5">
    {#if collapsed}
      <!-- Collapsed: stacked icon buttons -->
      <div class="flex flex-col items-center gap-1">
        <a href="/profile" onclick={onclose} title="View profile"
           class="flex h-8 w-8 items-center justify-center rounded-lg text-[11px] font-bold
                  text-white transition-opacity hover:opacity-80"
           style="background-color: var(--brand)">
          {userLabel().slice(0, 2).toUpperCase()}
        </a>
        <button onclick={handleLogout} title="Sign out"
                class="flex h-7 w-7 cursor-pointer items-center justify-center rounded-lg transition-colors
                       text-[var(--fg-muted)] hover:bg-red-50 dark:hover:bg-red-950/40 hover:text-red-500">
          <svg class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="1.6" viewBox="0 0 24 24">
            {@html ic.signOut}
          </svg>
        </button>
      </div>
    {:else}
      <!-- Expanded: full user row -->
      <div class="flex items-center gap-2 rounded-xl px-1 py-1">
        <a href="/profile" onclick={onclose} title="View profile"
           class="flex min-w-0 flex-1 items-center gap-2.5 rounded-lg px-1.5 py-1.5
                  transition-colors hover:bg-[var(--bg)]">
          <div class="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg
                      text-[11px] font-bold text-white"
               style="background-color: var(--brand)">
            {userLabel().slice(0, 2).toUpperCase()}
          </div>
          <div class="min-w-0">
            <p class="truncate text-xs font-semibold text-[var(--fg)]">{userLabel()}</p>
            <p class="text-[10px] text-[var(--fg-muted)]">
              {$currentUser?.is_superadmin ? 'Platform admin' : 'Staff member'}
            </p>
          </div>
        </a>
        <button onclick={handleLogout} title="Sign out"
                class="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg transition-colors
                       text-[var(--fg-muted)] hover:bg-red-50 dark:hover:bg-red-950/40 hover:text-red-500">
          <svg class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="1.6" viewBox="0 0 24 24">
            {@html ic.signOut}
          </svg>
        </button>
      </div>
    {/if}
  </div>
</aside>
