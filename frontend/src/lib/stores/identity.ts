import { derived } from 'svelte/store';
import { goto } from '$app/navigation';
import { currentUser, auth } from './auth';
import { school } from './school';
import { userRole, isClassTeacher, isSubjectTeacher, isHousemaster } from './permissions';
import { logout as apiLogout } from '$lib/api/auth';
import { ROLE_LABELS, type NavRole } from '$lib/nav';

export const userLabel = derived(currentUser,
  $u => $u?.display_name ?? $u?.email ?? $u?.phone ?? '—');

// 'staff' can be any combination of Class Teacher/Subject Teacher/
// Housemaster now, so unlike the other three roles it has no single fixed
// label in ROLE_LABELS — build one from whichever capabilities are actually
// held, falling back to a generic "Teacher" for a staff position with no
// assignment yet.
export const roleLabel = derived(
  [currentUser, userRole, isClassTeacher, isSubjectTeacher, isHousemaster],
  ([$u, $role, $classTeacher, $subjectTeacher, $housemaster]) => {
    if ($u?.is_superadmin) return 'Platform Admin';
    const role = $role as NavRole | null;
    if (!role) return 'Staff member';
    if (role !== 'staff') return ROLE_LABELS[role] ?? 'Staff member';
    const parts: string[] = [];
    if ($classTeacher) parts.push('Class Teacher');
    if (!$classTeacher && $subjectTeacher) parts.push('Subject Teacher');
    if ($housemaster) parts.push('Housemaster');
    return parts.length ? parts.join(' · ') : 'Teacher';
  },
);

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
