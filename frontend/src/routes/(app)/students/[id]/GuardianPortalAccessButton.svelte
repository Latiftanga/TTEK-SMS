<script lang="ts">
  import { createMutation, useQueryClient } from '@tanstack/svelte-query';
  import { toast } from '$lib/stores/toast';
  import { grantGuardianPortalAccess, revokeGuardianPortalAccess, type Guardian } from '$lib/api/students';
  import ConfirmModal from '$lib/components/ConfirmModal.svelte';

  interface Props { guardian: Guardian; studentId: string; canManage?: boolean; }
  const { guardian, studentId, canManage = true }: Props = $props();

  const qc = useQueryClient();
  const invalidate = () => qc.invalidateQueries({ queryKey: ['student', studentId] });

  let confirmRevoke = $state(false);

  const grantMut = createMutation({
    mutationFn: () => grantGuardianPortalAccess(studentId, guardian.guardian_id),
    onSuccess: (res) => {
      invalidate();
      toast.success(res.sms_sent ? 'Portal access granted — guardian notified by SMS.' : 'Portal access granted (SMS not sent — no active SMS provider).');
    },
    onError: (e: unknown) => {
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? 'Failed to grant access.';
      toast.error(msg);
    },
  });

  const revokeMut = createMutation({
    mutationFn: () => revokeGuardianPortalAccess(studentId, guardian.guardian_id),
    onSuccess: () => {
      confirmRevoke = false;
      invalidate();
      toast.success('Portal access revoked.');
    },
    onError: (e: unknown) => {
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? 'Failed to revoke access.';
      toast.error(msg);
    },
  });
</script>

{#if guardian.has_portal_access}
  <span class="rounded-full bg-green-50 px-2 py-0.5 text-[10px] font-bold text-green-700 ring-1 ring-inset ring-green-600/20 dark:bg-green-950/30 dark:text-green-400">
    Portal
  </span>
  {#if canManage}
    <button onclick={() => confirmRevoke = true} disabled={$revokeMut.isPending}
      class="rounded-lg p-1.5 text-[var(--fg-subtle)] transition hover:bg-red-50 hover:text-red-500 dark:hover:bg-red-950/30 disabled:opacity-40"
      title="Revoke parent portal access">
      <svg class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="1.75" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" d="M18.75 9v.906a2.25 2.25 0 01-1.183 1.981l-6.478 3.488M18.75 9V6a2.25 2.25 0 00-2.25-2.25H15M18.75 9h-1.5m-15-3.375c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125V9m-4.5 3.375l4.5 2.427m0 0l4.5-2.427m-4.5 2.427V21m0-8.198L3.375 9M3 12.75l1.5-1.5"/>
      </svg>
    </button>
  {/if}
{:else if canManage}
  <button onclick={() => $grantMut.mutate()} disabled={$grantMut.isPending}
    class="rounded-lg p-1.5 text-[var(--fg-subtle)] transition hover:bg-[var(--hover)] hover:text-[var(--fg)] disabled:opacity-40"
    title="Grant parent portal access">
    <svg class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="1.75" viewBox="0 0 24 24">
      <path stroke-linecap="round" stroke-linejoin="round" d="M15.75 5.25a3 3 0 013 3m3 0a6 6 0 01-7.029 5.912c-.563-.097-1.159.026-1.563.43L10.5 17.25H8.25v2.25H6v2.25H2.25v-2.818c0-.597.237-1.17.659-1.591l6.499-6.499c.404-.404.527-1 .43-1.563A6 6 0 1121.75 8.25z"/>
    </svg>
  </button>
{/if}

<ConfirmModal
  open={confirmRevoke}
  title="Revoke portal access?"
  message="{guardian.first_name} will immediately lose the ability to log in to the parent portal."
  confirmLabel="Revoke"
  isPending={$revokeMut.isPending}
  onConfirm={() => $revokeMut.mutate()}
  onCancel={() => confirmRevoke = false}
/>
