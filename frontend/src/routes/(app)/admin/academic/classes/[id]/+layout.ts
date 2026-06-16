import { redirect } from '@sveltejs/kit';

export const ssr = false;

export function load({ url, params }: { url: URL; params: { id: string } }) {
  const base = `/admin/academic/classes/${params.id}`;
  if (url.pathname === base || url.pathname === `${base}/`) {
    redirect(302, `${base}/students`);
  }
}
