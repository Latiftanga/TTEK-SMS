<script lang="ts">
  import { type TermEnrollmentRead } from '$lib/api/students';
  import SubjectRegistrationPanel from './SubjectRegistrationPanel.svelte';

  interface Props {
    enrollment: TermEnrollmentRead;
    termLabel: string;
    termLocked?: boolean;
    inline?: boolean;
  }
  const { enrollment, termLabel, termLocked = false, inline = false }: Props = $props();

  let expanded = $state(false);
  function toggle() { expanded = !expanded; }
</script>

{#snippet lockedBadge()}
  {#if termLocked}
    <span class="shrink-0 rounded-full bg-red-50 px-2 py-0.5 text-[10px] font-bold text-red-700 ring-1 ring-inset ring-red-600/20 dark:bg-red-950/30 dark:text-red-400" title="This term's results are locked">
      Term locked
    </span>
  {/if}
{/snippet}

{#snippet feeWaivedBadge()}
  {#if enrollment.fee_waived}
    <span class="shrink-0 rounded-full bg-amber-50 px-2 py-0.5 text-[10px] font-semibold text-amber-700 ring-1 ring-inset ring-amber-600/20 dark:bg-amber-950/30 dark:text-amber-400" title="Enrolled despite an outstanding fee balance">
      Fee waived
    </span>
  {/if}
{/snippet}

<!-- ── INLINE mode: flat tree row ─────────────────────────────────────────────── -->
{#if inline}
  <div>
    <button onclick={toggle}
      class="flex w-full items-center gap-2 rounded-lg py-2 pl-1 pr-2 text-left transition hover:bg-[var(--hover)]">
      <svg class="h-3.5 w-3.5 shrink-0 text-[var(--fg-muted)] transition-transform duration-150 {expanded ? 'rotate-90' : ''}"
        fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" d="M9 5l7 7-7 7"/>
      </svg>
      <span class="flex-1 text-sm font-medium text-[var(--fg)]">{termLabel}</span>
      <span class="pill-green">
        <svg class="h-3.5 w-3.5" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24"><polyline points="20 6 9 17 4 12"/></svg>
        Registered
      </span>
      {@render feeWaivedBadge()}
      {@render lockedBadge()}
    </button>

    {#if expanded}
      <div class="mb-2 ml-4 mt-1 space-y-2 border-l-2 pl-3"
        style="border-color: color-mix(in srgb, var(--brand) 35%, transparent)">
        <SubjectRegistrationPanel {enrollment} compact={true} />
      </div>
    {/if}
  </div>

<!-- ── STANDALONE mode: full card ─────────────────────────────────────────────── -->
{:else}
  <div class="overflow-hidden rounded-2xl border border-[var(--border)] bg-[var(--card)]">
    <button onclick={toggle}
      class="flex w-full items-center gap-3 px-4 py-3.5 text-left transition hover:bg-[var(--hover)]">
      <svg class="h-4 w-4 shrink-0 text-[var(--fg-muted)] transition-transform duration-200 {expanded ? 'rotate-90' : ''}"
        fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" d="M9 5l7 7-7 7"/>
      </svg>
      <div class="flex flex-1 min-w-0 items-center gap-2">
        <span class="text-sm font-semibold text-[var(--fg)]">{termLabel}</span>
        <span class="text-[10px] text-[var(--fg-muted)]">Term Registration</span>
      </div>
      <span class="pill-green">
        <svg class="h-3.5 w-3.5" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24"><polyline points="20 6 9 17 4 12"/></svg>
        Registered
      </span>
      {@render feeWaivedBadge()}
      {@render lockedBadge()}
    </button>

    {#if expanded}
      <div class="border-t border-[var(--border)] px-4 pb-4 pt-3 space-y-3">
        <SubjectRegistrationPanel {enrollment} compact={false} />
      </div>
    {/if}
  </div>
{/if}

<style>
  @reference "tailwindcss";
  .pill-green { @apply shrink-0 flex items-center gap-1 text-xs font-semibold text-green-600 dark:text-green-500; }
</style>
