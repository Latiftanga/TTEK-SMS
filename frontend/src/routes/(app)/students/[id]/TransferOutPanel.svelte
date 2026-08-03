<script lang="ts">
  import { createQuery, createMutation, useQueryClient } from '@tanstack/svelte-query';
  import { createTransferRequest, listTransfersForStudent } from '$lib/api/students';
  import { toast } from '$lib/stores/toast';
  import { isSchoolAdmin } from '$lib/stores/permissions';
  import { detailOf } from '$lib/apiError';

  // Extracted out of ClassActionPanel.svelte (was pushing the file over the
  // 300-line cap) — transfer-out is a separate, pastoral (Category A)
  // concern from the promote/repeat/demote year-end actions, can happen any
  // time rather than once a year, and never needs the programme/stream
  // override flow those do.
  interface Props { studentId: string; canEdit?: boolean; }
  const { studentId, canEdit = true }: Props = $props();

  const qc = useQueryClient();

  const transfersQ = createQuery({
    queryKey: ['student-transfers', studentId],
    queryFn:  () => listTransfersForStudent(studentId),
    staleTime: 30_000,
  });
  const pendingTransfer = $derived(($transfersQ.data ?? []).find(t => t.status === 'PENDING') ?? null);
  const lastTransfer    = $derived(($transfersQ.data ?? [])[0] ?? null);

  let showTransfer   = $state(false);
  let transferReason = $state('');
  let transferErr    = $state('');

  const transferMut = createMutation({
    mutationFn: () => createTransferRequest(studentId, { reason: transferReason.trim() || undefined }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['student-transfers', studentId] });
      showTransfer = false; transferReason = ''; transferErr = ''; toast.success('Transfer request submitted for review.');
    },
    onError: (e: unknown) => { transferErr = detailOf(e) ?? 'Could not create transfer.'; },
  });
</script>

{#if !canEdit}
{:else if !showTransfer}
  <div class="rounded-2xl border border-[var(--border)] bg-[var(--card)] p-4">
    <p class="mb-3 text-[10px] font-bold uppercase tracking-widest text-[var(--fg-subtle)]">Transfer to another school</p>
    {#if pendingTransfer}
      <div class="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-amber-200 bg-amber-50 px-3 py-2.5 dark:border-amber-800 dark:bg-amber-950/30">
        <div>
          <p class="text-xs font-semibold text-amber-800 dark:text-amber-200">Transfer request pending review</p>
          <p class="mt-0.5 text-[10px] text-amber-700 dark:text-amber-400">
            Submitted {new Date(pendingTransfer.created_at).toLocaleDateString()}{pendingTransfer.reason ? ` — ${pendingTransfer.reason}` : ''}
          </p>
        </div>
        {#if $isSchoolAdmin}
          <a href="/admin/transfers" class="shrink-0 text-xs font-medium text-amber-800 underline hover:no-underline dark:text-amber-200">
            View in transfer queue →
          </a>
        {/if}
      </div>
    {:else}
      {#if lastTransfer && lastTransfer.status !== 'PENDING'}
        <p class="mb-2 text-[10px] text-[var(--fg-muted)]">
          Last request: {lastTransfer.status.charAt(0) + lastTransfer.status.slice(1).toLowerCase()}
          {#if lastTransfer.reviewed_at} on {new Date(lastTransfer.reviewed_at).toLocaleDateString()}{/if}
        </p>
      {/if}
      <button onclick={() => showTransfer = true}
        class="rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2.5 text-left transition hover:border-[var(--fg-subtle)]">
        <p class="text-xs font-semibold text-[var(--fg)]">Transfer out</p>
        <p class="mt-0.5 text-[10px] text-[var(--fg-muted)]">Leave this school</p>
      </button>
    {/if}
  </div>
{:else}
  <div class="rounded-2xl border border-[var(--border)] bg-[var(--card)] p-5">
    <p class="text-sm font-semibold text-[var(--fg)]">Transfer out</p>
    <p class="mt-0.5 text-xs text-[var(--fg-muted)]">Creates a request for admin review. Approval marks this student inactive.</p>
    <div class="mt-4">
      <label class="block text-xs font-medium text-[var(--fg-muted)]">Reason (optional)</label>
      <textarea bind:value={transferReason} rows="2" placeholder="e.g. Relocating to Accra"
        class="mt-1 w-full resize-none rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--fg)] placeholder:text-[var(--fg-subtle)] focus:border-[var(--brand)] focus:outline-none transition"></textarea>
    </div>
    {#if transferErr}<p class="mt-2 text-xs text-red-500">{transferErr}</p>{/if}
    <div class="mt-3 flex gap-2">
      <button onclick={() => $transferMut.mutate()} disabled={$transferMut.isPending}
        class="rounded-xl px-4 py-2 text-sm font-semibold text-white transition hover:opacity-90 disabled:opacity-50"
        style="background: var(--brand)">
        {$transferMut.isPending ? 'Submitting…' : 'Submit transfer request'}
      </button>
      <button onclick={() => { showTransfer = false; transferReason = ''; transferErr = ''; }}
        class="rounded-xl border border-[var(--border)] px-4 py-2 text-sm text-[var(--fg-muted)] hover:bg-[var(--hover)] transition">
        Cancel
      </button>
    </div>
  </div>
{/if}
