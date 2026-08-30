<script lang="ts">
  import { createQuery, createMutation, useQueryClient } from '@tanstack/svelte-query';
  import { reactiveQuery } from '$lib/query.svelte';
  import {
    listAiProviders, listAiConfigs, saveAiConfig,
    activateAiProvider, deleteAiConfig, testAiProvider,
    listAiPlatformConfigs, saveAiPlatformConfig,
    activateAiPlatformProvider, deleteAiPlatformConfig, testAiPlatformProvider,
    type AiProvider, type AiConfigCreate,
  } from '$lib/api/ai';

  // platformDefault: renders the exact same UI against Tagnatek's own
  // shared config (superadmin-only /ai/platform-default/* endpoints)
  // instead of a school's own /ai/configs/* — see routers/ai_platform.py.
  interface Props { platformDefault?: boolean }
  const { platformDefault = false }: Props = $props();

  const scope = $derived(platformDefault ? 'platform' : 'school');
  const listConfigsFn = $derived(platformDefault ? listAiPlatformConfigs : listAiConfigs);
  const saveConfigFn = $derived(platformDefault ? saveAiPlatformConfig : saveAiConfig);
  const activateFn = $derived(platformDefault ? activateAiPlatformProvider : activateAiProvider);
  const deleteFn = $derived(platformDefault ? deleteAiPlatformConfig : deleteAiConfig);
  const testFn = $derived(platformDefault ? testAiPlatformProvider : testAiProvider);

  const qc = useQueryClient();

  const providersQ = createQuery({ queryKey: ['ai-providers'], queryFn: listAiProviders, staleTime: Infinity });
  const configsQ = reactiveQuery(() => ({
    queryKey: ['ai-configs', scope] as const,
    queryFn: () => listConfigsFn(),
    staleTime: 60_000,
  }));

  let selectedProvider = $state<AiProvider>('GEMINI');
  let apiKey           = $state('');
  let modelOverride    = $state('');
  let dailyLimit       = $state(10);
  let showForm         = $state(false);
  let formError        = $state('');
  let testResult       = $state<{ ok: boolean; message: string } | null>(null);

  const saveMut = createMutation({
    mutationFn: (data: AiConfigCreate) => saveConfigFn(data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['ai-configs', scope] });
      showForm = false; formError = ''; apiKey = ''; modelOverride = '';
    },
    onError: (e: unknown) => {
      formError = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? 'Failed to save.';
    },
  });

  const activateMut = createMutation({
    mutationFn: (provider: AiProvider) => activateFn(provider),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['ai-configs', scope] }),
  });

  const deleteMut = createMutation({
    mutationFn: (provider: AiProvider) => deleteFn(provider),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['ai-configs', scope] }),
  });

  const testMut = createMutation({
    mutationFn: () => testFn(),
    onSuccess: (r) => { testResult = { ok: r.ok, message: r.message }; },
    onError: () => { testResult = { ok: false, message: 'Request failed.' }; },
  });

  function openForm(provider: AiProvider) {
    selectedProvider = provider;
    apiKey = ''; modelOverride = ''; dailyLimit = 10; formError = '';
    showForm = true;
  }

  function handleSave() {
    if (!apiKey.trim()) { formError = 'API key is required.'; return; }
    $saveMut.mutate({
      provider: selectedProvider,
      api_key: apiKey.trim(),
      model: modelOverride.trim() || undefined,
      daily_limit_per_teacher: dailyLimit,
    });
  }

  const configuredMap = $derived(
    Object.fromEntries(($configsQ.data ?? []).map(c => [c.provider, c]))
  );
</script>

