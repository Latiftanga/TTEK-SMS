<script lang="ts">
  import { createMutation, useQueryClient } from '@tanstack/svelte-query';
  import { toast } from '$lib/stores/toast';
  import { grantPortalAccess, revokePortalAccess, type StudentDetail } from '$lib/api/students';
  import ConfirmModal from '$lib/components/ConfirmModal.svelte';

  interface Props { student: StudentDetail; studentId: string; }
  const { student, studentId }: Props = $props();

  const qc = useQueryClient();
  const invalidate = () => qc.invalidateQueries({ queryKey: ['student', studentId] });

  let confirmRevoke = $state(false);
  let lastResult = $state<{ admission_number: string; sms_sent: boolean } | null>(null);

  const grantMut = createMutation({
    mutationFn: () => grantPortalAccess(studentId),
    onSuccess: (res) => {
      lastResult = { admission_number: res.admission_number, sms_sent: res.sms_sent };
      invalidate();
      toast.success('Portal access granted.');
    },
    onError: (e: unknown) => {
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? 'Failed to grant access.';
      toast.error(msg);
    },
  });

  const revokeMut = createMutation({
    mutationFn: () => revokePortalAccess(studentId),
    onSuccess: () => {
      confirmRevoke = false;
      lastResult = null;
      invalidate();
      toast.success('Portal access revoked.');
    },
    onError: (e: unknown) => {
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? 'Failed to revoke access.';
      toast.error(msg);
    },
  });
</script>

<div class="rounded-xl border border-[var(--border)] bg-[var(--card)] p-5">
  <div class="mb-3 flex items-center justify-between">
    <h2 class="text-xs font-semibold uppercase tracking-widest text-[var(--fg-muted)]">Student portal access</h2>

    {#if student.has_portal_access}
      <span class="flex items-center gap-1.5 rounded-full bg-green-50 px-2.5 py-1 text-[11px] font-semibold text-green-700 dark:bg-green-950/40 dark:text-green-400">
        <span class="h-1.5 w-1.5 rounded-full bg-green-500"></span>Active
      </span>
    {:else}
      <span class="flex items-center gap-1.5 rounded-full bg-[var(--hover)] px-2.5 py-1 text-[11px] font-semibold text-[var(--fg-muted)]">
        <span class="h-1.5 w-1.5 rounded-full bg-[var(--fg-subtle)]"></span>No access
      </span>
    {/if}
  </div>

  {#if student.has_portal_access}
    <p class="text-sm text-[var(--fg-muted)]">
      {student.display_name} can log in to the student portal using admission number
      <span class="font-mono font-semibold text-[var(--fg)]">{student.admission_number}</span>.
    </p>

    <button
      onclick={() => confirmRevoke = true}
      class="mt-3 rounded-xl border border-red-200 px-3 py-1.5 text-xs font-medium text-red-600 transition hover:bg-red-50 dark:border-red-900 dark:text-red-400 dark:hover:bg-red-950/30">
      Revoke access
    </button>

  {:else}
    <p class="text-sm text-[var(--fg-muted)]">
      Granting access creates a login using the admission number
      <span class="font-mono font-semibold text-[var(--fg)]">{student.admission_number}</span>
      as both username and initial password. The primary guardian will be notified by SMS if an SMS provider is configured.
    </p>

    {#if lastResult}
      <div class="mt-3 rounded-xl border border-green-200 bg-green-50 p-3 dark:border-green-900 dark:bg-green-950/20">
        <p class="text-xs font-semibold text-green-800 dark:text-green-300">Access granted</p>
        <p class="mt-0.5 text-xs text-green-700 dark:text-green-400">
          Login: <span class="font-mono font-bold">{lastResult.admission_number}</span>
          &nbsp;·&nbsp;
          {lastResult.sms_sent ? 'Guardian notified by SMS.' : 'SMS not sent (no active SMS provider).'}
        </p>
      </div>
    {/if}

    <button
      onclick={() => $grantMut.mutate()}
      disabled={$grantMut.isPending}
      class="mt-3 rounded-xl px-4 py-2 text-sm font-semibold text-white transition hover:opacity-90 disabled:opacity-50"
      style="background-color: var(--brand)">
      {$grantMut.isPending ? 'Granting…' : 'Grant portal access'}
    </button>
  {/if}
</div>

<ConfirmModal
  open={confirmRevoke}
  title="Revoke portal access?"
  message="This will immediately block {student.first_name} from logging in."
  confirmLabel="Revoke"
  isPending={$revokeMut.isPending}
  onConfirm={() => $revokeMut.mutate()}
  onCancel={() => confirmRevoke = false}
/>
