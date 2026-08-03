<script lang="ts">
  import type { SchoolClass } from '$lib/api/academic';
  import { compatibleClasses, describeMismatch, suggestTargetClass, type PromotionMode } from '$lib/classProgression';

  interface Props {
    fromClass: SchoolClass | null;
    classes: SchoolClass[];
    value: string;
    onChange: (id: string) => void;
    mode: PromotionMode;
    label?: string;
    excludeClassId?: string;
    selectClass?: string;
  }
  const {
    fromClass, classes, value, onChange, mode,
    label = 'Target class', excludeClassId, selectClass = '',
  }: Props = $props();

  // Reset the "show everything" escape hatch whenever the source class or
  // mode changes, so switching e.g. Promote -> Demote doesn't carry over an
  // unfiltered list from a different context.
  let showAll = $state(false);
  $effect(() => { void fromClass; void mode; showAll = false; });

  const compatible = $derived(compatibleClasses(fromClass, classes, mode));
  const suggested  = $derived(suggestTargetClass(fromClass, classes, mode));

  // Nothing matches (e.g. the next class hasn't been created yet) — fall
  // back to the full list rather than presenting a dead-end empty dropdown.
  $effect(() => { if (fromClass && compatible.length === 0) showAll = true; });

  // Auto-fill the suggestion the moment one becomes available, same courtesy
  // as the three duplicated snippets this component replaces — only while
  // nothing has been picked yet, never overriding a deliberate choice.
  $effect(() => { if (!value && suggested) onChange(suggested.id); });

  const listed = $derived.by(() => {
    const base = showAll ? classes : compatible;
    return excludeClassId ? base.filter(c => c.id !== excludeClassId) : base;
  });

  const selectedClass = $derived(classes.find(c => c.id === value) ?? null);
  const mismatch = $derived(describeMismatch(fromClass, selectedClass));
  const isSuggested = $derived(!!suggested && value === suggested.id && !showAll);
</script>

<div>
  <label class="lx" for="target-class-picker">
    {label}
    {#if isSuggested}
      <span class="ml-1 rounded-full bg-green-50 px-1.5 py-0.5 text-[10px] font-semibold text-green-700 dark:bg-green-950/30 dark:text-green-400">suggested</span>
    {/if}
  </label>
  <select id="target-class-picker" value={value} onchange={(e) => onChange(e.currentTarget.value)}
    class="sel mt-1 {selectClass}">
    <option value="">Select class…</option>
    {#each listed as c (c.id)}<option value={c.id}>{c.display_name}</option>{/each}
    {#if listed.length === 0}<option disabled>No classes available</option>{/if}
  </select>

  {#if fromClass && compatible.length > 0}
    <label class="mt-1.5 flex cursor-pointer items-center gap-1.5 text-[11px] text-[var(--fg-muted)]">
      <input type="checkbox" bind:checked={showAll} class="h-3.5 w-3.5 rounded accent-[var(--brand)]" />
      Show all classes
    </label>
  {/if}

  {#if value && (mismatch.programme || mismatch.stream)}
    <p class="mt-1.5 rounded-lg bg-amber-50 px-2.5 py-1.5 text-[11px] font-medium text-amber-700 dark:bg-amber-950/30 dark:text-amber-400">
      {#if mismatch.programme}Different programme.{/if}
      {#if mismatch.stream}Different stream.{/if}
      You'll be asked for an override reason.
    </p>
  {/if}
</div>

<style>
  @reference "tailwindcss";
  .lx  { @apply block text-xs font-medium text-[var(--fg-muted)]; }
  .sel { @apply w-full rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--fg)] focus:border-[var(--brand)] focus:outline-none transition; }
</style>
