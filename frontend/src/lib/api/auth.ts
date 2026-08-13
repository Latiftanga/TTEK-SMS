import client from './client';
import type { CurrentUser } from '$lib/stores/auth';

export type LoginType = 'EMAIL' | 'PHONE' | 'ADMISSION_ID';

export interface LoginRequest {
  login_type: LoginType;
  identifier: string;
  password: string;
  // Required — every school is reached only via its own subdomain/custom
  // domain, which resolves this automatically before login() is ever
  // called. Platform-admin login (superadminLogin) is a fully separate
  // function that never touches school_code at all.
  school_code: string;
  remember_me?: boolean;
}

export interface SuperadminLoginRequest {
  identifier: string;
  password: string;
  remember_me?: boolean;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}

/** Student (ADMISSION_ID) or guardian (PHONE + guardian_id) — both land on /portal.
 * PHONE is shared with staff accounts, so login_type alone can't tell them apart. */
export function isPortalUser(user: CurrentUser): boolean {
  return user.login_type === 'ADMISSION_ID' || !!user.guardian_id;
}

/** Detect login type from identifier string. */
export function detectLoginType(identifier: string): LoginType {
  if (identifier.includes('@')) return 'EMAIL';
  if (/^[+\d\s]{7,}$/.test(identifier)) return 'PHONE';
  return 'ADMISSION_ID';
}

export async function login(req: LoginRequest): Promise<TokenResponse> {
  const { data } = await client.post<TokenResponse>('/auth/login', req);
  return data;
}

/** Platform-admin login — separate endpoint, never shares a code path
 * with login(). See services/auth.py::superadmin_login. */
export async function superadminLogin(req: SuperadminLoginRequest): Promise<TokenResponse> {
  const { data } = await client.post<TokenResponse>('/auth/superadmin-login', req);
  return data;
}

export async function logout(refreshToken: string): Promise<void> {
  await client.post('/auth/logout', { refresh_token: refreshToken }).catch(() => {});
}

export async function getMe(): Promise<CurrentUser> {
  const { data } = await client.get<CurrentUser>('/auth/me');
  return data;
}

export async function changePassword(current: string, next: string): Promise<void> {
  await client.post('/auth/change-password', {
    current_password: current,
    new_password: next,
  });
}

export async function forgotPassword(req: {
  login_type: LoginType;
  identifier: string;
  school_code?: string;
}): Promise<{ dev_otp?: string }> {
  const { data } = await client.post<{ dev_otp?: string }>('/auth/forgot-password', req);
  return data ?? {};
}

export async function verifyOtp(req: {
  login_type: LoginType;
  identifier: string;
  school_code?: string;
  otp: string;
}): Promise<{ reset_token: string }> {
  const { data } = await client.post<{ reset_token: string }>('/auth/verify-otp', req);
  return data;
}

export async function resetPassword(req: {
  token: string;
  new_password: string;
}): Promise<void> {
  await client.post('/auth/reset-password', req);
}

export async function updateProfile(req: {
  phone?: string;
  address?: string;
}): Promise<void> {
  await client.patch('/auth/me/profile', req);
}

export interface InvitationInfo {
  school_name: string;
  position_name: string | null;
  email: string | null;
  phone: string | null;
  is_expired: boolean;
  is_accepted: boolean;
}

export async function getInviteInfo(token: string): Promise<InvitationInfo> {
  const { data } = await client.get<InvitationInfo>(`/auth/invite-info/${token}`);
  return data;
}

export async function acceptInvite(req: { token: string; password: string }): Promise<void> {
  await client.post('/auth/accept-invite', req);
}
