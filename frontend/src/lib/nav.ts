/**
 * Sidebar navigation configuration.
 * Each item's `roles` array controls visibility; undefined = visible to all authenticated users.
 * Superadmins always see everything regardless of roles.
 */

export type NavRole = 'teacher' | 'admin' | 'approver' | 'finance' | 'housemaster';

export interface ChildNavItem {
  href: string;
  label: string;
  roles?: NavRole[];
}

export interface NavItem {
  href: string;        // used for active detection; also link target in collapsed mode
  label: string;
  icon: string;        // SVG inner path(s) — rendered via {@html}
  exact?: boolean;
  roles?: NavRole[];
  children?: ChildNavItem[];
}

export interface NavGroup {
  heading?: string;
  items: NavItem[];
}

// ── Icons (24×24 outline, stroke paths only) ──────────────────────────────────

const IC: Record<string, string> = {
  transfers:  `<path stroke-linecap="round" stroke-linejoin="round" d="M7.5 21L3 16.5m0 0L7.5 12M3 16.5h13.5m0-13.5L21 7.5m0 0L16.5 12M21 7.5H7.5"/>`,
  dashboard:  `<path stroke-linecap="round" stroke-linejoin="round" d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6"/>`,
  students:   `<path stroke-linecap="round" stroke-linejoin="round" d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z"/>`,
  attendance: `<path stroke-linecap="round" stroke-linejoin="round" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4"/>`,
  assessments:`<path stroke-linecap="round" stroke-linejoin="round" d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z"/>`,
  fees:       `<path stroke-linecap="round" stroke-linejoin="round" d="M3 10h18M7 15h1m4 0h1m-7 4h12a3 3 0 003-3V8a3 3 0 00-3-3H6a3 3 0 00-3 3v8a3 3 0 003 3z"/>`,
  reports:    `<path stroke-linecap="round" stroke-linejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/>`,
  housing:    `<path stroke-linecap="round" stroke-linejoin="round" d="M2.25 12l8.954-8.955c.44-.439 1.152-.439 1.591 0L21.75 12M4.5 9.75v10.125c0 .621.504 1.125 1.125 1.125H9.75v-4.875c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125V21h4.125c.621 0 1.125-.504 1.125-1.125V9.75M8.25 21h8.25"/>`,
  setup:      `<path stroke-linecap="round" stroke-linejoin="round" d="M10.5 6h9.75M10.5 6a1.5 1.5 0 11-3 0m3 0a1.5 1.5 0 10-3 0M3.75 6H7.5m3 12h9.75m-9.75 0a1.5 1.5 0 01-3 0m3 0a1.5 1.5 0 00-3 0m-3.75 0H7.5m9-6h3.75m-3.75 0a1.5 1.5 0 01-3 0m3 0a1.5 1.5 0 00-3 0m-9.75 0h9.75"/>`,
  academic:   `<path stroke-linecap="round" stroke-linejoin="round" d="M4.26 10.147a60.436 60.436 0 00-.491 6.347A48.627 48.627 0 0112 20.904a48.627 48.627 0 018.232-4.41 60.46 60.46 0 00-.491-6.347m-15.482 0a50.57 50.57 0 00-2.658-.813A59.905 59.905 0 0112 3.493a59.902 59.902 0 0110.399 5.84c-.896.248-1.783.52-2.658.814m-15.482 0A50.697 50.697 0 0112 13.489a50.702 50.702 0 017.74-3.342"/>`,
  staff:      `<path stroke-linecap="round" stroke-linejoin="round" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z"/>`,
  signOut:    `<path stroke-linecap="round" stroke-linejoin="round" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1"/>`,
  chevronL:   `<path stroke-linecap="round" stroke-linejoin="round" d="M15.75 19.5 8.25 12l7.5-7.5"/>`,
  chevronR:   `<path stroke-linecap="round" stroke-linejoin="round" d="M8.25 4.5l7.5 7.5-7.5 7.5"/>`,
  chevronD:   `<path stroke-linecap="round" stroke-linejoin="round" d="M19.5 8.25l-7.5 7.5-7.5-7.5"/>`,
};

export { IC };

// ── Navigation groups ─────────────────────────────────────────────────────────

export const NAV_GROUPS: NavGroup[] = [
  {
    // Daily work — no heading
    items: [
      { href: '/dashboard',   label: 'Dashboard',    icon: IC.dashboard,   exact: true },
      { href: '/attendance',  label: 'Attendance',   icon: IC.attendance,  roles: ['teacher', 'admin', 'approver'] },
      {
        href: '/assessments', label: 'Assessments',  icon: IC.assessments, roles: ['teacher', 'admin', 'approver'],
        children: [
          { href: '/assessments',        label: 'Assessments',    roles: ['teacher', 'admin', 'approver'] },
          { href: '/assessments/scales', label: 'Grading Scales', roles: ['admin', 'approver'] },
          { href: '/assessments/types',  label: 'Types',          roles: ['admin', 'approver'] },
        ],
      },
      { href: '/fees',        label: 'Fees',         icon: IC.fees,        roles: ['finance', 'admin'] },
      { href: '/reports',     label: 'Report Cards', icon: IC.reports,     roles: ['teacher', 'admin', 'approver'] },
      { href: '/housing',     label: 'Housing',      icon: IC.housing,     roles: ['admin', 'approver', 'housemaster'] },
    ],
  },
  {
    heading: 'Administration',
    items: [
      { href: '/admin/setup', label: 'School Setup', icon: IC.setup,     roles: ['admin'] },
      {
        href: '/admin/academic/classes', label: 'Academic', icon: IC.academic, roles: ['admin'],
        children: [
          { href: '/admin/academic/classes',  label: 'Classes',    roles: ['admin'] },
          { href: '/admin/academic/years',    label: 'Calendar',   roles: ['admin'] },
          { href: '/admin/academic/promote',  label: 'Promotion',  roles: ['admin'] },
        ],
      },
      {
        href: '/students', label: 'Students', icon: IC.students, roles: ['admin'],
        children: [
          { href: '/students',         label: 'Directory',  roles: ['admin'] },
          { href: '/admin/transfers',  label: 'Transfers',  roles: ['admin'] },
        ],
      },
      { href: '/admin/staff', label: 'Staff', icon: IC.staff, roles: ['admin'] },
    ],
  },
];

// ── Role display ──────────────────────────────────────────────────────────────

export const ROLE_LABELS: Record<string, string> = {
  teacher:     'Class Teacher',
  admin:       'School Admin',
  approver:    'HOD / Approver',
  finance:     'Finance Officer',
  housemaster: 'House Master',
};
