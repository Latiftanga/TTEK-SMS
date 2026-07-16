<script lang="ts">
  import { browser } from '$app/environment';
  import { page } from '$app/stores';
  import { currentUser } from '$lib/stores/auth';
  import { school } from '$lib/stores/school';
  import { userRole, isClassTeacher } from '$lib/stores/permissions';
  import { NAV_GROUPS, IC, type NavRole, type SchoolType, type NavItem, type ChildNavItem } from '$lib/nav';
  import SidebarFooter from './SidebarFooter.svelte';

  interface Props { open: boolean; onclose: () => void; }
  const { open, onclose }: Props = $props();

  let collapsed = $state(browser ? localStorage.getItem('sidebar_collapsed') === 'true' : false);

  function toggleCollapse() {
    collapsed = !collapsed;
    if (browser) localStorage.setItem('sidebar_collapsed', String(collapsed));
  }

  // ── Role + school-type resolution ────────────────────────────────────────────
  const isSuperadmin = $derived($currentUser?.is_superadmin ?? false);
  const role         = $derived($userRole as NavRole | null);
  const schoolType   = $derived($school?.schoolType as SchoolType | undefined);
  const classTeacher = $derived($isClassTeacher);

  function canSee(roles: NavRole[] | undefined): boolean {
    if (isSuperadmin || !roles) return true;
    if (!role) return false;
    return roles.includes(role);
  }

  function canSeeType(types: SchoolType[] | undefined): boolean {
    if (!types || !schoolType) return true;   // no restriction, or type not yet known
    return types.includes(schoolType);
  }

  function canSeeClassTeacherOnly(flag: boolean | undefined): boolean {
    if (isSuperadmin || !flag) return true;
    return classTeacher;
  }

  const visibleGroups = $derived(
    NAV_GROUPS
      .map(g => ({
        ...g,
        items: g.items
          .filter(i => canSee(i.roles) && canSeeType(i.schoolTypes) && canSeeClassTeacherOnly(i.classTeacherOnly))
          .map(i => ({
            ...i,
            children: i.children?.filter(c => canSee(c.roles) && canSeeType(c.schoolTypes)),
          })),
      }))
      .filter(g => g.items.length > 0)
  );

  // ── Active detection ─────────────────────────────────────────────────────────
  function isActive(href: string, exact: boolean | undefined) {
    const p = $page.url.pathname;
    return exact ? p === href : p.startsWith(href);
  }

  function isChildActive(href: string, siblings: ChildNavItem[]): boolean {
    const p = $page.url.pathname;
    if (p === href) return true;
    // Only match startsWith if no sibling is a more specific match for this path
    const siblingMatch = siblings.some(s => s.href !== href && (p === s.href || p.startsWith(s.href + '/')));
    return !siblingMatch && p.startsWith(href + '/');
  }

  function isParentActive(item: NavItem): boolean {
    if (item.children?.length) {
      return item.children.some(c => {
        const p = $page.url.pathname;
        return p === c.href || p.startsWith(c.href + '/');
      });
    }
    return isActive(item.href, item.exact);
  }

  // ── Submenu open/close state (persisted) ─────────────────────────────────────
  let openHrefs = $state<string[]>((() => {
    if (!browser) return [];
    const saved = JSON.parse(localStorage.getItem('sidebar_open') || '[]') as string[];
    const path = window.location.pathname;
    for (const g of NAV_GROUPS) {
      for (const item of g.items) {
        if (item.children && !saved.includes(item.href)) {
          const hasActive = item.children.some(c => path === c.href || path.startsWith(c.href + '/'));
          if (hasActive) saved.push(item.href);
        }
      }
    }
    return saved;
  })());

  // Auto-expand parent when navigating to a child page
  $effect(() => {
    const path = $page.url.pathname;
    for (const g of NAV_GROUPS) {
      for (const item of g.items) {
        if (item.children && !openHrefs.includes(item.href)) {
          const hasActive = item.children.some(c => path === c.href || path.startsWith(c.href + '/'));
          if (hasActive) { openHrefs = [...openHrefs, item.href]; return; }
        }
      }
    }
  });

  function toggleOpen(href: string) {
    openHrefs = openHrefs.includes(href) ? openHrefs.filter(h => h !== href) : [...openHrefs, href];
    if (browser) localStorage.setItem('sidebar_open', JSON.stringify(openHrefs));
  }

  // ── Misc ─────────────────────────────────────────────────────────────────────
  const schoolInitials = $derived.by(() => {
    const n = $school?.name ?? 'S';
    const words = n.split(' ').filter((w: string) => w.length > 1);
    return (words.length >= 2 ? words[0][0] + words[1][0] : n.slice(0, 2)).toUpperCase();
  });

  const linkBase = $derived(collapsed
    ? 'group flex items-center justify-center rounded-lg p-2.5 transition-all duration-150 text-sm'
    : 'group flex w-full items-center gap-3 rounded-lg px-3 py-2 transition-all duration-150 text-sm'
  );

  function linkClass(active: boolean, full: boolean = true) {
    const base = full ? linkBase : linkBase.replace('w-full', 'flex-1 min-w-0');
    return `${base} ${active
      ? 'font-semibold'
      : 'font-medium text-[var(--fg-muted)] hover:bg-[var(--hover)] hover:text-[var(--fg)]'}`;
  }

  const iconCls = (active: boolean) =>
    `h-[18px] w-[18px] shrink-0 transition-colors duration-150 ${active ? '' : 'group-hover:text-[var(--fg)]'}`;
