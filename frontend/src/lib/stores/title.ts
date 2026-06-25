import { writable, derived } from 'svelte/store';
import { school } from './school';

const _page = writable('');

export function setPageTitle(title: string) { _page.set(title); }

export const documentTitle = derived([_page, school], ([$page, $s]) =>
  $s?.name && $page ? `${$s.name} · ${$page}` : $page || 'TTEK SMS'
);
