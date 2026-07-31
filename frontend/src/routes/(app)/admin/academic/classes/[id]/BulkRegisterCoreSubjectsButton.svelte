<script lang="ts">
  import { createQuery, createMutation } from '@tanstack/svelte-query';
  import { getCurrentYear } from '$lib/api/academic';
  import { bulkRegisterCoreSubjects } from '$lib/api/students';
  import { toast } from '$lib/stores/toast';
  import { school } from '$lib/stores/school';
  import OverrideReasonModal from '$lib/components/OverrideReasonModal.svelte';

  interface Props { classId: string; }
  const { classId }: Props = $props();

  const yearQ = createQuery({ queryKey: ['current-year'], queryFn: getCurrentYear, staleTime: 5 * 60_000 });
  const currentTerm = $derived(($yearQ.data?.terms ?? []).find(t => t.is_current));

  // Basic schools have no elective concept — every subject is already
  // non-elective by default, so this button really just means "register
  // everyone for everything." Wording reflects that instead of exposing
  // SHS-specific "elective" jargon to a Basic school admin.
  const isBasic  = $derived($school?.schoolType === 'BASIC');
  const label    = $derived(isBasic ? 'Register all students for subjects' : 'Register non-elective subjects');
  const tooltip  = $derived(isBasic
    ? 'Register every actively-enrolled student for all of this class\'s subjects'
    : 'Register every actively-enrolled student for this class\'s non-elective subjects');

  let overrideNeeded = $state(false);
  let errorMessage    = $state('');

  function isLocked(e: unknown): boolean {
    return (e as { response?: { status?: number } })?.response?.status === 423;
  }
  function detailOf(e: unknown): string | undefined {
    return (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
  }

  const registerMut = createMutation({
    mutationFn: (overrideReason: string | undefined) =>
      bulkRegisterCoreSubjects(classId, currentTerm!.id, overrideReason),
    onSuccess: (result) => {
      overrideNeeded = false;
      errorMessage = '';
      const parts = [`${result.registered} student${result.registered !== 1 ? 's' : ''} registered`];
      if (result.skipped > 0) parts.push(`${result.skipped} skipped (not enrolled this term)`);
      toast.success(parts.join(', ') + '.');
    },
    onError: (e: unknown) => {
      if (isLocked(e)) { overrideNeeded = true; errorMessage = detailOf(e) ?? 'This term is locked.'; return; }
      toast.error(detailOf(e) ?? 'Failed to register subjects.');
    },
  });
</script>

<button onclick={() => $registerMut.mutate(undefined)}
  disabled={!currentTerm || $registerMut.isPending}
  title={currentTerm ? tooltip : 'No current academic term'}
  class="shrink-0 rounded-lg border border-[var(--border)] px-3 py-1.5 text-xs font-semibold text-[var(--fg-muted)]
         transition hover:bg-[var(--hover)] hover:text-[var(--fg)] disabled:opacity-40">
  {$registerMut.isPending ? 'Registering…' : label}
</button>

<OverrideReasonModal
  open={overrideNeeded}
  errorMessage={errorMessage}
  isPending={$registerMut.isPending}
  message="This term's results are locked. Bulk-registering subjects this late requires a reason — it is written to the audit log."
  onSubmit={(reason) => $registerMut.mutate(reason)}
  onCancel={() => overrideNeeded = false}
/>
