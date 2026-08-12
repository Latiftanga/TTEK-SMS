<script lang="ts">
  import { createMutation, useQueryClient } from '@tanstack/svelte-query';
  import {
    downloadImportTemplate, bulkImportStaff,
    type ImportBatchResult,
  } from '$lib/api/staff';
  import { toast } from '$lib/stores/toast';
  import { portal } from '$lib/actions/portal';

  interface Props { open: boolean; onClose: () => void; }
  const { open, onClose }: Props = $props();

  const qc = useQueryClient();

  let phase       = $state<'upload' | 'results'>('upload');
  let file        = $state<File | null>(null);
  let result      = $state<ImportBatchResult | null>(null);
  let dragOver    = $state(false);
  let downloading = $state(false);

  $effect(() => { if (!open) { phase = 'upload'; file = null; result = null; } });

  const importMut = createMutation({
    mutationFn: (f: File) => bulkImportStaff(f),
    onSuccess: (res) => {
      result = res;
      phase = 'results';
      qc.invalidateQueries({ queryKey: ['staff'] });
    },
    onError: (e: unknown) => {
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
        ?? 'Import failed. Check the file and try again.';
      toast.error(msg);
    },
  });

  function handleFiles(files: FileList | null) {
    if (!files?.length) return;
    const f = files[0];
    if (!f.name.endsWith('.xlsx')) { toast.error('Only .xlsx files are accepted.'); return; }
    file = f;
  }

  function handleDrop(e: DragEvent) {
    e.preventDefault(); dragOver = false;
    handleFiles(e.dataTransfer?.files ?? null);
  }

  async function download() {
    downloading = true;
    try { await downloadImportTemplate(); }
    catch { toast.error('Could not download template. Try again.'); }
    finally { downloading = false; }
  }
</script>

