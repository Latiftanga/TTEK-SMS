import { browser } from '$app/environment';
import { redirect } from '@sveltejs/kit';

export const ssr = false;

export function load() {
  if (!browser) return {};
  const token = localStorage.getItem('access_token');
  // Authenticated school staff go straight to the app
  if (token) return redirect(302, '/dashboard');
  // No token → show platform (superadmin) login
}
