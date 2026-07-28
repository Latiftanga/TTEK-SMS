<script lang="ts">
  import { page } from '$app/stores';
  import { createQuery } from '@tanstack/svelte-query';
  import { currentUser } from '$lib/stores/auth';
  import { school } from '$lib/stores/school';
  import { getMySchool } from '$lib/api/schools';
  import { userRole, isClassTeacher } from '$lib/stores/permissions';
  import { NAV_GROUPS, type NavItem, type NavRole, type SchoolType } from '$lib/nav';

  interface Props { onmore: () => void; }
  const { onmore }: Props = $props();

  type Tab = Omit<NavItem, 'children'>;

  // Shorter labels for the cramped mobile tab bar — falls back to the sidebar label.
  const MOBILE_LABELS: Partial<Record<string, string>> = {
    '/dashboard':   'Home',
    '/assessments': 'Scores',
    '/reports':     'Reports',
  };

  // Curated subset of NAV_GROUPS eligible for the mobile tab bar — deliberately excludes
  // config-heavy admin pages (School Setup, Academic, Transfers, Staff) that only make
  // sense from the full sidebar ("More"), not as a quick daily-work tab.
  const MOBILE_HREFS = new Set([
    '/dashboard', '/attendance', '/assessments', '/fees', '/housing', '/reports', '/students',
  ]);

  // Top-level items plus any nested child that carries its own icon — a child
  // without an icon (e.g. Grading Scales) isn't meant for the tab bar, only
  // reachable via "More" → the full sidebar.
  const ALL_TABS: Tab[] = NAV_GROUPS.flatMap(g => g.items)
    .flatMap((i): Tab[] => [
      { href: i.href, label: i.label, icon: i.icon, exact: i.exact, roles: i.roles, schoolTypes: i.schoolTypes,
        requiresBoarding: i.requiresBoarding, classTeacherOnly: i.classTeacherOnly },
      ...(i.children ?? [])
        .filter((c): c is typeof c & { icon: string } => !!c.icon)
        .map(c => ({ href: c.href, label: c.label, icon: c.icon, roles: c.roles, schoolTypes: c.schoolTypes })),
    ])
    .filter(t => MOBILE_HREFS.has(t.href))
    .map(t => ({ ...t, label: MOBILE_LABELS[t.href] ?? t.label }));

  // The 4 most useful tabs per role — in priority order.
  // Tabs not listed here bubble to the end and may end up behind "More".
  const MOBILE_ORDER: Partial<Record<NavRole, string[]>> = {
    teacher:     ['/dashboard', '/attendance', '/assessments', '/reports'],
    approver:    ['/dashboard', '/attendance', '/assessments', '/reports'],
    admin:       ['/dashboard', '/students',   '/attendance',  '/fees'],
    finance:     ['/dashboard', '/fees',       '/students'],
    housemaster: ['/dashboard', '/housing',    '/students'],
  };

  function isActive(href: string, exact: boolean | undefined) {
    const p = $page.url.pathname;
    return exact ? p === href : p.startsWith(href);
  }

  // has_boarding isn't in the lightweight `school` store (branding only) — fetched
  // separately, deduped via TanStack Query against the same ['my-school'] key
  // Sidebar.svelte and the /housing page itself use.
  const schoolQ = createQuery({
    queryKey: ['my-school'], queryFn: getMySchool, staleTime: 60_000,
    enabled: () => !($currentUser?.is_superadmin ?? false) && !!$userRole,
  });

  const eligible = $derived.by(() => {
    const role       = $userRole as NavRole | null;
    const isSuperadmin = $currentUser?.is_superadmin ?? false;
    const sType      = $school?.schoolType as SchoolType | undefined;
    const hasBoarding = $schoolQ.data?.has_boarding as boolean | undefined;
    const classTeacherOk = isSuperadmin || $isClassTeacher;
    return ALL_TABS.filter(t => {
      const roleOk = isSuperadmin || !t.roles || (role !== null && t.roles.includes(role));
      const typeOk = !t.schoolTypes || !sType || t.schoolTypes.includes(sType);
      const boardingOk = !t.requiresBoarding || isSuperadmin || hasBoarding === undefined || hasBoarding;
      return roleOk && typeOk && boardingOk && (!t.classTeacherOnly || classTeacherOk);
    });
  });

  const tabs = $derived.by(() => {
    const role = $userRole as NavRole | null;
    const order = role ? (MOBILE_ORDER[role] ?? null) : null;
    if (order) {
      const prioritised = order.flatMap(href => {
        const t = eligible.find(tab => tab.href === href);
        return t ? [t] : [];
      });
      const rest = eligible.filter(t => !order.includes(t.href));
      return [...prioritised, ...rest].slice(0, 4);
    }
    return eligible.slice(0, 4);
  });

  // Highlight "More" when the active page is hidden behind it
  const moreIsActive = $derived.by(() => {
    const shown = new Set(tabs.map(t => t.href));
    return eligible.filter(t => !shown.has(t.href)).some(t => isActive(t.href, t.exact));
  });
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
            fill="none" stroke="currentColor"
            stroke-width={active ? '2.2' : '1.6'}
            viewBox="0 0 24 24" aria-hidden="true"
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
      <div class="relative flex h-8 w-14 items-center justify-center rounded-2xl transition-all duration-200
                  hover:bg-[var(--bg)]">
        <svg
          style="width: 22px; height: 22px; color: {moreIsActive ? 'var(--brand)' : 'var(--fg-muted)'}"
          fill="currentColor" viewBox="0 0 24 24" aria-hidden="true"
        >
          <circle cx="5" cy="12" r="1.5"/><circle cx="12" cy="12" r="1.5"/><circle cx="19" cy="12" r="1.5"/>
        </svg>
        {#if moreIsActive}
          <span class="absolute right-2.5 top-1 h-2 w-2 rounded-full"
                style="background: var(--brand)" aria-hidden="true"></span>
        {/if}
      </div>
      <span class="text-[10px] font-semibold leading-none"
            style="color: {moreIsActive ? 'var(--brand)' : 'var(--fg-muted)'}">More</span>
    </button>

  </div>
</nav>
