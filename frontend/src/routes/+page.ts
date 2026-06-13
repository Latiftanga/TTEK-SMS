import { browser } from '$app/environment';
import { redirect } from '@sveltejs/kit';

export const ssr = false;

export function load() {
  if (!browser) return {};
  const token = localStorage.getItem('access_token');
  redirect(302, token ? '/dashboard' : '/login');
}
