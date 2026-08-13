export const ssr = false;

// Deliberately no redirect here. A `load()` here runs before the component
// (and its $effect) ever mounts, and before the root +layout.svelte's own
// getMe() call has populated currentUser — the only way to know whether a
// stored access token belongs to a superadmin or a regular school user. An
// earlier version of this file redirected to /dashboard on token presence
// alone, which fired for a superadmin's own token too (they also get an
// access token in localStorage) — a hard SvelteKit `load()` redirect that
// ran ahead of, and independent from, the component-level routing decision,
// producing a visible flash to /dashboard before the (app) layout's
// superadmin guard bounced back to /superadmin. Routing now happens in
// exactly one place: +page.svelte's $effect on the canonical currentUser
// store, once the root layout's single getMe() call resolves.