</script>

{#if open}
  <button type="button"
    class="fixed inset-0 z-30 w-full bg-black/40 backdrop-blur-sm lg:hidden border-0"
    onclick={onclose} aria-label="Close navigation">
  </button>
{/if}

<aside
  class="fixed inset-y-0 left-0 z-40 flex flex-col border-r border-[var(--border)] bg-[var(--sidebar)]
         transition-all duration-200 ease-out
         {collapsed ? 'w-[64px]' : 'w-[240px]'}
         {open ? 'translate-x-0' : '-translate-x-full'}
         lg:translate-x-0 lg:static lg:z-auto"
>
  <!-- ── School header ────────────────────────────────────────────────────── -->
  <div class="flex h-14 shrink-0 items-center border-b border-[var(--border)]
              {collapsed ? 'justify-center px-0' : 'gap-3 px-4'}">
    {#if $school?.logoUrl}
      <img src={$school.logoUrl} alt={$school.name}
           class="h-8 w-8 shrink-0 rounded-xl object-contain ring-1 ring-[var(--border)]" />
    {:else}
      <div class="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl text-[11px] font-bold text-white"
           style="background: linear-gradient(135deg, var(--brand) 0%, color-mix(in oklab, var(--brand) 70%, #7c3aed) 100%)">
        {schoolInitials}
      </div>
    {/if}

    {#if !collapsed}
      <div class="min-w-0 flex-1">
        <p class="truncate text-[0.8125rem] font-semibold leading-snug text-[var(--fg)]" title={$school?.name}>
          {$school?.shortName ?? $school?.name ?? 'My School'}
        </p>
        <p class="truncate text-[10px] text-[var(--fg-muted)]">
          {$school?.motto ?? 'School Management System'}
        </p>
      </div>
    {/if}
    <button onclick={toggleCollapse}
      title={collapsed ? 'Expand' : 'Collapse'} aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
      class="hidden lg:flex h-6 w-6 shrink-0 items-center justify-center rounded-md
             text-[var(--fg-subtle)] transition-colors hover:bg-[var(--hover)] hover:text-[var(--fg-muted)]">
      <svg class="h-3.5 w-3.5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
        {@html collapsed ? IC.chevronR : IC.chevronL}
      </svg>
    </button>
  </div>

  <!-- ── Navigation ───────────────────────────────────────────────────────── -->
  <nav class="flex-1 overflow-y-auto py-3 {collapsed ? 'px-2' : 'px-3'}" aria-label="Main navigation">
    {#each visibleGroups as group, gi}
      {#if group.heading}
        {#if !collapsed}
          <div class="px-3 pb-1 {gi > 0 ? 'pt-5' : 'pt-3'}">
            <p class="text-[11px] font-bold uppercase tracking-widest text-[var(--fg-subtle)]">
              {group.heading}
            </p>
          </div>
        {:else}
          <hr class="my-2 border-[var(--border)]" />
        {/if}
      {/if}

      <ul class="space-y-0.5 {gi > 0 && !group.heading ? 'mt-1' : ''}">
        {#each group.items as item}
          {@const active   = isParentActive(item)}
          {@const hasKids  = !!item.children?.length}
          {@const expanded = !collapsed && hasKids && openHrefs.includes(item.href)}
          <li class="relative">
            {#if active && !collapsed}
              <span class="pointer-events-none absolute inset-y-1 -left-3 w-[3px] rounded-r-full"
                    style="background: var(--brand)" aria-hidden="true"></span>
            {/if}
            {#if hasKids}
              <!-- Parent with submenu: link navigates, chevron toggles children -->
              {#if collapsed}
                <a href={item.href} onclick={onclose}
                   title={item.label}
                   aria-current={active ? 'page' : undefined}
                   class={linkClass(active)}
                   style={active ? 'background-color: color-mix(in oklab, var(--brand) 10%, transparent); color: var(--brand);' : ''}>
                  <svg class={iconCls(active)} fill="none" stroke="currentColor"
                       stroke-width={active ? '2.2' : '1.6'} viewBox="0 0 24 24" aria-hidden="true"
                       style={active ? 'color: var(--brand)' : ''}>
                    {@html item.icon}
                  </svg>
                </a>
              {:else}
                <div class="flex items-center gap-0.5">
                  <a href={item.href} onclick={onclose}
                     aria-current={active ? 'page' : undefined}
                     class={linkClass(active, false)}
                     style={active ? 'background-color: color-mix(in oklab, var(--brand) 10%, transparent); color: var(--brand);' : ''}>
                    <svg class={iconCls(active)} fill="none" stroke="currentColor"
                         stroke-width={active ? '2.2' : '1.6'} viewBox="0 0 24 24" aria-hidden="true"
                         style={active ? 'color: var(--brand)' : ''}>
                      {@html item.icon}
                    </svg>
                    <span class="flex-1 truncate text-left">{item.label}</span>
                  </a>
                  <button type="button" onclick={() => toggleOpen(item.href)}
                          aria-label="{expanded ? 'Collapse' : 'Expand'} {item.label} submenu"
                          aria-expanded={expanded}
                          class="flex h-8 w-8 shrink-0 items-center justify-center rounded-md
                                 text-[var(--fg-subtle)] transition-colors hover:bg-[var(--hover)] hover:text-[var(--fg)]">
                    <svg class="h-3.5 w-3.5 transition-transform duration-200 {expanded ? 'rotate-180' : ''}"
                         fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24" aria-hidden="true">
                      {@html IC.chevronD}
                    </svg>
                  </button>
                </div>
              {/if}
              <!-- Children -->
              {#if expanded}
                <ul class="mt-0.5 space-y-0.5 border-l border-[var(--border)] ml-[22px] pl-3">
                  {#each item.children ?? [] as child}
                    {@const childActive = isChildActive(child.href, item.children ?? [])}
                    <li>
                      <a href={child.href} onclick={onclose}
                         aria-current={childActive ? 'page' : undefined}
                         class="flex items-center gap-1.5 rounded-md px-2 py-1.5 transition
                                {childActive
                                  ? 'text-[0.8125rem] font-semibold'
                                  : 'text-xs font-medium text-[var(--fg-subtle)] hover:bg-[var(--hover)] hover:text-[var(--fg)]'}"
                         style={childActive ? 'color: var(--brand)' : ''}>
                        {#if childActive}
                          <span class="h-1.5 w-1.5 shrink-0 rounded-full"
                                style="background: var(--brand)" aria-hidden="true"></span>
                        {/if}
                        {child.label}
                      </a>
                    </li>
                  {/each}
                </ul>
              {/if}
            {:else}
              <!-- Regular link -->
              <a href={item.href}
                 onclick={onclose}
                 title={collapsed ? item.label : undefined}
                 aria-current={active ? 'page' : undefined}
                 class={linkClass(active)}
                 style={active
                   ? 'background-color: color-mix(in oklab, var(--brand) 10%, transparent); color: var(--brand);'
                   : ''}>
                <svg class={iconCls(active)} fill="none" stroke="currentColor"
                     stroke-width={active ? '2.2' : '1.6'} viewBox="0 0 24 24" aria-hidden="true"
                     style={active ? 'color: var(--brand)' : ''}>
                  {@html item.icon}
                </svg>
                {#if !collapsed}
                  <span class="truncate">{item.label}</span>
                {/if}
              </a>
            {/if}
          </li>
        {/each}
      </ul>
    {/each}
  </nav>

  <SidebarFooter {collapsed} {onclose} />
</aside>
