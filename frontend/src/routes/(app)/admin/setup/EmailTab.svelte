<script lang="ts">
  import { createQuery, createMutation, useQueryClient } from '@tanstack/svelte-query';
  import {
    listEmailConfigs, upsertEmailConfig, activateEmailConfig, deleteEmailConfig,
    type EmailProvider, type EmailConfigPayload,
  } from '$lib/api/email';

  const qc = useQueryClient();

  const emailConfigsQ = createQuery({ queryKey: ['email-configs'], queryFn: listEmailConfigs, staleTime: 60_000 });

  const EMAIL_PROVIDERS: { value: EmailProvider; label: string }[] = [
    { value: 'SMTP',     label: 'SMTP (custom server)' },
    { value: 'SENDGRID', label: 'SendGrid'             },
    { value: 'MAILGUN',  label: 'Mailgun'              },
    { value: 'BREVO',    label: 'Brevo'                },
  ];

  // Gmail/Outlook aren't separate EmailProviders — both are plain SMTP
  // servers, so a preset just pre-fills the SMTP host/port/TLS fields and
  // surfaces the one gotcha each requires (an app password, not the normal
  // account password — Gmail dropped plain-password SMTP auth years ago,
  // and Microsoft 365 tenants often disable SMTP AUTH entirely by default).
  const SMTP_PRESETS: Record<string, {
    label: string; host: string; port: number; use_tls: boolean; help: string; docs_url: string;
  }> = {
    gmail: {
      label: 'Gmail', host: 'smtp.gmail.com', port: 587, use_tls: true,
      help: "Gmail needs an App Password, not the normal account password — turn on 2-Step Verification first, then generate one. Set Username and From Address to the same Gmail address, or Gmail will silently rewrite the From header.",
      docs_url: 'https://support.google.com/accounts/answer/185833',
    },
    outlook: {
      label: 'Outlook', host: 'smtp.office365.com', port: 587, use_tls: true,
      help: "A personal outlook.com/hotmail.com account usually needs an app password if 2-factor is on. A work or school Microsoft 365 account may have SMTP AUTH disabled by its admin — ask IT to enable it if sending fails.",
      docs_url: 'https://support.microsoft.com/en-us/account-billing/how-to-get-and-use-app-passwords-5896ed9b-4263-e681-128a-a6f2979a7944',
    },
  };

  let showForm   = $state(false);
  let form       = $state<EmailConfigPayload>({ provider: 'SMTP', host: '', port: 587, username: '', password: '', from_name: '', from_address: '', use_tls: true });
  let formError  = $state('');
  let smtpPreset = $state<string | null>(null);

  $effect(() => { if (form.provider !== 'SMTP') smtpPreset = null; });

  function applyPreset(key: string) {
    const preset = SMTP_PRESETS[key];
    form.host = preset.host;
    form.port = preset.port;
    form.use_tls = preset.use_tls;
    smtpPreset = key;
  }

  const upsertMut = createMutation({
    mutationFn: upsertEmailConfig,
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['email-configs'] }); showForm = false; formError = ''; },
    onError: (e: unknown) => { formError = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? 'Failed.'; },
  });
  const activateMut = createMutation({
    mutationFn: (id: string) => activateEmailConfig(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['email-configs'] }),
  });
  const deleteMut = createMutation({
    mutationFn: (id: string) => deleteEmailConfig(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['email-configs'] }),
  });

  const apiKeyLabel = (p: EmailProvider) =>
    p === 'SMTP' ? 'Username' : 'API Key';
  const secretLabel = (p: EmailProvider) =>
    p === 'SMTP' ? 'Password' : p === 'MAILGUN' ? 'Domain (e.g. mg.school.edu.gh)' : null;
</script>

