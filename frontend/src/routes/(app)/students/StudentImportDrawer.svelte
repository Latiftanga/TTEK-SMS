<script lang="ts">
  import { portal }  from '$lib/actions/portal';
  import { importStudents, downloadImportTemplate, type ImportBatchResult } from '$lib/api/students';
  import { useQueryClient } from '@tanstack/svelte-query';

  interface Props { open: boolean; onClose: () => void; }
  const { open, onClose }: Props = $props();

  const qc = useQueryClient();

  type Stage = 'idle' | 'uploading' | 'done' | 'error';
  let stage    = $state<Stage>('idle');
  let result   = $state<ImportBatchResult | null>(null);
  let errMsg   = $state('');
  let dragging = $state(false);
  let fileInput: HTMLInputElement;

  function close() {
    onClose();
    if (stage === 'done') { stage = 'idle'; result = null; }
  }

  function onKeydown(e: KeyboardEvent) { if (e.key === 'Escape') close(); }

  async function handleFile(file: File) {
    if (!file.name.endsWith('.xlsx')) { errMsg = 'Only .xlsx files are accepted.'; stage = 'error'; return; }
    stage = 'uploading'; errMsg = '';
    try {
      result = await importStudents(file);
      qc.invalidateQueries({ queryKey: ['students'] });
      stage = 'done';
    } catch (e: unknown) {
      errMsg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? 'Import failed.';
      stage = 'error';
    }
  }

  function onFileChange(e: Event) {
    const f = (e.target as HTMLInputElement).files?.[0];
    if (f) handleFile(f);
  }

  function onDrop(e: DragEvent) {
    e.preventDefault(); dragging = false;
    const f = e.dataTransfer?.files[0];
    if (f) handleFile(f);
  }

  async function downloadTemplate() {
    const blob = await downloadImportTemplate();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a'); a.href = url; a.download = 'student_import_template.xlsx';
    a.click(); URL.revokeObjectURL(url);
  }
</script>

<svelte:window onkeydown={onKeydown} />

