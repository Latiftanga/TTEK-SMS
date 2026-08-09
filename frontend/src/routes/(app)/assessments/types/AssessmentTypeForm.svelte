<script lang="ts">
  import type {
    AggregationStrategy, AssessmentCategory, AssessmentTypePreset,
  } from '$lib/api/assessments';

  export interface AssessmentTypeFormState {
    name: string; code: string; weight: string;
    category: AssessmentCategory;
    allow_multiple_entries: boolean; aggregation_strategy: AggregationStrategy;
  }

  interface Props {
    form: AssessmentTypeFormState;
    onChange: (patch: Partial<AssessmentTypeFormState>) => void;
    error: string;
    pending: boolean;
    onSubmit: () => void;
    onCancel: () => void;
    submitLabel: string;
    presets?: AssessmentTypePreset[];
    compact?: boolean;
  }
  const { form, onChange, error, pending, onSubmit, onCancel, submitLabel, presets, compact = false }: Props = $props();

  // Aggregation strategy only means anything when more than one entry can be
  // recorded for this type — force it back to NONE the moment multiple
  // entries is turned off, so the form can never submit an invalid
  // combination (services/aggregation.py's own NONE-expects-exactly-one rule).
  function toggleMultiple(checked: boolean) {
    onChange({
      allow_multiple_entries: checked,
      aggregation_strategy: checked ? (form.aggregation_strategy === 'NONE' ? 'AVERAGE' : form.aggregation_strategy) : 'NONE',
    });
  }

  function applyPreset(p: AssessmentTypePreset) {
    onChange({
      name: p.name, code: p.code, weight: String(p.weight),
      category: p.category,
      allow_multiple_entries: p.allow_multiple_entries, aggregation_strategy: p.aggregation_strategy,
    });
  }

  // Sensible defaults by category — a summative type (the end-of-term exam)
  // happens once per term, formative/diagnostic types are the ones that
  // realistically recur (class tests, repeated check-ins). These are only
  // defaults, not a hard rule — allow_multiple_entries stays a normal
  // checkbox the user can still flip either way; see the warning below for
  // the one combination worth flagging (summative + multiple entries).
  function onCategoryChange(category: AssessmentCategory) {
    if (category === 'SUMMATIVE' && form.category !== 'SUMMATIVE') {
      onChange({ category, allow_multiple_entries: false, aggregation_strategy: 'NONE' });
    } else if (category !== 'SUMMATIVE' && form.category === 'SUMMATIVE') {
      onChange({ category, allow_multiple_entries: true, aggregation_strategy: 'AVERAGE' });
    } else {
      onChange({ category });
    }
  }

  const CATEGORY_HELP: Record<AssessmentCategory, string> = {
    FORMATIVE: 'Recurring assessments during the term, like class tests and homework.',
    SUMMATIVE: 'The major end-of-term exam — normally happens once per term.',
    DIAGNOSTIC: 'Identifies a learning gap or guides a decision like placement — never counted in the term total.',
  };

  const AGGREGATION_HELP: Record<AggregationStrategy, string> = {
    AVERAGE: 'The mean of every recorded entry — e.g. 3 class tests average out to one score.',
    BEST_OF: 'Only the highest-scoring entry counts; the rest are ignored.',
    SUM_NORMALIZE: 'Every entry is added together and scaled against their combined maximum.',
    NONE: 'A single entry, used as-is.',
  };

  const labelCls = compact ? 'label-xs' : 'label';
  const inputCls = compact ? 'inp' : 'input';
</script>

