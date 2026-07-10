<script lang="ts">
  import { IC } from '$lib/nav';
  import { userLabel, roleLabel, initials, avatarStyle, signOut } from '$lib/stores/identity';

  interface Props { collapsed: boolean; onclose: () => void; }
  const { collapsed, onclose }: Props = $props();
</script>

<div class="shrink-0 border-t border-[var(--border)] p-2">
  {#if collapsed}
    <div class="flex flex-col items-center gap-1">
      <a href="/profile" onclick={onclose} title={$userLabel}
         class="flex h-8 w-8 items-center justify-center rounded-lg text-[11px] font-bold
                text-white transition-opacity hover:opacity-80"
         style={avatarStyle}>
        {$initials}
      </a>
      <button onclick={signOut} title="Sign out"
        class="flex h-8 w-8 items-center justify-center rounded-lg transition-colors
               text-[var(--fg-muted)] hover:bg-red-50 dark:hover:bg-red-950/40 hover:text-red-500">
        <svg class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="1.6" viewBox="0 0 24 24">
          {@html IC.signOut}
        </svg>
      </button>
    </div>
  {:else}
    <div class="flex items-center gap-1.5">
      <a href="/profile" onclick={onclose}
         class="group flex min-w-0 flex-1 items-center gap-2.5 rounded-lg px-2 py-1.5
                transition-colors hover:bg-[var(--hover)]">
        <div class="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-[11px] font-bold text-white"
             style={avatarStyle}>
          {$initials}
        </div>
        <div class="min-w-0">
          <p class="truncate text-xs font-semibold text-[var(--fg)]">{$userLabel}</p>
          <p class="text-[10px] text-[var(--fg-muted)]">{$roleLabel}</p>
        </div>
      </a>
      <button onclick={signOut} title="Sign out"
        class="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg transition-colors
               text-[var(--fg-muted)] hover:bg-red-50 dark:hover:bg-red-950/40 hover:text-red-500">
        <svg class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="1.6" viewBox="0 0 24 24">
          {@html IC.signOut}
        </svg>
      </button>
    </div>
  {/if}
</div>
