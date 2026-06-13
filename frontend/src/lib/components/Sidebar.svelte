<script lang="ts">
  import { page } from '$app/stores';
  import { currentUser } from '$lib/stores/auth';

  interface Props { open: boolean; onclose: () => void; }
  const { open, onclose }: Props = $props();

  interface NavItem {
    href: string;
    label: string;
    icon: string;
    exact?: boolean;
  }

  const coreItems: NavItem[] = [
    { href: '/dashboard', label: 'Dashboard', icon: '🏠', exact: true },
    { href: '/students', label: 'Students', icon: '👩‍🎓' },
    { href: '/attendance', label: 'Attendance', icon: '📋' },
    { href: '/scores', label: 'Scores', icon: '✏️' },
    { href: '/fees', label: 'Fees', icon: '💰' },
    { href: '/reports', label: 'Report Cards', icon: '📄' },
  ];

  const adminItems: NavItem[] = [
    { href: '/admin/academic', label: 'Academic Setup', icon: '📅' },
    { href: '/admin/structure', label: 'Classes & Subjects', icon: '🏫' },
    { href: '/admin/staff', label: 'Staff', icon: '👩‍🏫' },
    { href: '/admin/grading', label: 'Grading', icon: '📊' },
    { href: '/admin/fees-setup', label: 'Fee Setup', icon: '⚙️' },
    { href: '/admin/sms', label: 'SMS Config', icon: '📱' },
  ];

  const isAdmin = $derived(() => $currentUser?.is_superadmin);

  function isActive(href: string, exact?: boolean): boolean {
    const current = $page.url.pathname;
    return exact ? current === href : current.startsWith(href);
  }

  function itemClass(href: string, exact?: boolean) {
    const active = isActive(href, exact);
    return `flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition-colors
      ${active
        ? 'text-white'
        : 'text-gray-600 hover:bg-gray-100 hover:text-gray-900'}`;
  }
</script>

<!-- Backdrop (mobile only) -->
{#if open}
  <!-- svelte-ignore a11y_click_events_have_key_events a11y_no_static_element_interactions -->
  <div
    class="fixed inset-0 z-30 bg-black/30 lg:hidden"
    onclick={onclose}
  ></div>
{/if}

<aside
  class="fixed inset-y-0 left-0 z-40 flex w-60 flex-col border-r border-gray-100 bg-white transition-transform duration-200
         {open ? 'translate-x-0' : '-translate-x-full'} lg:translate-x-0 lg:static lg:z-auto"
>
  <!-- School identity -->
  <div class="flex h-14 items-center gap-3 border-b border-gray-100 px-4">
    <span
      class="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-xs font-bold text-white"
      style="background-color: var(--brand)"
    >S</span>
    <span class="truncate text-sm font-semibold text-gray-800">My School</span>
  </div>

  <!-- Navigation -->
  <nav class="flex-1 overflow-y-auto px-3 py-4 space-y-0.5">
    {#each coreItems as item}
      <a
        href={item.href}
        class={itemClass(item.href, item.exact)}
        style={isActive(item.href, item.exact) ? 'background-color: var(--brand)' : ''}
        onclick={onclose}
      >
        <span class="text-base">{item.icon}</span>
        {item.label}
      </a>
    {/each}

    {#if isAdmin()}
      <div class="mt-4 mb-1 px-3 text-[10px] font-semibold uppercase tracking-widest text-gray-400">
        Administration
      </div>
      {#each adminItems as item}
        <a
          href={item.href}
          class={itemClass(item.href)}
          style={isActive(item.href) ? 'background-color: var(--brand)' : ''}
          onclick={onclose}
        >
          <span class="text-base">{item.icon}</span>
          {item.label}
        </a>
      {/each}
    {/if}
  </nav>

  <!-- Bottom: version -->
  <div class="border-t border-gray-100 px-4 py-3 text-[10px] text-gray-300">
    TTEK-SMS v0.1
  </div>
</aside>
