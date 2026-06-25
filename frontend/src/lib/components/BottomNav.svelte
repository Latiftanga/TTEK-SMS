<script lang="ts">
  import { page } from '$app/stores';
  import { currentUser } from '$lib/stores/auth';
  import { userRole } from '$lib/stores/permissions';
  import { IC, type NavRole } from '$lib/nav';

  interface Props { onmore: () => void; }
  const { onmore }: Props = $props();

  interface Tab {
    href:  string;
    label: string;
    icon:  string;
    exact?: boolean;
    roles?: NavRole[];
  }

  const ALL_TABS: Tab[] = [
    { href: '/dashboard',   label: 'Home',       icon: IC.dashboard,   exact: true },
    { href: '/attendance',  label: 'Attendance', icon: IC.attendance,  roles: ['teacher', 'admin', 'approver'] },
    { href: '/assessments', label: 'Scores',     icon: IC.assessments, roles: ['teacher', 'admin', 'approver'] },
    { href: '/fees',        label: 'Fees',       icon: IC.fees,        roles: ['finance', 'admin'] },
    { href: '/housing',     label: 'Housing',    icon: IC.housing,     roles: ['admin', 'housemaster'] },
    { href: '/reports',     label: 'Reports',    icon: IC.reports,     roles: ['teacher', 'admin', 'approver'] },
    { href: '/students',    label: 'Students',   icon: IC.students,    roles: ['admin'] },
  ];

  const tabs = $derived.by(() => {
    const role = $userRole as NavRole | null;
    const isSuperadmin = $currentUser?.is_superadmin ?? false;
    return ALL_TABS
      .filter(t => isSuperadmin || !t.roles || (role !== null && t.roles.includes(role)))
      .slice(0, 4);
  });

  function isActive(href: string, exact: boolean | undefined) {
    const p = $page.url.pathname;
    return exact ? p === href : p.startsWith(href);
  }
</script>

<nav
  class="fixed bottom-0 left-0 right-0 z-50 lg:hidden bg-[var(--card)]"
  style="
    padding-bottom: env(safe-area-inset-bottom);
    box-shadow: 0 -1px 0 0 var(--border), 0 -8px 24px -4px rgba(0,0,0,0.08);
  "
  aria-label="Main navigation"
>
  <div class="flex h-[62px] items-center px-2">

    {#each tabs as tab (tab.href)}
      {@const active = isActive(tab.href, tab.exact)}
      <a
        href={tab.href}
        aria-current={active ? 'page' : undefined}
        class="flex flex-1 flex-col items-center justify-center gap-1 py-2 select-none"
      >
        <div
          class="flex h-8 w-14 items-center justify-center rounded-2xl transition-all duration-200"
          style={active ? 'background-color: rgba(var(--brand-rgb), 0.13)' : ''}
        >
          <svg
            class="transition-all duration-200"
            style="width: 22px; height: 22px; color: {active ? 'var(--brand)' : 'var(--fg-muted)'};"
            fill="none"
            stroke="currentColor"
            stroke-width={active ? '2.2' : '1.6'}
            viewBox="0 0 24 24"
            aria-hidden="true"
          >
            {@html tab.icon}
          </svg>
        </div>
        <span
          class="text-[10px] font-semibold leading-none transition-colors duration-200"
          style="color: {active ? 'var(--brand)' : 'var(--fg-muted)'}"
        >
          {tab.label}
        </span>
      </a>
    {/each}

    <!-- More — opens the full sidebar -->
    <button
      onclick={onmore}
      aria-label="More options"
      class="flex flex-1 cursor-pointer flex-col items-center justify-center gap-1 py-2 select-none"
    >
      <div class="flex h-8 w-14 items-center justify-center rounded-2xl transition-all duration-200
                  hover:bg-[var(--bg)]">
        <svg
          style="width: 22px; height: 22px; color: var(--fg-muted)"
          fill="currentColor"
          viewBox="0 0 24 24"
          aria-hidden="true"
        >
          <circle cx="5" cy="12" r="1.5"/><circle cx="12" cy="12" r="1.5"/><circle cx="19" cy="12" r="1.5"/>
        </svg>
      </div>
      <span class="text-[10px] font-semibold leading-none" style="color: var(--fg-muted)">More</span>
    </button>

  </div>
</nav>
