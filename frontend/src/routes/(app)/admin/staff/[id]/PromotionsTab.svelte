<script lang="ts">
  import { createQuery, createMutation, useQueryClient } from '@tanstack/svelte-query';
  import { listPromotions, addPromotion, updatePromotion, deletePromotion, listRanks, type StaffDetail } from '$lib/api/staff';
  import { apiError } from '$lib/utils';
  import EmptyState from '$lib/components/EmptyState.svelte';
  import ConfirmModal from '$lib/components/ConfirmModal.svelte';

  interface Props { staff: StaffDetail; staffId: string; readOnly?: boolean; }
  const { staff, staffId, readOnly = false }: Props = $props();

  const qc = useQueryClient();
  const invalidate = () => qc.invalidateQueries({ queryKey: ['staff', staffId, 'promotions'] });

  const promotionsQuery = createQuery({
    queryKey: ['staff', staffId, 'promotions'],
    queryFn: () => listPromotions(staffId),
  });

  const ranksQuery = createQuery({
    queryKey: ['staff-ranks', staff.category_id],
    queryFn: () => listRanks(staff.category_id!),
    enabled: !!staff.category_id,
    staleTime: 10 * 60_000,
  });

  let showForm     = $state(false);
  let editingId    = $state<string | null>(null);
  let confirmDelId = $state<string | null>(null);
  let fromRankId = $state('');
  let toRankId   = $state('');
  let effDate    = $state('');
  let reason     = $state('');
  let formError  = $state('');

  function resetForm() {
    fromRankId = ''; toRankId = ''; effDate = ''; reason = ''; formError = '';
  }

  function startEdit(p: { id: string; from_rank_id: string | null; to_rank_id: string | null; effective_date: string; reason: string | null }) {
    editingId  = p.id;
    showForm   = false;
    fromRankId = p.from_rank_id ?? '';
    toRankId   = p.to_rank_id   ?? '';
    effDate    = p.effective_date;
    reason     = p.reason ?? '';
    formError  = '';
  }

  const addMut = createMutation({
    mutationFn: () => addPromotion(staffId, {
      from_rank_id:   fromRankId  || undefined,
      to_rank_id:     toRankId,
      effective_date: effDate,
      reason:         reason      || undefined,
    }),
    onSuccess: () => { invalidate(); showForm = false; resetForm(); },
    onError: (e) => { formError = apiError(e, 'Failed to record promotion.'); },
  });

  const editMut = createMutation({
    mutationFn: (id: string) => updatePromotion(staffId, id, {
      from_rank_id:   fromRankId  || undefined,
      to_rank_id:     toRankId    || undefined,
      effective_date: effDate     || undefined,
      reason:         reason      || undefined,
    }),
    onSuccess: () => { invalidate(); editingId = null; resetForm(); },
    onError: (e) => { formError = apiError(e, 'Failed to update promotion.'); },
  });

  const delMut = createMutation({
    mutationFn: (id: string) => deletePromotion(staffId, id),
    onSuccess: () => { invalidate(); confirmDelId = null; },
  });

  function fmtDate(d: string) {
    return new Date(d).toLocaleDateString('en-GH', { day: 'numeric', month: 'short', year: 'numeric' });
  }
</script>