{#if open}
  <div use:portal class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
    <div class="flex max-h-[90vh] w-full max-w-lg flex-col rounded-2xl border border-[var(--border)] bg-[var(--card)] shadow-2xl">

      {#if phase === 'upload'}
        <div class="flex shrink-0 items-center justify-between border-b border-[var(--border)] px-6 py-4">
          <h2 class="text-lg font-semibold text-[var(--fg)]">Import Staff</h2>
          <button onclick={onClose} aria-label="Close"
            class="flex min-h-[44px] min-w-[44px] items-center justify-center rounded-lg text-[var(--fg-subtle)] transition hover:bg-[var(--hover)] hover:text-[var(--fg)]">
            <svg class="h-5 w-5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12"/>
            </svg>
          </button>
        </div>

        <div class="space-y-3 overflow-y-auto px-6 py-5">
          <!-- Step 1 -->
          <div class="flex items-start gap-3 rounded-xl border border-[var(--border)] bg-[var(--bg)] p-4">
            <div class="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-[color-mix(in_srgb,var(--brand)_12%,transparent)] text-xs font-bold text-[var(--brand)]">1</div>
            <div class="min-w-0 flex-1">
              <p class="text-sm font-medium text-[var(--fg)]">Download the Excel template</p>
              <p class="mt-0.5 text-xs text-[var(--fg-muted)]">Pre-filled with your school's staff positions as a dropdown. Fill in one row per staff member.</p>
              <button onclick={download} disabled={downloading}
                class="mt-2.5 flex min-h-[44px] items-center gap-1.5 rounded-lg border border-[var(--border)] bg-[var(--card)] px-3 text-xs font-medium text-[var(--fg)] transition hover:bg-[var(--hover)] disabled:opacity-50">
                <svg class="h-3.5 w-3.5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M16.5 12 12 16.5m0 0L7.5 12m4.5 4.5V3"/>
                </svg>
                {downloading ? 'Downloading…' : 'Download template (.xlsx)'}
              </button>
            </div>
          </div>

          <!-- Step 2 -->
          <div class="flex items-start gap-3 rounded-xl border border-[var(--border)] bg-[var(--bg)] p-4">
            <div class="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-[color-mix(in_srgb,var(--brand)_12%,transparent)] text-xs font-bold text-[var(--brand)]">2</div>
            <div class="min-w-0 flex-1">
              <p class="text-sm font-medium text-[var(--fg)]">Fill it in, then upload</p>
              <!-- svelte-ignore a11y_no_static_element_interactions -->
              <label
                ondragover={(e) => { e.preventDefault(); dragOver = true; }}
                ondragleave={() => dragOver = false}
                ondrop={handleDrop}
                class="mt-2.5 flex cursor-pointer flex-col items-center gap-2 rounded-xl border-2 border-dashed px-4 py-5 text-center transition
                       {dragOver
                         ? 'border-[var(--brand)] bg-[color-mix(in_srgb,var(--brand)_6%,transparent)]'
                         : 'border-[var(--border)] hover:border-[var(--brand)] hover:bg-[var(--hover)]'}"
              >
                <input type="file" accept=".xlsx" class="sr-only" onchange={(e) => handleFiles(e.currentTarget.files)} />
                {#if file}
                  <svg class="h-7 w-7 text-emerald-500" fill="none" stroke="currentColor" stroke-width="1.5" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
                  </svg>
                  <p class="text-sm font-medium text-[var(--fg)]">{file.name}</p>
                  <p class="text-xs text-[var(--fg-muted)]">{(file.size / 1024).toFixed(1)} KB · click to change</p>
                {:else}
                  <svg class="h-7 w-7 text-[var(--fg-subtle)]" fill="none" stroke="currentColor" stroke-width="1.5" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5"/>
                  </svg>
                  <p class="text-sm font-medium text-[var(--fg)]">Drop your .xlsx here</p>
                  <p class="text-xs text-[var(--fg-muted)]">or click to browse</p>
                {/if}
              </label>
            </div>
          </div>
        </div>

        <div class="flex shrink-0 items-center justify-end gap-3 border-t border-[var(--border)] px-6 py-4">
          <button onclick={onClose} class="min-h-[44px] rounded-lg px-4 py-2 text-sm text-[var(--fg-muted)] hover:bg-[var(--hover)]">Cancel</button>
          <button onclick={() => file && $importMut.mutate(file)} disabled={!file || $importMut.isPending}
            class="flex min-h-[44px] items-center gap-2 rounded-lg bg-[var(--brand)] px-4 py-2 text-sm font-medium text-white disabled:opacity-40 hover:opacity-90">
            {#if $importMut.isPending}
              <svg class="h-4 w-4 animate-spin" fill="none" viewBox="0 0 24 24">
                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/>
                <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z"/>
              </svg>
              Importing…
            {:else}
              Upload &amp; Import
            {/if}
          </button>
        </div>

      {:else}
        <!-- Results -->
        {@const allOk = result!.failed === 0 && result!.warnings.length === 0}
        {@const hasWarnings = result!.warnings.length > 0}
        <div class="flex shrink-0 items-center justify-between border-b border-[var(--border)] px-6 py-4">
          <h2 class="text-lg font-semibold text-[var(--fg)]">Import Complete</h2>
          <button onclick={onClose} aria-label="Close"
            class="flex min-h-[44px] min-w-[44px] items-center justify-center rounded-lg text-[var(--fg-subtle)] transition hover:bg-[var(--hover)] hover:text-[var(--fg)]">
            <svg class="h-5 w-5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12"/>
            </svg>
          </button>
        </div>

        <div class="space-y-4 overflow-y-auto px-6 py-5">
          <!-- Summary banner -->
          <div class="flex items-center gap-3 rounded-xl border p-4
                      {allOk
                        ? 'border-emerald-200 bg-emerald-50 dark:border-emerald-800 dark:bg-emerald-950/30'
                        : 'border-amber-200 bg-amber-50 dark:border-amber-800 dark:bg-amber-950/30'}">
            <svg class="h-8 w-8 shrink-0 {allOk ? 'text-emerald-500' : 'text-amber-500'}"
                 fill="none" stroke="currentColor" stroke-width="1.5" viewBox="0 0 24 24">
              {#if allOk}
                <path stroke-linecap="round" stroke-linejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
              {:else}
                <path stroke-linecap="round" stroke-linejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z"/>
              {/if}
            </svg>
            <div>
              <p class="text-sm font-semibold {allOk ? 'text-emerald-800 dark:text-emerald-200' : 'text-amber-800 dark:text-amber-200'}">
                {result!.created} of {result!.total_rows} record{result!.total_rows !== 1 ? 's' : ''} imported
              </p>
              {#if result!.failed > 0}
                <p class="mt-0.5 text-xs text-red-600 dark:text-red-400">
                  {result!.failed} row{result!.failed !== 1 ? 's' : ''} failed — see errors below
                </p>
              {/if}
              {#if hasWarnings}
                <p class="mt-0.5 text-xs text-amber-600 dark:text-amber-400">
                  {result!.warnings.length} imported without a position — see warnings below
                </p>
              {/if}
            </div>
          </div>

          <!-- Warnings table -->
          {#if hasWarnings}
            <div>
              <p class="mb-1.5 text-xs font-semibold uppercase tracking-wide text-amber-600 dark:text-amber-400">
                Warnings — imported but needs attention
              </p>
              <div class="max-h-40 overflow-y-auto rounded-xl border border-amber-200 dark:border-amber-800">
                <table class="w-full text-xs">
                  <thead class="sticky top-0 bg-amber-50 dark:bg-amber-950/40">
                    <tr class="border-b border-amber-200 dark:border-amber-800">
                      <th class="w-12 px-3 py-2 text-left font-semibold text-amber-700 dark:text-amber-300">Row</th>
                      <th class="px-3 py-2 text-left font-semibold text-amber-700 dark:text-amber-300">Staff #</th>
                      <th class="px-3 py-2 text-left font-semibold text-amber-700 dark:text-amber-300">Note</th>
                    </tr>
                  </thead>
                  <tbody class="divide-y divide-amber-100 dark:divide-amber-900">
                    {#each result!.warnings as w}
                      <tr class="bg-[var(--card)]">
                        <td class="px-3 py-2 font-mono text-[var(--fg-muted)]">{w.row}</td>
                        <td class="px-3 py-2 text-[var(--fg-muted)]">{w.ref ?? '—'}</td>
                        <td class="px-3 py-2 text-amber-700 dark:text-amber-300">{w.warning}</td>
                      </tr>
                    {/each}
                  </tbody>
                </table>
              </div>
            </div>
          {/if}

          <!-- Errors table -->
          {#if result!.errors.length > 0}
            <div>
              <p class="mb-1.5 text-xs font-semibold uppercase tracking-wide text-red-600 dark:text-red-400">
                Errors — rows not imported
              </p>
              <div class="max-h-40 overflow-y-auto rounded-xl border border-[var(--border)]">
                <table class="w-full text-xs">
                  <thead class="sticky top-0 bg-[var(--bg)]">
                    <tr class="border-b border-[var(--border)]">
                      <th class="w-12 px-3 py-2 text-left font-semibold uppercase tracking-wide text-[var(--fg-muted)]">Row</th>
                      <th class="px-3 py-2 text-left font-semibold uppercase tracking-wide text-[var(--fg-muted)]">Ref</th>
                      <th class="px-3 py-2 text-left font-semibold uppercase tracking-wide text-[var(--fg-muted)]">Reason</th>
                    </tr>
                  </thead>
                  <tbody class="divide-y divide-[var(--border)]">
                    {#each result!.errors as err}
                      <tr class="bg-[var(--card)]">
                        <td class="px-3 py-2 font-mono text-[var(--fg-muted)]">{err.row}</td>
                        <td class="px-3 py-2 text-[var(--fg-muted)]">{err.ref ?? '—'}</td>
                        <td class="px-3 py-2 text-red-600 dark:text-red-400">{err.error ?? 'Unknown error'}</td>
                      </tr>
                    {/each}
                  </tbody>
                </table>
              </div>
            </div>
          {/if}
        </div>

        <div class="flex shrink-0 items-center justify-between border-t border-[var(--border)] px-6 py-4">
          <button onclick={() => { phase = 'upload'; file = null; result = null; }}
            class="min-h-[44px] rounded-lg border border-[var(--border)] px-4 py-2 text-sm text-[var(--fg)] hover:bg-[var(--hover)]">
            Import another
          </button>
          <button onclick={onClose}
            class="min-h-[44px] rounded-lg bg-[var(--brand)] px-4 py-2 text-sm font-medium text-white hover:opacity-90">
            Done
          </button>
        </div>
      {/if}

    </div>
  </div>
{/if}
