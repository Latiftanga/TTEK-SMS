import { redirect } from '@sveltejs/kit';

export const ssr = false;

export function load({ url }: { url: URL }) {
  if (url.pathname === '/admin/academic' || url.pathname === '/admin/academic/') {
    redirect(302, '/admin/academic/years');
  }
}