{#if presets && presets.length > 0}
  <div class="mb-3">
    <span class="{labelCls}">Quick fill from preset</span>
    <div class="flex flex-wrap gap-1.5">
      {#each presets as p (p.code)}
        <button type="button" onclick={() => applyPreset(p)}
          class="rounded-lg border border-[var(--border)] px-2.5 py-1 text-xs font-medium text-[var(--fg-muted)] transition hover:border-[var(--brand)] hover:text-[var(--brand)]">
          {p.name}
        </button>
      {/each}
    </div>
  </div>
{/if}

<div>
  <label class={labelCls} for="{compact ? 'e' : 'c'}-category">Category</label>
  <select id="{compact ? 'e' : 'c'}-category" value={form.category}
    onchange={e => onCategoryChange(e.currentTarget.value as AssessmentCategory)} class={inputCls}>
    <option value="FORMATIVE">Formative</option>
    <option value="SUMMATIVE">Summative</option>
    <option value="DIAGNOSTIC">Diagnostic</option>
  </select>
  <p class="mt-1 text-[11px] text-[var(--fg-subtle)]">{CATEGORY_HELP[form.category]}</p>
</div>

<div class={compact ? 'mt-2 grid gap-2 sm:grid-cols-3' : 'mt-3 grid gap-3 sm:grid-cols-3'}>
  <div>
    <label class={labelCls} for="{compact ? 'e' : 'c'}-name">Name <span class="text-red-500">*</span></label>
    <input id="{compact ? 'e' : 'c'}-name" value={form.name} oninput={e => onChange({ name: e.currentTarget.value })}
      placeholder="End of Term" class={inputCls} />
  </div>
  <div>
    <label class={labelCls} for="{compact ? 'e' : 'c'}-code">Code <span class="text-red-500">*</span></label>
    <input id="{compact ? 'e' : 'c'}-code" value={form.code} oninput={e => onChange({ code: e.currentTarget.value })}
      placeholder="EOT" class={inputCls} />
  </div>
  <div>
    <label class={labelCls} for="{compact ? 'e' : 'c'}-weight">Weight % <span class="text-red-500">*</span></label>
    <input id="{compact ? 'e' : 'c'}-weight" type="number" min="0.01" max="100" step="0.01" value={form.weight}
      oninput={e => onChange({ weight: e.currentTarget.value })} placeholder="e.g. 70" class={inputCls} />
  </div>
</div>

<div class={compact ? 'mt-2 grid gap-2 sm:grid-cols-2' : 'mt-3 grid gap-3 sm:grid-cols-2'}>
  <label class="flex items-center gap-2 text-xs text-[var(--fg-muted)]">
    <input type="checkbox" checked={form.allow_multiple_entries}
      onchange={e => toggleMultiple(e.currentTarget.checked)} class="rounded border-[var(--border)]" />
    Allow multiple entries per term
  </label>
  {#if form.allow_multiple_entries}
    <div>
      <label class={labelCls} for="{compact ? 'e' : 'c'}-agg">How multiple entries combine</label>
      <select id="{compact ? 'e' : 'c'}-agg" value={form.aggregation_strategy}
        onchange={e => onChange({ aggregation_strategy: e.currentTarget.value as AggregationStrategy })} class={inputCls}>
        <option value="AVERAGE">Average</option>
        <option value="BEST_OF">Best of</option>
        <option value="SUM_NORMALIZE">Sum, normalized</option>
      </select>
      <p class="mt-1 text-[11px] text-[var(--fg-subtle)]">{AGGREGATION_HELP[form.aggregation_strategy]}</p>
    </div>
  {/if}
</div>

{#if form.category === 'SUMMATIVE' && form.allow_multiple_entries}
  <p class="mt-2 rounded-lg bg-amber-50 px-2.5 py-1.5 text-[11px] font-medium text-amber-700 dark:bg-amber-950/30 dark:text-amber-400">
    Summative assessments (like the end-of-term exam) usually happen once per term. Double-check this is intentional before saving.
  </p>
{/if}

{#if error}<p class="mt-2 text-xs text-red-500">{error}</p>{/if}
<div class={compact ? 'mt-2 flex gap-2' : 'mt-3 flex gap-2'}>
  {#if compact}
    <button onclick={onSubmit} disabled={pending}
      class="rounded-lg px-3 py-1.5 text-xs font-semibold text-white disabled:opacity-50 transition hover:opacity-90"
      style="background: var(--brand)">
      {pending ? 'Saving…' : submitLabel}
    </button>
    <button onclick={onCancel} class="text-xs text-[var(--fg-muted)] hover:text-[var(--fg)] transition">Cancel</button>
  {:else}
    <button onclick={onSubmit} disabled={pending}
      class="rounded-xl px-4 py-2 text-sm font-semibold text-white disabled:opacity-50 transition hover:opacity-90"
      style="background: var(--brand)">
      {pending ? 'Saving…' : submitLabel}
    </button>
    <button onclick={onCancel}
      class="rounded-xl border border-[var(--border)] px-4 py-2 text-sm text-[var(--fg-muted)] hover:bg-[var(--hover)] transition">
      Cancel
    </button>
  {/if}
</div>

<style>
  @reference "tailwindcss";
  .label    { @apply block text-xs font-medium text-[var(--fg-muted)] mb-1; }
  .label-xs { @apply block text-[10px] font-medium text-[var(--fg-muted)] mb-0.5; }
  .input    { @apply w-full rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--fg)] placeholder:text-[var(--fg-subtle)] focus:border-[var(--brand)] focus:outline-none transition; }
  .inp      { @apply w-full rounded-lg border border-[var(--border)] bg-[var(--card)] px-2 py-1.5 text-xs text-[var(--fg)] placeholder:text-[var(--fg-subtle)] focus:border-[var(--brand)] focus:outline-none transition; }
</style>
