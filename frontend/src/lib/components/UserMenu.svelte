<script lang="ts">
  import { IC } from '$lib/nav';
  import { userLabel, roleLabel, initials, avatarStyle, signOut } from '$lib/stores/identity';

  let menuOpen = $state(false);
  let menuEl   = $state<HTMLElement | undefined>();

  function handleOutsideClick(e: PointerEvent) {
    if (menuEl && !menuEl.contains(e.target as Node)) menuOpen = false;
  }

  $effect(() => {
    if (menuOpen) {
      document.addEventListener('pointerdown', handleOutsideClick);
      return () => document.removeEventListener('pointerdown', handleOutsideClick);
    }
  });

  async function handleLogout() {
    menuOpen = false;
    await signOut();
  }

  function close() { menuOpen = false; }
</script>

<div class="relative" bind:this={menuEl}>
  <button
    onclick={() => menuOpen = !menuOpen}
    aria-label="User menu"
    aria-expanded={menuOpen}
    class="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-[11px] font-bold text-white
           ring-2 ring-transparent transition hover:opacity-90 focus-visible:ring-[var(--brand)]"
    style={avatarStyle}
  >
    {$initials}
  </button>

  {#if menuOpen}
    <div
      role="menu"
      class="absolute right-0 top-full z-50 mt-2 w-56 overflow-hidden rounded-xl
             border border-[var(--border)] bg-[var(--card)] shadow-xl"
    >
      <!-- Identity header -->
      <div class="border-b border-[var(--border)] px-4 py-3">
        <p class="truncate text-sm font-semibold text-[var(--fg)]">{$userLabel}</p>
        <p class="text-[11px] text-[var(--fg-muted)]">{$roleLabel}</p>
      </div>

      <!-- Actions -->
      <div class="p-1">
        <a href="/profile" onclick={close}
          class="flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm text-[var(--fg)]
                 transition hover:bg-[var(--hover)]">
          <svg class="h-4 w-4 shrink-0 text-[var(--fg-muted)]" fill="none" stroke="currentColor" stroke-width="1.6" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" d="M15.75 6a3.75 3.75 0 11-7.5 0 3.75 3.75 0 017.5 0zM4.501 20.118a7.5 7.5 0 0114.998 0A17.933 17.933 0 0112 21.75c-2.676 0-5.216-.584-7.499-1.632z"/>
          </svg>
          Profile
        </a>
        <a href="/change-password" onclick={close}
          class="flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm text-[var(--fg)]
                 transition hover:bg-[var(--hover)]">
          <svg class="h-4 w-4 shrink-0 text-[var(--fg-muted)]" fill="none" stroke="currentColor" stroke-width="1.6" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" d="M16.5 10.5V6.75a4.5 4.5 0 10-9 0v3.75m-.75 11.25h10.5a2.25 2.25 0 002.25-2.25v-6.75a2.25 2.25 0 00-2.25-2.25H6.75a2.25 2.25 0 00-2.25 2.25v6.75a2.25 2.25 0 002.25 2.25z"/>
          </svg>
          Change password
        </a>
      </div>

      <!-- Sign out -->
      <div class="border-t border-[var(--border)] p-1">
        <button onclick={handleLogout}
          class="flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-sm
                 text-red-600 transition hover:bg-red-50
                 dark:text-red-400 dark:hover:bg-red-950/40">
          <svg class="h-4 w-4 shrink-0" fill="none" stroke="currentColor" stroke-width="1.6" viewBox="0 0 24 24">
            {@html IC.signOut}
          </svg>
          Sign out
        </button>
      </div>
    </div>
  {/if}
</div>
