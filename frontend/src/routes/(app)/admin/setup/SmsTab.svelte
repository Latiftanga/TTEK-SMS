<script lang="ts">
  import { createQuery, createMutation, useQueryClient } from '@tanstack/svelte-query';
  import {
    listSmsConfigs, upsertSmsConfig, activateSmsProvider, deleteSmsConfig,
    type SmsProvider, type SmsConfigPayload,
  } from '$lib/api/sms';
  import ConfirmModal   from '$lib/components/ConfirmModal.svelte';
  import SmsLogViewer   from './SmsLogViewer.svelte';

  const qc = useQueryClient();

  const smsConfigsQ = createQuery({ queryKey: ['sms-configs'], queryFn: listSmsConfigs, staleTime: 60_000 });

  const SMS_PROVIDERS: { value: SmsProvider; label: string }[] = [
    { value: 'AFRICAS_TALKING', label: "Africa's Talking" },
    { value: 'HUBTEL',          label: 'Hubtel'           },
    { value: 'ARKESEL',        label: 'Arkesel'          },
    { value: 'WIGAL',           label: 'WiGal'            },
    { value: 'TWILIO',          label: 'Twilio'           },
  ];
  const SMS_SECRET_LABEL: Record<SmsProvider, string | null> = {
    AFRICAS_TALKING: 'Username',
    HUBTEL:          'Client Secret',
    ARKESEL:        null,
    WIGAL:           null,
    TWILIO:          'Auth Token',
  };

  let showForm             = $state(false);
  let form                 = $state<SmsConfigPayload>({ provider: 'AFRICAS_TALKING', api_key: '', api_secret: '', sender_id: '' });
  let formError            = $state('');
  let confirmActivate      = $state<SmsProvider | null>(null);
  let confirmDelete        = $state<SmsProvider | null>(null);

  const upsertMut = createMutation({
    mutationFn: upsertSmsConfig,
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['sms-configs'] }); showForm = false; formError = ''; form = { provider: 'AFRICAS_TALKING', api_key: '', api_secret: '', sender_id: '' }; },
    onError: (e: unknown) => { formError = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? 'Failed.'; },
  });
  const activateMut = createMutation({
    mutationFn: (provider: SmsProvider) => activateSmsProvider(provider),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['sms-configs'] }),
  });
  const deleteMut = createMutation({
    mutationFn: (provider: SmsProvider) => deleteSmsConfig(provider),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['sms-configs'] }),
  });
</script>