<div class="space-y-4">
  {#if !readOnly}
    <div class="flex justify-end">
      <button onclick={() => { showForm = !showForm; editingId = null; resetForm(); }}
        class="flex items-center gap-2 rounded-xl px-4 py-2 text-sm font-semibold text-white transition hover:opacity-90"
        style="background-color: var(--brand)">
        <svg class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" d="M12 4v16m8-8H4"/>
        </svg>
        Record promotion
      </button>
    </div>

    {#if showForm}
      <div class="rounded-xl border border-[var(--border)] bg-[var(--card)] p-5">
        {#if !staff.category_id}
          <p class="mb-4 rounded-lg bg-amber-50 px-4 py-3 text-sm text-amber-700">
            Assign a category to this staff member first to load the rank list.
          </p>
        {/if}
        {@render promotionForm(false)}
      </div>
    {/if}
  {/if}

  {#if $promotionsQuery.isPending}
    <div class="skeleton h-24"></div>
  {:else if ($promotionsQuery.data ?? []).length === 0}
    <EmptyState
      iconPath="M2.25 18L9 11.25l4.306 4.307a11.95 11.95 0 015.814-5.519l2.74-1.22m0 0l-5.94-2.28m5.94 2.28l-2.28 5.941"
      title="No promotions recorded yet."
      description="Record rank promotions for this staff member."
      action={() => { showForm = true; resetForm(); }}
      actionLabel="Record promotion"
    />
  {:else}
    <div class="overflow-hidden rounded-xl border border-[var(--border)] bg-[var(--card)]">
      {#each $promotionsQuery.data ?? [] as p, i (p.id)}
        <div class="px-5 py-4 {i > 0 ? 'border-t border-[var(--border)]' : ''}">
          {#if editingId === p.id}
            {@render promotionForm(true, p.id)}
          {:else}
            <div class="flex items-start gap-4">
              <div class="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-[var(--brand-dim)]">
                <svg class="h-5 w-5 text-[var(--brand)]" fill="none" stroke="currentColor" stroke-width="1.75" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M2.25 18L9 11.25l4.306 4.307a11.95 11.95 0 015.814-5.519l2.74-1.22m0 0l-5.94-2.28m5.94 2.28l-2.28 5.941"/>
                </svg>
              </div>
              <div class="min-w-0 flex-1">
                <div class="flex flex-wrap items-center gap-2">
                  {#if p.from_rank_title}
                    <span class="text-sm text-[var(--fg-muted)]">{p.from_rank_title}</span>
                    <svg class="h-4 w-4 shrink-0 text-[var(--fg-muted)]" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
                      <path stroke-linecap="round" stroke-linejoin="round" d="M13.5 4.5L21 12m0 0l-7.5 7.5M21 12H3"/>
                    </svg>
                  {/if}
                  <span class="font-semibold text-[var(--fg)]">{p.to_rank_title ?? '—'}</span>
                </div>
                <p class="mt-0.5 text-xs text-[var(--fg-muted)]">
                  {fmtDate(p.effective_date)}{p.reason ? ' · ' + p.reason : ''}
                </p>
              </div>
              {#if !readOnly}
                <div class="flex shrink-0 gap-1">
                  <button onclick={() => startEdit(p)} title="Edit"
                    class="rounded-lg p-1.5 text-[var(--fg-muted)] transition hover:bg-[var(--hover)] hover:text-[var(--fg)]">
                    <svg class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="1.75" viewBox="0 0 24 24">
                      <path stroke-linecap="round" stroke-linejoin="round" d="M16.862 4.487l1.687-1.688a1.875 1.875 0 112.652 2.652L10.582 16.07a4.5 4.5 0 01-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 011.13-1.897l8.932-8.931zm0 0L19.5 7.125"/>
                    </svg>
                  </button>
                  <button onclick={() => confirmDelId = p.id} title="Delete"
                    class="rounded-lg p-1.5 text-[var(--fg-muted)] transition hover:bg-red-50 hover:text-red-500 dark:hover:bg-red-950/30">
                    <svg class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="1.75" viewBox="0 0 24 24">
                      <path stroke-linecap="round" stroke-linejoin="round" d="M14.74 9l-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 01-2.244 2.077H8.084a2.25 2.25 0 01-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 00-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 013.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 00-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 00-7.5 0"/>
                    </svg>
                  </button>
                </div>
              {/if}
            </div>
          {/if}
        </div>
      {/each}
    </div>
  {/if}
</div>

{#snippet promotionForm(isEdit: boolean, promotionId: string | undefined = undefined)}
  <div class="grid gap-4 sm:grid-cols-2">
    <div>
      <label class="mb-1 block text-xs font-medium text-[var(--fg-muted)]">
        From rank <span class="font-normal">(leave blank for first entry)</span>
      </label>
      <select bind:value={fromRankId}
        class="w-full rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--fg)] focus:border-[var(--brand)] focus:outline-none">
        <option value="">— First promotion —</option>
        {#each $ranksQuery.data ?? [] as r (r.id)}
          <option value={r.id}>{r.title}</option>
        {/each}
      </select>
    </div>

    <div>
      <label class="mb-1 block text-xs font-medium text-[var(--fg-muted)]">To rank *</label>
      <select bind:value={toRankId}
        class="w-full rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--fg)] focus:border-[var(--brand)] focus:outline-none">
        <option value="">Select rank…</option>
        {#each $ranksQuery.data ?? [] as r (r.id)}
          <option value={r.id}>{r.title}</option>
        {/each}
      </select>
    </div>

    <div>
      <label class="mb-1 block text-xs font-medium text-[var(--fg-muted)]">Effective date *</label>
      <input type="date" bind:value={effDate}
        class="w-full rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--fg)] focus:border-[var(--brand)] focus:outline-none" />
    </div>

    <div>
      <label class="mb-1 block text-xs font-medium text-[var(--fg-muted)]">
        Letter / reference <span class="font-normal">(optional)</span>
      </label>
      <input type="text" bind:value={reason} placeholder="e.g. GES/HQ/PROMO/2024/001"
        class="w-full rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--fg)] placeholder:text-[var(--fg-muted)] focus:border-[var(--brand)] focus:outline-none" />
    </div>
  </div>

  {#if formError}<p class="mt-2 text-xs text-red-500">{formError}</p>{/if}

  <div class="mt-4 flex gap-2">
    {#if isEdit && promotionId}
      <button
        onclick={() => $editMut.mutate(promotionId)}
        disabled={$editMut.isPending || !toRankId || !effDate}
        class="rounded-xl px-4 py-2 text-sm font-semibold text-white transition hover:opacity-90 disabled:opacity-50"
        style="background-color: var(--brand)">
        {$editMut.isPending ? 'Saving…' : 'Save changes'}
      </button>
      <button onclick={() => { editingId = null; resetForm(); }}
        class="rounded-xl border border-[var(--border)] px-4 py-2 text-sm font-medium text-[var(--fg-muted)] transition hover:bg-[var(--hover)]">
        Cancel
      </button>
    {:else}
      <button
        onclick={() => $addMut.mutate()}
        disabled={$addMut.isPending || !toRankId || !effDate}
        class="rounded-xl px-4 py-2 text-sm font-semibold text-white transition hover:opacity-90 disabled:opacity-50"
        style="background-color: var(--brand)">
        {$addMut.isPending ? 'Saving…' : 'Record promotion'}
      </button>
      <button onclick={() => { showForm = false; resetForm(); }}
        class="rounded-xl border border-[var(--border)] px-4 py-2 text-sm font-medium text-[var(--fg-muted)] transition hover:bg-[var(--hover)]">
        Cancel
      </button>
    {/if}
  </div>
{/snippet}

<ConfirmModal
  open={!!confirmDelId}
  title="Delete promotion record?"
  message="This promotion record will be permanently removed. This cannot be undone."
  confirmLabel="Delete"
  isPending={$delMut.isPending}
  onConfirm={() => confirmDelId && $delMut.mutate(confirmDelId)}
  onCancel={() => confirmDelId = null}
/>
