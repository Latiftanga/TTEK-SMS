import { writable } from 'svelte/store';
import { createQuery, type CreateQueryOptions, type CreateQueryResult, type StoreOrVal } from '@tanstack/svelte-query';

/**
 * Minimal query options accepted by reactiveQuery.
 * The queryFn is typed as () => Promise<T> (no context arg) because all API
 * calls in this project close over their parameters via the factory closure.
 */
interface ReactiveOpts<T> {
  queryKey:             readonly unknown[];
  queryFn:              () => Promise<T>;
  enabled?:             boolean;
  staleTime?:           number;
  refetchOnWindowFocus?: boolean;
}

/**
 * Reactive TanStack Query wrapper for Svelte 5.
 *
 * @tanstack/svelte-query v5 needs a Readable<Options> to react to key changes.
 * Manually writing `const opts = writable(…); $effect(() => opts.set(…));
 * const q = createQuery(opts)` for every dynamic query adds 3 lines of
 * boilerplate per query. This helper collapses that into one call.
 *
 * The factory function is a plain closure that reads $state / $derived values.
 * Svelte's reactivity system tracks those reads inside $effect and re-runs the
 * factory (and updates the underlying store) whenever any dependency changes.
 *
 * @example
 *   const q = reactiveQuery(() => ({
 *     queryKey: ['items', selectedId] as const,
 *     queryFn:  () => fetchItems(selectedId),
 *     enabled:  !!selectedId,
 *     staleTime: 30_000,
 *   }));
 *   // subscribe as $q — $q.data, $q.isPending, $q.isError, $q.refetch()
 */
export function reactiveQuery<T>(factory: () => ReactiveOpts<T>): CreateQueryResult<T> {
  const store = writable(factory());
  $effect(() => { store.set(factory()); });
  // ReactiveOpts<T> is structurally compatible with CreateQueryOptions<T>; the cast
  // bridges the mismatch on queryFn's context-arg signature. Casting through
  // StoreOrVal<CreateQueryOptions<T>> (rather than the old `Parameters<typeof
  // createQuery>[0]`, which resolves against createQuery's last overload with all
  // generics defaulted to `unknown`) is what lets createQuery correctly infer
  // TQueryFnData = T from the argument — without it, every caller's `.data` silently
  // degraded to `unknown` regardless of T.
  return createQuery(store as unknown as StoreOrVal<CreateQueryOptions<T>>);
}