<div use:portal>
  {#if open}
    <div class="fixed inset-0 z-50 bg-black/30 backdrop-blur-sm"
         onclick={close} role="presentation" aria-hidden="true"></div>
  {/if}

  <div class="fixed inset-y-0 right-0 z-[60] flex w-full max-w-md flex-col border-l border-[var(--border)] bg-[var(--card)] shadow-2xl transition-transform duration-300"
       class:translate-x-full={!open}>

    <div class="flex shrink-0 items-center justify-between border-b border-[var(--border)] px-6 py-4">
      <div>
        <h2 class="text-base font-semibold text-[var(--fg)]">Import students</h2>
        <p class="mt-0.5 text-xs text-[var(--fg-muted)]">Upload the official TTEK template (.xlsx)</p>
      </div>
      <button onclick={close} aria-label="Close"
        class="rounded-xl p-2 text-[var(--fg-muted)] hover:bg-[var(--hover)] transition">
        <svg class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12"/>
        </svg>
      </button>
    </div>

    <div class="flex-1 overflow-y-auto px-6 py-6 space-y-5">

      <!-- Download template -->
      <div class="rounded-xl border border-[var(--border)] bg-[var(--hover)] p-4">
        <p class="text-xs font-semibold text-[var(--fg)]">Step 1 — Download the template</p>
        <p class="mt-1 text-xs text-[var(--fg-muted)]">Fill in student data exactly as shown. Do not add or rename columns.</p>
        <button onclick={downloadTemplate}
          class="mt-3 flex items-center gap-1.5 rounded-xl border border-[var(--border)] bg-[var(--card)] px-3 py-2 text-xs font-semibold text-[var(--fg)] transition hover:bg-[var(--hover)]">
          <svg class="h-4 w-4 text-green-600" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M16.5 12L12 16.5m0 0L7.5 12m4.5 4.5V3"/>
          </svg>
          student_import_template.xlsx
        </button>
      </div>

      <!-- Upload -->
      <div>
        <p class="mb-2 text-xs font-semibold text-[var(--fg)]">Step 2 — Upload filled template</p>
        <!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
        <label
          role="region"
          ondragover={(e) => { e.preventDefault(); dragging = true; }}
          ondragleave={() => dragging = false}
          ondrop={onDrop}
          class="flex cursor-pointer flex-col items-center gap-3 rounded-xl border-2 border-dashed px-6 py-10 text-center transition
                 {dragging ? 'border-[var(--brand)] bg-[var(--brand-dim)]' : 'border-[var(--border)] hover:border-[var(--brand)] hover:bg-[var(--hover)]'}">
          <svg class="h-8 w-8 text-[var(--fg-subtle)]" fill="none" stroke="currentColor" stroke-width="1.5" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" d="M12 16.5V9.75m0 0l3 3m-3-3l-3 3M6.75 19.5a4.5 4.5 0 01-1.41-8.775 5.25 5.25 0 0110.233-2.33 3 3 0 013.758 3.848A3.752 3.752 0 0118 19.5H6.75z"/>
          </svg>
          <div>
            <p class="text-sm font-medium text-[var(--fg)]">
              {dragging ? 'Drop to upload' : 'Drag & drop or click to select'}
            </p>
            <p class="text-xs text-[var(--fg-muted)]">.xlsx files only</p>
          </div>
          <input bind:this={fileInput} type="file" accept=".xlsx" onchange={onFileChange} class="sr-only" />
        </label>
      </div>

      <!-- Result -->
      {#if stage === 'uploading'}
        <div class="flex items-center gap-3 rounded-xl border border-[var(--border)] bg-[var(--hover)] px-4 py-3">
          <svg class="h-5 w-5 shrink-0 animate-spin text-[var(--brand)]" fill="none" viewBox="0 0 24 24">
            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/>
            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
          </svg>
          <p class="text-sm text-[var(--fg-muted)]">Processing import…</p>
        </div>

      {:else if stage === 'done' && result}
        <div class="rounded-xl border border-green-200 bg-green-50 dark:border-green-900 dark:bg-green-950/30 p-4 space-y-3">
          <div class="flex items-center gap-2">
            <svg class="h-5 w-5 text-green-600 dark:text-green-400" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
            </svg>
            <p class="text-sm font-semibold text-green-700 dark:text-green-400">Import complete</p>
          </div>
          <div class="grid grid-cols-3 gap-2 text-center text-xs">
            <div class="rounded-lg bg-white dark:bg-green-950/50 px-2 py-2">
              <p class="text-lg font-bold text-green-700 dark:text-green-300">{result.created}</p>
              <p class="text-[10px] font-medium text-green-600 dark:text-green-500">Created</p>
            </div>
            <div class="rounded-lg bg-white dark:bg-green-950/50 px-2 py-2">
              <p class="text-lg font-bold text-amber-600 dark:text-amber-400">{result.skipped}</p>
              <p class="text-[10px] font-medium text-amber-500">Skipped</p>
            </div>
            <div class="rounded-lg bg-white dark:bg-green-950/50 px-2 py-2">
              <p class="text-lg font-bold text-[var(--fg)]">{result.total_rows}</p>
              <p class="text-[10px] font-medium text-[var(--fg-muted)]">Total rows</p>
            </div>
          </div>
          {#if result.errors.length > 0}
            <div class="rounded-lg border border-red-200 bg-red-50 dark:border-red-900 dark:bg-red-950/30 p-3 max-h-40 overflow-y-auto">
              <p class="mb-1 text-[10px] font-bold uppercase tracking-wide text-red-600 dark:text-red-400">Errors</p>
              {#each result.errors as err}
                <p class="text-xs text-red-600 dark:text-red-400">Row {err.row}: {err.reason}</p>
              {/each}
            </div>
          {/if}
        </div>

      {:else if stage === 'error'}
        <div class="rounded-xl border border-red-200 bg-red-50 dark:border-red-900 dark:bg-red-950/30 px-4 py-3 text-sm text-red-600 dark:text-red-400">
          {errMsg}
        </div>
      {/if}
    </div>

    <div class="shrink-0 border-t border-[var(--border)] px-6 py-4">
      {#if stage === 'done'}
        <button onclick={close}
          class="w-full rounded-xl py-2.5 text-sm font-semibold text-white hover:opacity-90 transition" style="background: var(--brand)">
          Done
        </button>
      {:else}
        <button onclick={() => { stage = 'idle'; errMsg = ''; result = null; fileInput && (fileInput.value = ''); }}
          disabled={stage === 'uploading'}
          class="w-full rounded-xl border border-[var(--border)] py-2.5 text-sm font-medium text-[var(--fg-muted)] hover:bg-[var(--hover)] transition disabled:opacity-50">
          {stage === 'uploading' ? 'Processing…' : 'Reset'}
        </button>
      {/if}
    </div>
  </div>
</div>
