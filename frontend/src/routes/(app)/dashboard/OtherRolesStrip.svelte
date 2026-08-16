<script lang="ts">
  import type { RoleBadge } from '$lib/api/dashboard';

  // Compact "you also..." row — surfaces every responsibility the primary
  // dashboard view doesn't already cover (e.g. a Housemaster who's also a
  // Class Teacher). Deliberately quiet, not another hero card: the primary
  // view above already carries the one thing to focus on right now.
  interface Props { roles: RoleBadge[]; }
  const { roles }: Props = $props();
</script>

{#if roles.length > 0}
  <div class="mt-4 flex flex-wrap gap-2">
    {#each roles as r (r.role)}
      <a href={r.href}
        class="flex items-center gap-1.5 rounded-xl border border-[var(--border)] bg-[var(--card)] px-3 py-2 text-xs transition hover:border-[var(--brand)]">
        <span class="font-semibold text-[var(--fg)]">{r.label}</span>
        <span class="text-[var(--fg-muted)]">· {r.detail}</span>
      </a>
    {/each}
  </div>
{/if}
