import client from './client';
import type { CurrentUser } from '$lib/stores/auth';

export type LoginType = 'EMAIL' | 'PHONE' | 'ADMISSION_ID';

export interface LoginRequest {
  login_type: LoginType;
  identifier: string;
  password: string;
  school_code?: string;
  remember_me?: boolean;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
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
}): Promise<void> {
  await client.post('/auth/forgot-password', req);
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
