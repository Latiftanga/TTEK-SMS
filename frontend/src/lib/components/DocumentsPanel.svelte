<script lang="ts">
  import { createMutation, useQueryClient } from '@tanstack/svelte-query';
  import { reactiveQuery } from '$lib/query.svelte';
  import {
    listDocuments, uploadDocument, downloadDocumentBlob, deleteDocument,
    type DocumentRecord, type DocumentEntityType,
  } from '$lib/api/documents';
  import { apiError } from '$lib/utils';
  import { toast } from '$lib/stores/toast';
  import ConfirmModal from '$lib/components/ConfirmModal.svelte';

  interface Props { entityType: DocumentEntityType; entityId: string; }
  const { entityType, entityId }: Props = $props();

  const qc = useQueryClient();
  // A shared component reused on two different profile pages — entityId is a
  // prop that can change without this instance being destroyed (SvelteKit
  // reuses the component across navigations to the same route), so the
  // query key needs to react to it, same as BehaviourTab.svelte's term-scoped
  // query on this same page family.
  const listQ = reactiveQuery(() => ({
    queryKey: ['documents', entityType, entityId] as const,
    queryFn: () => listDocuments(entityType, entityId),
    staleTime: 30_000,
  }));
  // No documents.view at all (a plain subject-only Teacher, per
  // reference_data.py's TEACHER template) — distinct from an empty list,
  // which is a normal, expected state.
  const forbidden = $derived(($listQ.error as { response?: { status?: number } } | null)?.response?.status === 403);

  const DOC_TYPE_SUGGESTIONS = [
    'certificate', 'id_card', 'birth_certificate', 'medical_record',
    'contract', 'qualification', 'transfer_letter', 'photo', 'other',
  ];

  function fmtSize(bytes: number | null): string {
    if (bytes == null) return '';
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  }
  function fmtDate(d: string): string {
    return new Date(d).toLocaleDateString('en-GH', { day: 'numeric', month: 'short', year: 'numeric' });
  }

  // ── Upload ────────────────────────────────────────────────────────────────────
  let showUpload = $state(false);
  let documentType = $state('');
  let selectedFile = $state<File | null>(null);
  let uploadError = $state('');
  let fileInputEl = $state<HTMLInputElement | undefined>();

  function resetUpload() {
    documentType = ''; selectedFile = null; uploadError = '';
    if (fileInputEl) fileInputEl.value = '';
  }

  const uploadMut = createMutation({
    mutationFn: () => uploadDocument(entityType, entityId, documentType.trim(), selectedFile!),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['documents', entityType, entityId] });
      showUpload = false;
      resetUpload();
      toast.success('Document uploaded.');
    },
    onError: (e: unknown) => { uploadError = apiError(e, 'Could not upload the file.'); },
  });

  function submitUpload() {
    uploadError = '';
    if (!documentType.trim()) { uploadError = 'Document type is required.'; return; }
    if (!selectedFile)        { uploadError = 'Choose a file to upload.'; return; }
    $uploadMut.mutate();
  }

  // ── Download ──────────────────────────────────────────────────────────────────
  let downloadingId = $state<string | null>(null);
  async function download(doc: DocumentRecord) {
    if (downloadingId) return;
    downloadingId = doc.id;
    try {
      const blob = await downloadDocumentBlob(doc.id);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = doc.file_name;
      a.click();
      setTimeout(() => URL.revokeObjectURL(url), 5000);
    } catch {
      toast.error('Could not download this file.');
    } finally {
      downloadingId = null;
    }
  }

  // ── Delete ────────────────────────────────────────────────────────────────────
  let deleteTarget = $state<DocumentRecord | null>(null);
  const deleteMut = createMutation({
    mutationFn: () => deleteDocument(deleteTarget!.id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['documents', entityType, entityId] });
      deleteTarget = null;
      toast.success('Document deleted.');
    },
    onError: (e: unknown) => { toast.error(apiError(e, 'Could not delete this file.')); deleteTarget = null; },
  });
</script>