<div class="space-y-6">
  <div class="flex items-center justify-between">
    <p class="text-sm text-[var(--fg-muted)]">Configure an email provider for receipts, report card alerts, and other notifications.</p>
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
            {#each EMAIL_PROVIDERS as p}<option value={p.value}>{p.label}</option>{/each}
          </select>
        </div>

        {#if form.provider === 'SMTP'}
          <div class="sm:col-span-2">
            <label class="mb-1 block text-xs font-medium text-[var(--fg-muted)]">Quick fill</label>
            <div class="flex flex-wrap gap-2">
              {#each Object.entries(SMTP_PRESETS) as [key, preset]}
                <button type="button" onclick={() => applyPreset(key)}
                  class="rounded-lg border px-3 py-1 text-xs font-medium transition {smtpPreset === key ? 'border-[var(--brand)] text-[var(--brand)] bg-[var(--brand)]/10' : 'border-[var(--border)] text-[var(--fg-muted)] hover:bg-[var(--hover)]'}">
                  {preset.label}
                </button>
              {/each}
            </div>
          </div>
          <div>
            <label class="mb-1 block text-xs font-medium text-[var(--fg-muted)]">SMTP Host <span class="text-red-500">*</span></label>
            <input bind:value={form.host} oninput={() => smtpPreset = null} placeholder="e.g. smtp.gmail.com"
              class="w-full rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--fg)] placeholder:text-[var(--fg-muted)] focus:border-[var(--brand)] focus:outline-none" />
          </div>
          <div>
            <label class="mb-1 block text-xs font-medium text-[var(--fg-muted)]">Port</label>
            <input bind:value={form.port} type="number" placeholder="587"
              class="w-full rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--fg)] placeholder:text-[var(--fg-muted)] focus:border-[var(--brand)] focus:outline-none" />
          </div>
          <div class="sm:col-span-2 flex items-center gap-2">
            <input type="checkbox" bind:checked={form.use_tls} id="use_tls" class="h-4 w-4 rounded" />
            <label for="use_tls" class="text-sm text-[var(--fg)]">Use TLS / STARTTLS</label>
          </div>
          {#if smtpPreset}
            <div class="sm:col-span-2 rounded-lg bg-[var(--brand)]/5 px-3 py-2">
              <p class="text-[11px] leading-relaxed text-[var(--fg-subtle)]">
                {SMTP_PRESETS[smtpPreset].help}
                <a href={SMTP_PRESETS[smtpPreset].docs_url} target="_blank" rel="noopener noreferrer"
                  class="text-[var(--brand)] hover:underline">Set up an app password →</a>
              </p>
            </div>
          {/if}
        {/if}

        <div>
          <label class="mb-1 block text-xs font-medium text-[var(--fg-muted)]">{apiKeyLabel(form.provider)}</label>
          <input bind:value={form.username} placeholder="Required"
            class="w-full rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm font-mono text-[var(--fg)] placeholder:font-sans placeholder:text-[var(--fg-muted)] focus:border-[var(--brand)] focus:outline-none" />
        </div>
        {#if secretLabel(form.provider)}
          <div>
            <label class="mb-1 block text-xs font-medium text-[var(--fg-muted)]">{secretLabel(form.provider)}</label>
            <input bind:value={form.password} type={form.provider === 'SMTP' ? 'password' : 'text'}
              class="w-full rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm font-mono text-[var(--fg)] placeholder:font-sans placeholder:text-[var(--fg-muted)] focus:border-[var(--brand)] focus:outline-none" />
          </div>
        {/if}

        <div>
          <label class="mb-1 block text-xs font-medium text-[var(--fg-muted)]">From Name</label>
          <input bind:value={form.from_name} placeholder="e.g. PRESEC Admin"
            class="w-full rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--fg)] placeholder:text-[var(--fg-muted)] focus:border-[var(--brand)] focus:outline-none" />
        </div>
        <div>
          <label class="mb-1 block text-xs font-medium text-[var(--fg-muted)]">From Address <span class="text-red-500">*</span></label>
          <input bind:value={form.from_address} type="email" placeholder="e.g. admin@school.edu.gh"
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

  {#if $emailConfigsQ.isPending}
    <div class="space-y-2">{#each [1,2] as _}<div class="h-16 animate-pulse rounded-xl bg-[var(--card)]"></div>{/each}</div>
  {:else if ($emailConfigsQ.data ?? []).length === 0}
    <div class="rounded-xl border border-dashed border-[var(--border)] p-8 text-center">
      <p class="text-sm text-[var(--fg-muted)]">No email provider configured. Add one above to enable email notifications.</p>
    </div>
  {:else}
    <div class="space-y-3">
      {#each $emailConfigsQ.data ?? [] as cfg (cfg.id)}
        <div class="flex items-center gap-4 rounded-xl border border-[var(--border)] bg-[var(--card)] px-5 py-4">
          <div class="min-w-0 flex-1">
            <p class="text-sm font-semibold text-[var(--fg)]">{EMAIL_PROVIDERS.find(p => p.value === cfg.provider)?.label ?? cfg.provider}</p>
            <p class="text-xs text-[var(--fg-muted)]">
              From: {cfg.from_name} &lt;{cfg.from_address}&gt;{cfg.host ? ` · ${cfg.host}:${cfg.port}` : ''}
            </p>
          </div>
          {#if cfg.is_active}
            <span class="shrink-0 inline-flex items-center gap-1 text-xs font-semibold text-green-600 dark:text-green-500"><svg class="h-3.5 w-3.5" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24"><polyline points="20 6 9 17 4 12"/></svg>Active</span>
          {:else}
            <button onclick={() => $activateMut.mutate(cfg.id)} disabled={$activateMut.isPending}
              class="shrink-0 rounded-lg border border-[var(--border)] px-3 py-1 text-xs font-medium text-[var(--fg-muted)] transition hover:bg-[var(--hover)] disabled:opacity-50">
              Set active
            </button>
          {/if}
          <button onclick={() => $deleteMut.mutate(cfg.id)} disabled={$deleteMut.isPending} title="Remove provider"
            class="shrink-0 rounded-lg p-1.5 text-[var(--fg-muted)] transition hover:bg-red-50 hover:text-red-500 dark:hover:bg-red-950/30 disabled:opacity-40">
            <svg class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="1.75" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M14.74 9l-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 01-2.244 2.077H8.084a2.25 2.25 0 01-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 00-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 013.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 00-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 00-7.5 0"/></svg>
          </button>
        </div>
      {/each}
    </div>
  {/if}
</div>
