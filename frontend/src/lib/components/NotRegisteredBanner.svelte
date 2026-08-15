<script lang="ts">
  import { createMutation } from '@tanstack/svelte-query';
  import { bulkEnrollStudents } from '$lib/api/students';
  import { apiError } from '$lib/utils';
  import { toast } from '$lib/stores/toast';

  interface Props {
    items: { student_id: string; academic_term_id: string }[];
    termName: string;
    onRegistered?: () => void;
  }
  const { items, termName, onRegistered }: Props = $props();

  const registerMut = createMutation({
    mutationFn: () => bulkEnrollStudents(items),
    onSuccess: (res) => {
      toast.success(`${res.enrolled} registered for ${termName}. Skipped: ${res.skipped}.`);
      onRegistered?.();
    },
    onError: (e) => toast.error(apiError(e, 'Failed to register students for the term.')),
  });
</script>

{#if items.length > 0}
  <div class="flex flex-wrap items-center gap-2">
    <span class="shrink-0 rounded-full bg-amber-50 px-2.5 py-0.5 text-[10px] font-semibold text-amber-700 dark:bg-amber-950/30 dark:text-amber-400">
      {items.length} not registered for {termName}
    </span>
    <button onclick={() => $registerMut.mutate()} disabled={$registerMut.isPending}
      class="shrink-0 rounded-lg border border-[var(--border)] px-3 py-1.5 text-xs font-semibold text-[var(--fg-muted)]
             transition hover:bg-[var(--hover)] hover:text-[var(--fg)] disabled:opacity-40">
      {$registerMut.isPending ? 'Registering…' : `Register ${items.length} for ${termName}`}
    </button>
  </div>
{/if}
