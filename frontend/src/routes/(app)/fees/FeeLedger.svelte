<script lang="ts">
  import {
    ghs, PAYMENT_METHOD_LABELS, DISCOUNT_TYPE_LABELS,
    type FeeRecord, type FeePayment, type FeeDiscount,
  } from '$lib/api/fees';

  interface Props {
    records:         FeeRecord[];
    sortedPayments:  FeePayment[];
    discountsByRecord: Map<string, FeeDiscount[]>;
    paidByRecord:    Map<string, number>;
    termName:        string;
    isAdmin:         boolean;
    remaining:       (r: FeeRecord) => number;
    onPay:           (r: FeeRecord) => void;
    onDiscount:      (r: FeeRecord) => void;
  }
  const {
    records, sortedPayments, discountsByRecord, paidByRecord,
    termName, isAdmin, remaining, onPay, onDiscount,
  }: Props = $props();

  function recPct(r: FeeRecord): number {
    const due = Number(r.amount_due);
    if (due <= 0) return 0;
    return Math.min(100, Math.round(((paidByRecord.get(r.id) ?? 0) / due) * 100));
  }
</script>

<!-- ── Fee records ─────────────────────────────────────────────────────────────── -->
{#if records.length > 0}
  <div class="rounded-2xl border border-[var(--border)] bg-[var(--card)]">
    <div class="border-b border-[var(--border)] px-5 py-3">
      <h2 class="text-sm font-semibold text-[var(--fg)]">Fee Records — {termName}</h2>
    </div>
    <div class="divide-y divide-[var(--border)]">
      {#each records as r (r.id)}
        {@const paid       = paidByRecord.get(r.id) ?? 0}
        {@const rem        = remaining(r)}
        {@const rdiscounts = discountsByRecord.get(r.id) ?? []}
        {@const pct        = recPct(r)}

        <div class="px-5 py-3">
          <div class="flex items-start gap-4">
            <div class="min-w-0 flex-1">
              <p class="text-sm font-medium text-[var(--fg)]">{r.fee_type_name}</p>
              {#if r.due_date}
                <p class="text-xs text-[var(--fg-muted)]">Due {r.due_date}</p>
              {/if}
              {#each rdiscounts as d (d.id)}
                <p class="text-xs text-blue-600 dark:text-blue-400">
                  {DISCOUNT_TYPE_LABELS[d.discount_type]}:
                  {d.percentage ? d.percentage + '%' : ghs(d.amount ?? 0)}
                  {#if d.reason} — {d.reason}{/if}
                </p>
              {/each}
              {#if !r.is_waived && Number(r.amount_due) > 0}
                <div class="mt-1.5 h-1 w-20 overflow-hidden rounded-full bg-[var(--hover)]">
                  <div class="h-full rounded-full {pct >= 100 ? 'bg-green-500' : ''}"
                       style="width: {pct}%; {pct < 100 ? 'background: var(--brand)' : ''}">
                  </div>
                </div>
              {/if}
            </div>
            <div class="tabular-nums text-right text-sm text-[var(--fg)]">{ghs(r.amount_due)}</div>
            <div class="tabular-nums text-right text-sm text-green-600 dark:text-green-400">
              {paid > 0 ? ghs(paid) : '—'}
            </div>
            <div class="flex shrink-0 items-center gap-2">
              {#if r.is_waived}
                <span class="rounded-full border border-[var(--border)] px-2 py-0.5 text-xs text-[var(--fg-muted)]">Waived</span>
              {:else if rem <= 0}
                <span class="text-xs font-semibold text-green-600 dark:text-green-400">✓ Paid</span>
              {:else}
                <button onclick={() => onPay(r)}
                  class="rounded-lg border border-[var(--brand)] px-2.5 py-1 text-xs font-semibold
                         text-[var(--brand)] transition hover:bg-[var(--brand)] hover:text-white">
                  Pay
                </button>
              {/if}
              {#if isAdmin && !r.is_waived}
                <button onclick={() => onDiscount(r)}
                  class="rounded-lg border border-[var(--border)] px-2.5 py-1 text-xs font-semibold
                         text-[var(--fg-muted)] transition hover:border-[var(--brand)] hover:text-[var(--brand)]">
                  Discount
                </button>
              {/if}
            </div>
          </div>
        </div>
      {/each}
    </div>
  </div>
{/if}

<!-- ── Payment history ─────────────────────────────────────────────────────────── -->
{#if sortedPayments.length > 0}
  <div class="rounded-2xl border border-[var(--border)] bg-[var(--card)]">
    <div class="border-b border-[var(--border)] px-5 py-3">
      <h2 class="text-sm font-semibold text-[var(--fg)]">Payment History</h2>
    </div>
    <div class="divide-y divide-[var(--border)]">
      {#each sortedPayments as p (p.id)}
        {@const recName = records.find(r => r.id === p.fee_record_id)?.fee_type_name ?? ''}
        <div class="flex items-center gap-4 px-5 py-3">
          <div class="min-w-0 flex-1">
            <p class="text-sm text-[var(--fg)]">{recName || 'Fee payment'}</p>
            <p class="text-xs text-[var(--fg-muted)]">
              {PAYMENT_METHOD_LABELS[p.payment_method]}{p.reference_number ? ' · ' + p.reference_number : ''}
            </p>
          </div>
          <div class="text-right">
            <p class="text-sm font-semibold text-green-600 dark:text-green-400">{ghs(p.amount_paid)}</p>
            <p class="text-xs text-[var(--fg-muted)]">{p.payment_date}</p>
          </div>
        </div>
      {/each}
    </div>
  </div>
{/if}
