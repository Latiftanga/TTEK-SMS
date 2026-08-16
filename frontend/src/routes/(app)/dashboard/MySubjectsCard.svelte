<script lang="ts">
  // Mirrors AdminView.svelte's "Administration" quick-links card exactly
  // (icon box + label/sub + trailing arrow, divide-y rows) with a pending
  // badge inserted before the arrow when there's something waiting.
  import type { SubjectSnapshot } from '$lib/api/dashboard';

  interface Props { subjects: SubjectSnapshot[]; }
  const { subjects }: Props = $props();

  const icon = `<path stroke-linecap="round" stroke-linejoin="round" d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z"/>`;
  const arrow = `<path stroke-linecap="round" stroke-linejoin="round" d="M7 17L17 7M17 7H7M17 7v10"/>`;
</script>

<div>
  <p class="mb-2.5 text-[0.6875rem] font-semibold uppercase tracking-widest text-[var(--fg-muted)]">My Subjects</p>
  <div class="overflow-hidden rounded-[1.25rem] border border-[var(--border)] bg-[var(--card)] divide-y divide-[var(--border)]"
       style="box-shadow: var(--shadow-sm);">
    {#each subjects as s (s.class_id + s.subject_id)}
      <a href="/assessments?class={s.class_id}&subject={s.subject_id}"
         class="group flex items-center gap-3.5 px-4 py-3.5 transition hover:bg-[var(--hover)]">
        <div class="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl
                    bg-[var(--hover)] transition group-hover:bg-[var(--card)]">
          <svg class="h-4 w-4 text-[var(--fg-muted)]" fill="none" stroke="currentColor" stroke-width="1.6" viewBox="0 0 24 24">
            {@html icon}
          </svg>
        </div>
        <div class="min-w-0 flex-1">
          <p class="text-[0.8125rem] font-semibold text-[var(--fg)]">{s.subject_name}</p>
          <p class="text-[0.6875rem] text-[var(--fg-muted)]">{s.class_name}</p>
        </div>
        {#if s.pending_score_assessments > 0}
          <span class="shrink-0 rounded-full bg-amber-100 dark:bg-amber-900/50 px-2 py-0.5 text-[10px] font-bold text-amber-600 dark:text-amber-400">
            {s.pending_score_assessments}
          </span>
        {/if}
        <svg class="h-4 w-4 shrink-0 text-[var(--fg-subtle)] transition-transform group-hover:translate-x-0.5"
             fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
          {@html arrow}
        </svg>
      </a>
    {/each}
  </div>
</div>
