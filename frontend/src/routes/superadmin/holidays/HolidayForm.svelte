<script lang="ts">
  import { createMutation, useQueryClient } from '@tanstack/svelte-query';
  import { createHoliday, updateHoliday, type HolidayRead } from '$lib/api/holidays';
  import { toast } from '$lib/stores/toast';
  import { portal } from '$lib/actions/portal';
  import { apiError } from '$lib/utils';
  import ConfirmModal from '$lib/components/ConfirmModal.svelte';

  interface Props {
    open: boolean;
    holiday?: HolidayRead | null;   // present => edit mode, absent => create mode
    onSuccess: () => void;
    onCancel: () => void;
  }
  const { open, holiday = null, onSuccess, onCancel }: Props = $props();
  const isEdit = $derived(!!holiday);

  const qc = useQueryClient();

  function emptyForm() {
    return { name: '', date: '', is_recurring: true, description: '' };
  }
  function formFromHoliday(h: HolidayRead) {
    return { name: h.name, date: h.date, is_recurring: h.is_recurring, description: h.description ?? '' };
  }

  let form = $state(emptyForm());
  let original = emptyForm();
  let formError = $state('');

  $effect(() => {
    if (open) {
      const seed = holiday ? formFromHoliday(holiday) : emptyForm();
      form = { ...seed };
      original = seed;
      formError = '';
    }
  });

  const hasUnsaved = $derived(JSON.stringify(form) !== JSON.stringify(original));
  let confirmDiscard = $state(false);

  function requestClose() {
    if (hasUnsaved) confirmDiscard = true;
    else onCancel();
  }

  const createMut = createMutation({
    mutationFn: createHoliday,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['holidays'] });
      toast.success('Holiday added.');
      onSuccess();
    },
    onError: (e) => { formError = apiError(e, 'Failed to add holiday.'); toast.error(formError); },
  });

  const updateMut = createMutation({
    mutationFn: (payload: Parameters<typeof updateHoliday>[1]) => updateHoliday(holiday!.id, payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['holidays'] });
      toast.success('Holiday updated.');
      onSuccess();
    },
    onError: (e) => { formError = apiError(e, 'Failed to update holiday.'); toast.error(formError); },
  });

  const isPending = $derived($createMut.isPending || $updateMut.isPending);

  function submit() {
    formError = '';
    if (!form.name || !form.date) {
      formError = 'Name and date are required.';
      return;
    }
    const payload = {
      name: form.name, date: form.date,
      is_recurring: form.is_recurring,
      description: form.description || undefined,
    };
    if (isEdit) $updateMut.mutate(payload);
    else $createMut.mutate(payload);
  }

  const inp = 'w-full min-h-[44px] rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--fg)] placeholder:text-[var(--fg-muted)] focus:border-[var(--brand)] focus:outline-none disabled:opacity-50';
  const lbl = 'mb-1 block text-xs font-medium text-[var(--fg-muted)]';
</script>

{#if open}
  <div use:portal class="contents">
  <div class="fixed inset-0 z-40 bg-black/40 backdrop-blur-sm" onclick={requestClose} role="none"></div>

  <div class="fixed inset-y-0 right-0 z-50 flex w-full max-w-[420px] flex-col
              border-l border-[var(--border)] bg-[var(--card)]"
       style="box-shadow: -8px 0 40px rgba(0,0,0,0.14);">

    <div class="flex shrink-0 items-center justify-between border-b border-[var(--border)] px-6 py-4">
      <div>
        <h2 class="text-sm font-semibold text-[var(--fg)]">{isEdit ? holiday?.name : 'Add a holiday'}</h2>
        <p class="mt-0.5 text-xs text-[var(--fg-muted)]">Applies to every school on the platform.</p>
      </div>
      <button onclick={requestClose} aria-label="Close"
        class="flex min-h-[44px] min-w-[44px] items-center justify-center rounded-lg text-[var(--fg-muted)]
               transition hover:bg-[var(--hover)] hover:text-[var(--fg)]">
        <svg class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12"/>
        </svg>
      </button>
    </div>

    <div class="flex-1 overflow-y-auto px-6 py-5">
      <div class="mb-4">
        <label class={lbl} for="hol-name">Name</label>
        <input id="hol-name" class={inp} bind:value={form.name} placeholder="e.g. Independence Day" />
      </div>
      <div class="mb-4">
        <label class={lbl} for="hol-date">Date</label>
        <input id="hol-date" type="date" class={inp} bind:value={form.date} />
      </div>
      <div class="mb-4">
        <label class="flex min-h-[44px] cursor-pointer items-center gap-2 text-sm text-[var(--fg)]">
          <input type="checkbox" bind:checked={form.is_recurring} class="h-4 w-4 rounded border-[var(--border)]" />
          Recurring every year (same month/day)
        </label>
        <p class="mt-1 text-xs text-[var(--fg-subtle)]">
          {#if form.is_recurring}
            Fixed-date holiday — matched on this month/day in every future year's calendar.
          {:else}
            Moveable holiday (e.g. Easter, Eid) — matched on this exact date only; add a new row each year.
          {/if}
        </p>
      </div>
      <div class="mb-4">
        <label class={lbl} for="hol-desc">Description (optional)</label>
        <textarea id="hol-desc" class={inp} rows="2" bind:value={form.description}></textarea>
      </div>
    </div>

    <div class="shrink-0 border-t border-[var(--border)] px-6 py-4">
      {#if formError}
        <p class="mb-3 text-xs text-red-500">{formError}</p>
      {/if}
      <div class="flex gap-2">
        <button onclick={submit} disabled={isPending}
          class="min-h-[44px] flex-1 rounded-xl py-2.5 text-sm font-semibold text-white transition
                 hover:opacity-90 disabled:opacity-50"
          style="background-color: var(--brand)">
          {#if isPending}
            {isEdit ? 'Saving…' : 'Adding…'}
          {:else}
            {isEdit ? 'Save changes' : 'Add holiday'}
          {/if}
        </button>
        <button onclick={requestClose}
          class="min-h-[44px] rounded-xl border border-[var(--border)] px-4 py-2 text-sm font-medium
                 text-[var(--fg-muted)] transition hover:bg-[var(--hover)]">
          Cancel
        </button>
      </div>
    </div>

  </div>
  </div>

  <ConfirmModal
    open={confirmDiscard}
    title={isEdit ? 'Discard changes?' : 'Discard new holiday?'}
    message="You've made changes that haven't been saved yet. Closing now will lose them."
    confirmLabel="Discard"
    variant="warning"
    onConfirm={() => { confirmDiscard = false; onCancel(); }}
    onCancel={() => confirmDiscard = false}
  />
{/if}
