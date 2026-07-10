import { derived } from 'svelte/store';
import { goto } from '$app/navigation';
import { currentUser, auth } from './auth';
import { school } from './school';
import { userRole } from './permissions';
import { logout as apiLogout } from '$lib/api/auth';
import { ROLE_LABELS, type NavRole } from '$lib/nav';

export const userLabel = derived(currentUser,
  $u => $u?.display_name ?? $u?.email ?? $u?.phone ?? '—');

export const roleLabel = derived([currentUser, userRole], ([$u, $role]) => {
  if ($u?.is_superadmin) return 'Platform Admin';
  const role = $role as NavRole | null;
  return role ? (ROLE_LABELS[role] ?? 'Staff member') : 'Staff member';
});

export const initials = derived(userLabel, $label =>
  $label.split(' ').filter((w: string) => w).slice(0, 2).map((w: string) => w[0]).join('').toUpperCase()
  || $label.slice(0, 2).toUpperCase()
);

export const avatarStyle =
  'background: linear-gradient(135deg, var(--brand) 0%, color-mix(in oklab, var(--brand) 60%, #7c3aed) 100%)';

export async function signOut(): Promise<void> {
  const rt = localStorage.getItem('refresh_token') ?? '';
  await apiLogout(rt);
  auth.clearAuth();
  school.clear();
  userRole.reset();
  goto('/login');
}