<div class="space-y-6">
  <div class="flex items-center justify-between">
    <p class="text-sm text-[var(--fg-muted)]">Configure SMS providers for parent notifications. Only one can be active at a time.</p>
    <button onclick={() => { showForm = !showForm; formError = ''; }}
      class="flex shrink-0 items-center gap-2 rounded-xl px-4 py-2 text-sm font-semibold text-white transition hover:opacity-90" style="background-color: var(--brand)">
      <svg class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M12 4v16m8-8H4"/></svg>
      Add provider
    </button>
  </div>

  {#if showForm}
    <div class="rounded-xl border border-[var(--border)] bg-[var(--card)] p-5">
      <h2 class="mb-4 text-sm font-semibold text-[var(--fg)]">Provider Credentials</h2>
      <div class="grid gap-4 sm:grid-cols-2">
        <div class="sm:col-span-2">
          <label class="mb-1 block text-xs font-medium text-[var(--fg-muted)]">Provider</label>
          <select bind:value={form.provider}
            class="h-9 w-full rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 text-sm text-[var(--fg)] focus:border-[var(--brand)] focus:outline-none">
            {#each SMS_PROVIDERS as p}<option value={p.value}>{p.label}</option>{/each}
          </select>
        </div>
        <div>
          <label class="mb-1 block text-xs font-medium text-[var(--fg-muted)]">
            {form.provider === 'AFRICAS_TALKING' ? 'API Key' : form.provider === 'HUBTEL' ? 'Client ID' : form.provider === 'TWILIO' ? 'Account SID' : 'API Key'}
          </label>
          <input bind:value={form.api_key} placeholder="Required"
            class="w-full rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm font-mono text-[var(--fg)] placeholder:font-sans placeholder:text-[var(--fg-muted)] focus:border-[var(--brand)] focus:outline-none" />
        </div>
        {#if SMS_SECRET_LABEL[form.provider]}
          <div>
            <label class="mb-1 block text-xs font-medium text-[var(--fg-muted)]">{SMS_SECRET_LABEL[form.provider]}</label>
            <input bind:value={form.api_secret} placeholder="Required"
              class="w-full rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm font-mono text-[var(--fg)] placeholder:font-sans placeholder:text-[var(--fg-muted)] focus:border-[var(--brand)] focus:outline-none" />
          </div>
        {/if}
        <div>
          <label class="mb-1 block text-xs font-medium text-[var(--fg-muted)]">Sender ID</label>
          <input bind:value={form.sender_id} placeholder={form.provider === 'TWILIO' ? '+233XXXXXXXXX' : 'e.g. PRESEC'}
            class="w-full rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--fg)] placeholder:text-[var(--fg-muted)] focus:border-[var(--brand)] focus:outline-none" />
        </div>
      </div>
      {#if formError}<p class="mt-2 text-xs text-red-500">{formError}</p>{/if}
      <div class="mt-4 flex gap-2">
        <button onclick={() => $upsertMut.mutate(form)} disabled={$upsertMut.isPending}
          class="rounded-xl px-4 py-2 text-sm font-semibold text-white transition hover:opacity-90 disabled:opacity-50" style="background-color: var(--brand)">
          {$upsertMut.isPending ? 'Saving…' : 'Save credentials'}
        </button>
        <button onclick={() => { showForm = false; formError = ''; }}
          class="rounded-xl border border-[var(--border)] px-4 py-2 text-sm font-medium text-[var(--fg-muted)] transition hover:bg-[var(--bg)]">Cancel</button>
      </div>
    </div>
  {/if}

  {#if $smsConfigsQ.isPending}
    <div class="space-y-2">{#each [1,2] as _}<div class="h-16 animate-pulse rounded-xl bg-[var(--card)]"></div>{/each}</div>
  {:else if ($smsConfigsQ.data ?? []).length === 0}
    <div class="rounded-xl border border-dashed border-[var(--border)] p-8 text-center">
      <p class="text-sm text-[var(--fg-muted)]">No SMS provider configured. Add one above to enable parent notifications.</p>
    </div>
  {:else}
    <div class="space-y-3">
      {#each $smsConfigsQ.data ?? [] as cfg (cfg.id)}
        <div class="flex items-center gap-4 rounded-xl border border-[var(--border)] bg-[var(--card)] px-5 py-4">
          <div class="min-w-0 flex-1">
            <p class="text-sm font-semibold text-[var(--fg)]">{SMS_PROVIDERS.find(p => p.value === cfg.provider)?.label ?? cfg.provider}</p>
            <p class="text-xs text-[var(--fg-muted)]">Sender: {cfg.sender_id}</p>
          </div>
          {#if cfg.is_active}
            <span class="shrink-0 inline-flex items-center gap-1 text-xs font-semibold text-green-600 dark:text-green-500"><svg class="h-3.5 w-3.5" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24"><polyline points="20 6 9 17 4 12"/></svg>Active</span>
          {:else}
            <button onclick={() => confirmActivate = cfg.provider} disabled={$activateMut.isPending}
              class="shrink-0 rounded-lg border border-[var(--border)] px-3 py-1 text-xs font-medium text-[var(--fg-muted)] transition hover:bg-[var(--hover)] disabled:opacity-50">
              Set active
            </button>
          {/if}
          <button onclick={() => confirmDelete = cfg.provider} disabled={$deleteMut.isPending} title="Remove provider"
            class="shrink-0 rounded-lg p-1.5 text-[var(--fg-muted)] transition hover:bg-red-50 hover:text-red-500 dark:hover:bg-red-950/30 disabled:opacity-40">
            <svg class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="1.75" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M14.74 9l-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 01-2.244 2.077H8.084a2.25 2.25 0 01-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 00-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 013.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 00-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 00-7.5 0"/></svg>
          </button>
        </div>
      {/each}
    </div>
  {/if}

  <SmsLogViewer />

  <div class="rounded-xl border border-[var(--border)] bg-[var(--bg)] p-4">
    <p class="mb-3 text-xs font-semibold uppercase tracking-widest text-[var(--fg-muted)]">Credential guide</p>
    <div class="overflow-x-auto">
      <table class="w-full text-xs">
        <thead><tr class="border-b border-[var(--border)]">
          <th class="pb-2 text-left font-medium text-[var(--fg-muted)]">Provider</th>
          <th class="pb-2 text-left font-medium text-[var(--fg-muted)]">API Key</th>
          <th class="pb-2 text-left font-medium text-[var(--fg-muted)]">Secret</th>
          <th class="pb-2 text-left font-medium text-[var(--fg-muted)]">Sender</th>
        </tr></thead>
        <tbody class="divide-y divide-[var(--border)] text-[var(--fg-muted)]">
          <tr><td class="py-1.5 pr-4">Africa's Talking</td><td>AT API key</td><td>AT username</td><td>Name</td></tr>
          <tr><td class="py-1.5 pr-4">Hubtel</td><td>Client ID</td><td>Client secret</td><td>Name</td></tr>
          <tr><td class="py-1.5 pr-4">Arkesel</td><td>Arkesel API key</td><td>—</td><td>Name</td></tr>
          <tr><td class="py-1.5 pr-4">WiGal</td><td>WiGal API key</td><td>—</td><td>Name</td></tr>
          <tr><td class="py-1.5 pr-4">Twilio</td><td>Account SID</td><td>Auth Token</td><td>E.164</td></tr>
        </tbody>
      </table>
    </div>
  </div>
</div>

<ConfirmModal
  open={!!confirmActivate}
  title="Switch to {SMS_PROVIDERS.find(p => p.value === confirmActivate)?.label ?? confirmActivate}?"
  message="This will deactivate your current provider and set the selected one as active. Future notifications will use this provider."
  confirmLabel="Set active"
  variant="warning"
  isPending={$activateMut.isPending}
  onConfirm={() => { $activateMut.mutate(confirmActivate!); confirmActivate = null; }}
  onCancel={() => confirmActivate = null}
/>

<ConfirmModal
  open={!!confirmDelete}
  title="Remove provider?"
  message="The {SMS_PROVIDERS.find(p => p.value === confirmDelete)?.label ?? confirmDelete} credentials will be permanently deleted. SMS notifications will stop until a new provider is configured."
  confirmLabel="Remove"
  isPending={$deleteMut.isPending}
  onConfirm={() => { $deleteMut.mutate(confirmDelete!); confirmDelete = null; }}
  onCancel={() => confirmDelete = null}
/>
