<script lang="ts">
  import { page } from '$app/stores';

  interface Props { onmore: () => void; }
  const { onmore }: Props = $props();

  const ic = {
    dashboard:  `<path stroke-linecap="round" stroke-linejoin="round" d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6"/>`,
    attendance: `<path stroke-linecap="round" stroke-linejoin="round" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4"/>`,
    scores:     `<path stroke-linecap="round" stroke-linejoin="round" d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z"/>`,
    fees:       `<path stroke-linecap="round" stroke-linejoin="round" d="M3 10h18M7 15h1m4 0h1m-7 4h12a3 3 0 003-3V8a3 3 0 00-3-3H6a3 3 0 00-3 3v8a3 3 0 003 3z"/>`,
    menu:       `<circle cx="5" cy="12" r="1.5" fill="currentColor"/><circle cx="12" cy="12" r="1.5" fill="currentColor"/><circle cx="19" cy="12" r="1.5" fill="currentColor"/>`,
  };

  const tabs = [
    { href: '/dashboard', label: 'Home',       icon: ic.dashboard,  exact: true },
    { href: '/attendance',label: 'Attendance', icon: ic.attendance              },
    { href: '/scores',    label: 'Scores',     icon: ic.scores                  },
    { href: '/fees',      label: 'Fees',       icon: ic.fees                    },
  ];

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

    {#each tabs as tab}
      {@const active = isActive(tab.href, tab.exact)}
      <a
        href={tab.href}
        aria-current={active ? 'page' : undefined}
        class="flex flex-1 flex-col items-center justify-center gap-1 py-2 select-none"
      >
        <!-- Pill capsule wrapping the icon -->
        <div
          class="flex h-8 w-14 items-center justify-center rounded-2xl transition-all duration-200"
          style={active ? 'background-color: rgba(var(--brand-rgb), 0.13)' : ''}
        >
          <svg
            class="transition-all duration-200"
            style="
              width: 22px; height: 22px;
              color: {active ? 'var(--brand)' : 'var(--fg-muted)'};
            "
            fill="none"
            stroke="currentColor"
            stroke-width={active ? '2.2' : '1.6'}
            viewBox="0 0 24 24"
            aria-hidden="true"
          >
            {@html tab.icon}
          </svg>
        </div>

        <!-- Label -->
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
          {@html ic.menu}
        </svg>
      </div>
      <span class="text-[10px] font-semibold leading-none" style="color: var(--fg-muted)">More</span>
    </button>

  </div>
</nav>
