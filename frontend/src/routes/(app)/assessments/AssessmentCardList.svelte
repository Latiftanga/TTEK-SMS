<script lang="ts">
  import { goto } from '$app/navigation';
  import { assessmentLabel, type Assessment } from '$lib/api/assessments';

  interface Props {
    assessments: Assessment[];
    typeName: (id: string) => string;
    onCreate: () => void;
  }
  const { assessments, typeName, onCreate }: Props = $props();
</script>

<!-- One interaction pattern on every breakpoint: a plain tappable list, no
     inline-editable grid — a matrix table doesn't collapse onto a phone
     without becoming worse than either extreme (research: Canvas LMS ships
     a dedicated one-at-a-time "Individual View" for exactly this reason),
     and keeping the same pattern on desktop means "back" always does the
     obvious thing instead of behaving differently depending on screen size.
     Tapping a card hands off to the existing single-assessment page
     (assessments/[id]), which already has full-width, keyboard-nav'd,
     offline-capable score entry built for a focused one-screen flow. -->
<div class="space-y-2">
  {#each assessments as a (a.id)}
    <button onclick={() => goto(`/assessments/${a.id}`)}
      class="flex w-full min-h-[44px] items-center justify-between gap-3 rounded-2xl border border-[var(--border)] bg-[var(--card)] px-4 py-3.5 text-left transition hover:border-[var(--brand)] active:scale-[0.99]">
      <div class="min-w-0">
        <p class="truncate font-medium text-[var(--fg)]">{assessmentLabel(a, typeName(a.assessment_type_id))}</p>
        <p class="mt-0.5 truncate text-xs text-[var(--fg-muted)]">
          {#if a.description}{a.description} ·{/if}
          Max {a.max_score}
          {#if a.due_date}· Given {a.due_date}{/if}
        </p>
      </div>
      <div class="flex shrink-0 items-center gap-2">
        {#if a.is_published}
          <span class="rounded-full bg-green-50 px-2.5 py-1 text-[10px] font-bold text-green-700 ring-1 ring-inset ring-green-600/20 dark:bg-green-950/30 dark:text-green-400">Published</span>
        {:else}
          <span class="rounded-full bg-[var(--hover)] px-2.5 py-1 text-[10px] font-semibold text-[var(--fg-muted)]">Draft</span>
        {/if}
        <svg class="h-4 w-4 shrink-0 text-[var(--fg-subtle)]" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" d="M9 5l7 7-7 7"/>
        </svg>
      </div>
    </button>
  {/each}

  <button onclick={onCreate}
    class="flex w-full min-h-[44px] items-center justify-center gap-2 rounded-2xl border border-dashed border-[var(--border)] px-4 py-3.5 text-sm font-semibold text-[var(--fg-muted)] transition hover:border-[var(--brand)] hover:text-[var(--brand)]">
    <svg class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24">
      <path stroke-linecap="round" stroke-linejoin="round" d="M12 4v16m8-8H4"/>
    </svg>
    New assessment
  </button>
</div>
