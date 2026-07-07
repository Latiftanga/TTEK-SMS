<script lang="ts">
  import { goto } from '$app/navigation';
  import { currentUser, auth } from '$lib/stores/auth';
  import { school } from '$lib/stores/school';
  import { userRole } from '$lib/stores/permissions';
  import { logout } from '$lib/api/auth';
  import { IC, ROLE_LABELS, type NavRole } from '$lib/nav';

  interface Props { collapsed: boolean; onclose: () => void; }
  const { collapsed, onclose }: Props = $props();

  const isSuperadmin = $derived($currentUser?.is_superadmin ?? false);
  const role         = $derived($userRole as NavRole | null);
  const userLabel    = $derived($currentUser?.display_name ?? $currentUser?.email ?? $currentUser?.phone ?? '—');
  const roleLabel    = $derived(
    isSuperadmin ? 'Platform Admin' : role ? (ROLE_LABELS[role] ?? 'Staff member') : 'Staff member'
  );
  const avatarStyle  = 'background: linear-gradient(135deg, var(--brand) 0%, color-mix(in oklab, var(--brand) 60%, #7c3aed) 100%)';

  async function handleLogout() {
    const rt = localStorage.getItem('refresh_token') ?? '';
    await logout(rt);
    auth.clearAuth();
    school.clear();
    userRole.reset();
    goto('/login');
  }
</script>

<div class="shrink-0 border-t border-[var(--border)] p-2">
  {#if collapsed}
    <div class="flex flex-col items-center gap-1">
      <a href="/profile" onclick={onclose} title={userLabel}
         class="flex h-8 w-8 items-center justify-center rounded-lg text-[11px] font-bold
                text-white transition-opacity hover:opacity-80"
         style={avatarStyle}>
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
        <div class="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-[11px] font-bold text-white"
             style={avatarStyle}>
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