<div class="space-y-6">
  <div class="flex items-start justify-between gap-4">
    <div>
      <p class="text-sm text-[var(--fg-muted)]">
        {#if platformDefault}
          The platform-default provider — every school with no AI key of its
          own automatically falls back to this one, so lesson planning works
          out of the box with zero setup on their end.
        {:else}
          Enable AI-powered lesson note generation for your teachers.
          Teachers pay nothing — the cost comes from this API key.
        {/if}
        <span class="font-medium text-[var(--fg)]">Gemini and Groq have generous free tiers.</span>
      </p>
    </div>
  </div>

  <!-- Provider cards -->
  {#if $providersQ.isPending}
    <div class="grid gap-3 sm:grid-cols-2">{#each [1,2,3,4] as _}<div class="h-32 animate-pulse rounded-xl bg-[var(--card)]"></div>{/each}</div>
  {:else}
    <div class="grid gap-3 sm:grid-cols-2">
      {#each $providersQ.data ?? [] as info (info.provider)}
        {@const cfg = configuredMap[info.provider]}
        <div class="rounded-xl border bg-[var(--card)] p-4 transition"
             style="border-color: {cfg?.is_active ? 'var(--brand)' : 'var(--border)'}">
          <div class="flex items-start justify-between gap-2">
            <div class="min-w-0 flex-1">
              <div class="flex items-center gap-2 flex-wrap">
                <span class="text-sm font-semibold text-[var(--fg)]">{info.name}</span>
                {#if info.free_tier}
                  <span class="inline-flex items-center gap-1 text-[10px] font-bold uppercase tracking-wide text-green-600 dark:text-green-500">
                    <svg class="h-3 w-3" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24"><polyline points="20 6 9 17 4 12"/></svg>
                    Free tier
                  </span>
                {:else}
                  <span class="rounded-full bg-[var(--hover)] px-2 py-0.5 text-[10px] font-medium text-[var(--fg-muted)]">Paid</span>
                {/if}
              </div>
              <p class="mt-1 text-xs text-[var(--fg-muted)] leading-relaxed">{info.description}</p>
              {#if info.free_tier}
                <p class="mt-1 text-[11px] text-green-600 dark:text-green-400">{info.free_tier}</p>
              {/if}
              <p class="mt-1 text-[11px] text-[var(--fg-subtle)]">Default: <span class="font-mono">{info.default_model}</span></p>
            </div>
          </div>

          <div class="mt-3 flex items-center gap-2 flex-wrap">
            {#if cfg?.is_active}
              <span class="flex items-center gap-1 text-xs font-semibold text-green-600 dark:text-green-500">
                <svg class="h-3.5 w-3.5" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24"><polyline points="20 6 9 17 4 12"/></svg>
                Active
              </span>
            {:else if cfg}
              <button onclick={() => $activateMut.mutate(info.provider)} disabled={$activateMut.isPending}
                class="rounded-lg border border-[var(--border)] px-3 py-1 text-xs font-medium text-[var(--fg-muted)] transition hover:bg-[var(--hover)] disabled:opacity-50">
                Set active
              </button>
            {/if}

            {#if cfg}
              <button onclick={() => openForm(info.provider)}
                class="rounded-lg border border-[var(--border)] px-3 py-1 text-xs font-medium text-[var(--fg-muted)] transition hover:bg-[var(--hover)]">
                Update key
              </button>
              <button onclick={() => $deleteMut.mutate(info.provider)} disabled={$deleteMut.isPending}
                class="rounded-lg p-1.5 text-[var(--fg-muted)] transition hover:bg-red-50 hover:text-red-500 dark:hover:bg-red-950/30 disabled:opacity-40" title="Remove">
                <svg class="h-3.5 w-3.5" fill="none" stroke="currentColor" stroke-width="1.75" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M14.74 9l-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 01-2.244 2.077H8.084a2.25 2.25 0 01-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 00-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 013.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 00-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 00-7.5 0"/></svg>
              </button>
            {:else}
              <a href={info.docs_url} target="_blank" rel="noopener noreferrer"
                class="text-[11px] text-[var(--brand)] hover:underline transition">Get free API key →</a>
              <button onclick={() => openForm(info.provider)}
                class="ml-auto rounded-lg px-3 py-1 text-xs font-semibold text-white transition hover:opacity-90" style="background: var(--brand)">
                Configure
              </button>
            {/if}
          </div>
        </div>
      {/each}
    </div>
  {/if}

  <!-- Credential form -->
  {#if showForm}
    {@const info = ($providersQ.data ?? []).find(p => p.provider === selectedProvider)}
    <div class="rounded-xl border border-[var(--brand)]/30 bg-[var(--card)] p-5">
      <h2 class="mb-4 text-sm font-semibold text-[var(--fg)]">
        Configure {info?.name ?? selectedProvider}
      </h2>
      <div class="grid gap-4 sm:grid-cols-2">
        <div class="sm:col-span-2">
          <label class="mb-1 block text-xs font-medium text-[var(--fg-muted)]">
            API Key <span class="text-red-500">*</span>
          </label>
          <input bind:value={apiKey} type="password" placeholder="Paste your API key"
            class="w-full rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm font-mono text-[var(--fg)] placeholder:font-sans placeholder:text-[var(--fg-muted)] focus:border-[var(--brand)] focus:outline-none" />
          {#if info?.docs_url}
            <p class="mt-1 text-[11px] text-[var(--fg-subtle)]">
              Don't have one?
              <a href={info.docs_url} target="_blank" rel="noopener noreferrer" class="text-[var(--brand)] hover:underline">Get it here →</a>
            </p>
          {/if}
        </div>
        <div>
          <label class="mb-1 block text-xs font-medium text-[var(--fg-muted)]">
            Model override <span class="text-[var(--fg-subtle)]">(optional)</span>
          </label>
          <input bind:value={modelOverride} placeholder={info?.default_model ?? ''}
            class="w-full rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm font-mono text-[var(--fg)] placeholder:text-[var(--fg-subtle)] focus:border-[var(--brand)] focus:outline-none" />
          <p class="mt-0.5 text-[11px] text-[var(--fg-subtle)]">Leave blank to use the default above</p>
        </div>
        <div>
          <label class="mb-1 block text-xs font-medium text-[var(--fg-muted)]">Daily limit per teacher</label>
          <input type="number" bind:value={dailyLimit} min="1" max="200"
            class="w-full rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--fg)] focus:border-[var(--brand)] focus:outline-none" />
          <p class="mt-0.5 text-[11px] text-[var(--fg-subtle)]">Max lesson notes per teacher per day</p>
        </div>
      </div>

      {#if formError}<p class="mt-2 text-xs text-red-500">{formError}</p>{/if}

      <div class="mt-4 flex gap-2">
        <button onclick={handleSave} disabled={$saveMut.isPending}
          class="rounded-xl px-4 py-2 text-sm font-semibold text-white transition hover:opacity-90 disabled:opacity-50" style="background: var(--brand)">
          {$saveMut.isPending ? 'Saving…' : 'Save & close'}
        </button>
        <button onclick={() => { showForm = false; formError = ''; }}
          class="rounded-xl border border-[var(--border)] px-4 py-2 text-sm font-medium text-[var(--fg-muted)] transition hover:bg-[var(--hover)]">
          Cancel
        </button>
      </div>
    </div>
  {/if}

  <!-- Test active provider -->
  {#if ($configsQ.data ?? []).some(c => c.is_active)}
    <div class="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
      <div class="flex items-center justify-between gap-4">
        <div>
          <p class="text-sm font-medium text-[var(--fg)]">Test active provider</p>
          <p class="text-xs text-[var(--fg-muted)]">Sends a trivial prompt to verify the API key is working.</p>
        </div>
        <button onclick={() => { testResult = null; $testMut.mutate(); }} disabled={$testMut.isPending}
          class="shrink-0 rounded-xl border border-[var(--border)] px-4 py-2 text-sm font-medium text-[var(--fg)] transition hover:bg-[var(--hover)] disabled:opacity-50">
          {$testMut.isPending ? 'Testing…' : 'Run test'}
        </button>
      </div>
      {#if testResult}
        <div class="mt-3 flex items-start gap-2 rounded-xl px-3 py-2.5 text-sm"
             style="background: {testResult.ok ? 'color-mix(in oklab, #22c55e 10%, transparent)' : 'color-mix(in oklab, #ef4444 10%, transparent)'}">
          <svg class="mt-0.5 h-4 w-4 shrink-0" fill="currentColor" viewBox="0 0 24 24"
               style="color: {testResult.ok ? '#22c55e' : '#ef4444'}">
            {#if testResult.ok}
              <path fill-rule="evenodd" d="M2.25 12c0-5.385 4.365-9.75 9.75-9.75s9.75 4.365 9.75 9.75-4.365 9.75-9.75 9.75S2.25 17.385 2.25 12zm13.36-1.814a.75.75 0 10-1.22-.872l-3.236 4.53L9.53 12.22a.75.75 0 00-1.06 1.06l2.25 2.25a.75.75 0 001.14-.094l3.75-5.25z" clip-rule="evenodd"/>
            {:else}
              <path fill-rule="evenodd" d="M12 2.25c-5.385 0-9.75 4.365-9.75 9.75s4.365 9.75 9.75 9.75 9.75-4.365 9.75-9.75S17.385 2.25 12 2.25zm-1.72 6.97a.75.75 0 10-1.06 1.06L10.94 12l-1.72 1.72a.75.75 0 101.06 1.06L12 13.06l1.72 1.72a.75.75 0 101.06-1.06L13.06 12l1.72-1.72a.75.75 0 10-1.06-1.06L12 10.94l-1.72-1.72z" clip-rule="evenodd"/>
            {/if}
          </svg>
          <div>
            <p class="font-medium" style="color: {testResult.ok ? '#15803d' : '#dc2626'}">{testResult.ok ? 'Connected!' : 'Failed'}</p>
            <p class="text-xs mt-0.5 text-[var(--fg-muted)]">{testResult.message}</p>
          </div>
        </div>
      {/if}
    </div>
  {/if}
</div>
