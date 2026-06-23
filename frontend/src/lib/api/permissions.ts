import api from './client';

export interface PermissionEntry {
  module: string;
  action: string;
  is_allowed: boolean;
}

export interface PositionWithPerms {
  id: string;
  code: string;
  name: string;
  is_template: boolean;
  school_id: string | null;
  permissions: PermissionEntry[];
}

export const PERMISSION_MATRIX: Record<string, string[]> = {
  school:      ['view', 'edit', 'manage_users'],
  staff:       ['view', 'create', 'edit', 'delete'],
  students:    ['view', 'create', 'edit', 'delete'],
  academic:    ['view', 'create', 'edit', 'delete'],
  attendance:  ['view', 'record', 'approve'],
  assessments: ['view', 'enter_scores', 'approve_scores'],
  fees:        ['view', 'collect', 'manage'],
  housing:     ['view', 'assign', 'manage'],
  reports:     ['view', 'generate'],
};

export const MODULE_LABELS: Record<string, string> = {
  school:      'School',
  staff:       'Staff',
  students:    'Students',
  academic:    'Academic',
  attendance:  'Attendance',
  assessments: 'Assessments',
  fees:        'Fees',
  housing:     'Housing',
  reports:     'Reports',
};

export const ACTION_LABELS: Record<string, string> = {
  view:           'View',
  edit:           'Edit',
  create:         'Create',
  delete:         'Delete',
  manage_users:   'Manage users',
  record:         'Record',
  approve:        'Approve',
  enter_scores:   'Enter scores',
  approve_scores: 'Approve scores',
  collect:        'Collect',
  manage:         'Manage',
  assign:         'Assign',
  generate:       'Generate',
};

export const listPositionsWithPerms = () =>
  api.get<PositionWithPerms[]>('/permissions/positions').then(r => r.data);

export const updatePositionPermissions = (positionId: string, permissions: PermissionEntry[]) =>
  api.put<PositionWithPerms>(`/permissions/positions/${positionId}`, { permissions }).then(r => r.data);

/** Build a Set of "module.action" strings that are granted for a position */
export function grantedSet(pos: PositionWithPerms): Set<string> {
  return new Set(
    pos.permissions.filter(p => p.is_allowed).map(p => `${p.module}.${p.action}`)
  );
}
