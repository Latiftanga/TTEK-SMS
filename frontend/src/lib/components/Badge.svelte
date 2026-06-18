<script lang="ts">
  /**
   * Badge — status and category indicator.
   *
   * variant="dot"   A coloured dot prefixes the label. No background fill.
   *                 Reads like an ink mark in a register. Smaller footprint
   *                 than a pill; appropriate for active/inactive states.
   *
   * variant="solid" Light tinted background, text-matched colour.
   *                 Uses rounded (4px) NOT rounded-full — a deliberate
   *                 departure from the universal pill shape.
   *                 Appropriate for categorical labels (Teaching, Non-Teaching).
   */
  type Color = 'green' | 'red' | 'amber' | 'teal' | 'violet' | 'gray' | 'blue' | 'brand';
  type Variant = 'dot' | 'solid';

  interface Props {
    label: string;
    color?: Color;
    variant?: Variant;
  }
  const { label, color = 'gray', variant = 'dot' }: Props = $props();

  const DOT: Record<Color, string> = {
    green:  'bg-emerald-500',
    red:    'bg-red-500',
    amber:  'bg-amber-400',
    teal:   'bg-teal-500',
    violet: 'bg-violet-500',
    gray:   'bg-[var(--fg-subtle)]',
    blue:   'bg-blue-500',
    brand:  'bg-[var(--brand)]',
  };

  const DOT_TEXT: Record<Color, string> = {
    green:  'text-emerald-700 dark:text-emerald-400',
    red:    'text-red-600 dark:text-red-400',
    amber:  'text-amber-700 dark:text-amber-400',
    teal:   'text-teal-700 dark:text-teal-400',
    violet: 'text-violet-600 dark:text-violet-400',
    gray:   'text-[var(--fg-muted)]',
    blue:   'text-blue-700 dark:text-blue-400',
    brand:  'text-[var(--brand)]',
  };

  const SOLID: Record<Color, string> = {
    green:  'bg-emerald-100 dark:bg-emerald-950/50 text-emerald-700 dark:text-emerald-400',
    red:    'bg-red-100 dark:bg-red-950/50 text-red-600 dark:text-red-400',
    amber:  'bg-amber-100 dark:bg-amber-950/50 text-amber-700 dark:text-amber-400',
    teal:   'bg-teal-100 dark:bg-teal-950/50 text-teal-700 dark:text-teal-400',
    violet: 'bg-violet-100 dark:bg-violet-950/50 text-violet-600 dark:text-violet-400',
    gray:   'bg-[var(--hover)] text-[var(--fg-muted)]',
    blue:   'bg-blue-100 dark:bg-blue-950/50 text-blue-700 dark:text-blue-400',
    brand:  'bg-[var(--brand-dim)] text-[var(--brand)]',
  };
</script>

{#if variant === 'dot'}
  <span class="inline-flex items-center gap-1.5 {DOT_TEXT[color]}">
    <span class="h-[6px] w-[6px] shrink-0 rounded-full {DOT[color]}"></span>
    <span class="text-[10px] font-semibold uppercase tracking-wide leading-none">{label}</span>
  </span>
{:else}
  <!-- rounded, NOT rounded-full — the deliberate shape choice -->
  <span class="inline-flex items-center rounded px-2 py-0.5 text-[10px]
               font-semibold uppercase tracking-wide {SOLID[color]}">
    {label}
  </span>
{/if}