{#if $listQ.isPending}
  <div class="space-y-2">{#each [1, 2] as _}<div class="h-14 animate-pulse rounded-xl bg-[var(--hover)]"></div>{/each}</div>
{:else if forbidden}
  <div class="rounded-2xl border border-dashed border-[var(--border)] p-10 text-center">
    <p class="text-sm text-[var(--fg-muted)]">You don't have access to documents here.</p>
  </div>
{:else if $listQ.isError}
  <div class="rounded-xl bg-red-50 dark:bg-red-950/30 p-4 text-sm text-red-600 dark:text-red-400">
    Could not load documents.
    <button onclick={() => $listQ.refetch()} class="ml-1 underline">Retry</button>
  </div>
{:else}
  <div class="mb-4 flex items-center justify-end">
    <button onclick={() => { showUpload = !showUpload; resetUpload(); }}
      class="flex min-h-[44px] items-center gap-1.5 rounded-xl px-4 py-2 text-sm font-semibold text-white transition hover:opacity-90"
      style="background: var(--brand)">
      <svg class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" d="M12 4v16m8-8H4"/>
      </svg>
      Upload document
    </button>
  </div>

  {#if showUpload}
    <div class="mb-4 rounded-2xl border border-[var(--border)] bg-[var(--card)] p-5">
      <p class="mb-3 text-sm font-semibold text-[var(--fg)]">Upload a new document</p>
      <div class="grid gap-3 sm:grid-cols-2">
        <label class="block">
          <span class="lx">Document type <span class="text-red-500">*</span></span>
          <input bind:value={documentType} list="doc-type-suggestions" placeholder="e.g. certificate" class="inp mt-1" />
          <datalist id="doc-type-suggestions">
            {#each DOC_TYPE_SUGGESTIONS as t}<option value={t}></option>{/each}
          </datalist>
        </label>
        <label class="block">
          <span class="lx">File <span class="text-red-500">*</span> <span class="font-normal text-[var(--fg-subtle)]">(PDF, image, or Word — up to 10 MB)</span></span>
          <input bind:this={fileInputEl} type="file" accept=".pdf,.jpg,.jpeg,.png,.webp,.doc,.docx"
            onchange={(e) => selectedFile = (e.currentTarget as HTMLInputElement).files?.[0] ?? null}
            class="inp mt-1 file:mr-3 file:rounded-lg file:border-0 file:bg-[var(--hover)] file:px-3 file:py-1.5 file:text-xs file:font-medium file:text-[var(--fg)]" />
        </label>
      </div>
      {#if uploadError}<p class="mt-2 text-xs text-red-500">{uploadError}</p>{/if}
      <div class="mt-3 flex gap-2">
        <button onclick={submitUpload} disabled={$uploadMut.isPending}
          class="min-h-[44px] rounded-xl px-4 py-2 text-sm font-semibold text-white disabled:opacity-50 transition hover:opacity-90" style="background: var(--brand)">
          {$uploadMut.isPending ? 'Uploading…' : 'Upload'}
        </button>
        <button onclick={() => { showUpload = false; resetUpload(); }}
          class="min-h-[44px] rounded-xl border border-[var(--border)] px-4 py-2 text-sm text-[var(--fg-muted)] hover:bg-[var(--hover)] transition">
          Cancel
        </button>
      </div>
    </div>
  {/if}

  {#if ($listQ.data ?? []).length === 0}
    <div class="rounded-2xl border border-dashed border-[var(--border)] p-10 text-center">
      <p class="text-sm text-[var(--fg-muted)]">No documents uploaded yet.</p>
    </div>
  {:else}
    <div class="space-y-2">
      {#each [...($listQ.data ?? [])].sort((a, b) => b.created_at.localeCompare(a.created_at)) as doc (doc.id)}
        <div class="flex items-center justify-between gap-3 rounded-2xl border border-[var(--border)] bg-[var(--card)] p-4">
          <div class="flex min-w-0 items-center gap-3">
            <div class="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-[var(--brand-dim)]">
              <svg class="h-4.5 w-4.5 text-[var(--brand)]" fill="none" stroke="currentColor" stroke-width="1.75" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z"/>
              </svg>
            </div>
            <div class="min-w-0">
              <p class="truncate text-sm font-medium text-[var(--fg)]">{doc.file_name}</p>
              <div class="mt-0.5 flex flex-wrap items-center gap-x-2 gap-y-0.5 text-xs text-[var(--fg-subtle)]">
                <span class="rounded-full bg-[var(--hover)] px-2 py-0.5 font-medium text-[var(--fg-muted)]">{doc.document_type}</span>
                {#if doc.file_size != null}<span>{fmtSize(doc.file_size)}</span>{/if}
                <span>{fmtDate(doc.created_at)}</span>
              </div>
            </div>
          </div>
          <div class="flex shrink-0 items-center gap-1">
            <button onclick={() => download(doc)} disabled={downloadingId === doc.id}
              aria-label="Download {doc.file_name}" title="Download"
              class="flex h-11 w-11 items-center justify-center rounded-lg border border-[var(--border)] text-[var(--fg-muted)] transition hover:bg-[var(--hover)] hover:text-[var(--fg)] disabled:opacity-50">
              <svg class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M16.5 12L12 16.5m0 0L7.5 12m4.5 4.5V3"/>
              </svg>
            </button>
            <button onclick={() => deleteTarget = doc}
              aria-label="Delete {doc.file_name}" title="Delete"
              class="flex h-11 w-11 items-center justify-center rounded-lg border border-[var(--border)] text-[var(--fg-subtle)] transition hover:border-red-200 hover:bg-red-50 hover:text-red-600 dark:hover:border-red-800 dark:hover:bg-red-950/30">
              <svg class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/>
              </svg>
            </button>
          </div>
        </div>
      {/each}
    </div>
  {/if}
{/if}

<ConfirmModal
  open={!!deleteTarget}
  title="Delete this document?"
  message="{deleteTarget?.file_name ?? ''} will be permanently removed. This can't be undone."
  confirmLabel="Delete"
  isPending={$deleteMut.isPending}
  onConfirm={() => $deleteMut.mutate()}
  onCancel={() => deleteTarget = null}
/>

<style>
  @reference "tailwindcss";
  .inp { @apply w-full rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--fg)] focus:border-[var(--brand)] focus:outline-none transition; }
  .lx  { @apply block text-xs font-medium text-[var(--fg-muted)]; }
</style>
