<script lang="ts">
  import { createMutation, useQueryClient } from '@tanstack/svelte-query';
  import { reactiveQuery } from '$lib/query.svelte';
  import {
    listCurriculumMaterials, uploadCurriculumMaterial, deleteCurriculumMaterial, extractCurriculumUnits,
    type CurriculumMaterial,
  } from '$lib/api/curriculumMaterials';
  import { apiError } from '$lib/utils';
  import { toast } from '$lib/stores/toast';
  import ConfirmModal from '$lib/components/ConfirmModal.svelte';
  import CurriculumUnitsAdmin from './CurriculumUnitsAdmin.svelte';

  interface Props { classSubjectId: string; }
  const { classSubjectId }: Props = $props();

  const DOCUMENT_TYPES = ['TEXTBOOK', 'TEACHER_MANUAL', 'SYLLABUS'];

  const materialsQ = reactiveQuery(() => ({
    queryKey: ['curriculum-materials', classSubjectId] as const,
    queryFn: () => listCurriculumMaterials(classSubjectId),
    staleTime: 30_000,
  }));
  const materials = $derived($materialsQ.data ?? []);

  let documentType = $state('TEXTBOOK');
  let fileInput = $state<HTMLInputElement | null>(null);
  let deleteTarget = $state<CurriculumMaterial | null>(null);
  let expandedUnitsId = $state<string | null>(null);

  const qc = useQueryClient();
  function invalidate() { qc.invalidateQueries({ queryKey: ['curriculum-materials', classSubjectId] }); }

  const uploadMut = createMutation({
    mutationFn: (file: File) => uploadCurriculumMaterial(classSubjectId, documentType, file),
    onSuccess: () => { invalidate(); toast.success('Uploaded — extracting text in the background.'); if (fileInput) fileInput.value = ''; },
    onError: (e: unknown) => toast.error(apiError(e, 'Could not upload this file.')),
  });

  const deleteMut = createMutation({
    mutationFn: (id: string) => deleteCurriculumMaterial(id),
    onSuccess: () => { invalidate(); deleteTarget = null; toast.success('Removed.'); },
    onError: (e: unknown) => { toast.error(apiError(e, 'Could not remove this file.')); deleteTarget = null; },
  });

  // Admin-triggered, not automatic on upload — a large document can cost
  // 10-30 sequential AI calls, a conscious action rather than a surprise
  // side effect of every upload.
  const extractUnitsMut = createMutation({
    mutationFn: (id: string) => extractCurriculumUnits(id),
    onSuccess: () => { invalidate(); toast.success('Extracting week-by-week content in the background.'); },
    onError: (e: unknown) => toast.error(apiError(e, 'Could not start extraction.')),
  });

  function handleFileChange(e: Event) {
    const file = (e.currentTarget as HTMLInputElement).files?.[0];
    if (file) $uploadMut.mutate(file);
  }

  function statusLabel(m: CurriculumMaterial): { text: string; cls: string } {
    switch (m.extraction_status) {
      case 'DONE': return { text: 'Ready', cls: 'text-green-600 dark:text-green-400' };
      case 'PENDING': return { text: 'Processing…', cls: 'text-[var(--fg-muted)]' };
      case 'EMPTY': return { text: 'Needs a text-based PDF', cls: 'text-amber-600 dark:text-amber-400' };
      case 'FAILED': return { text: 'Failed to process', cls: 'text-red-600 dark:text-red-400' };
    }
  }

  function unitStatusLabel(m: CurriculumMaterial): { text: string; cls: string } | null {
    switch (m.unit_extraction_status) {
      case 'DONE': return { text: 'Week-by-week content ready', cls: 'text-green-600 dark:text-green-400' };
      case 'PENDING': return null; // never triggered, or currently running — the button below covers this
      case 'EMPTY': return { text: 'No teaching units could be identified', cls: 'text-amber-600 dark:text-amber-400' };
      case 'FAILED': return { text: 'Extraction incomplete', cls: 'text-red-600 dark:text-red-400' };
    }
  }
</script>

<div class="space-y-2">
  <p class="text-[10px] font-bold uppercase tracking-widest text-[var(--fg-subtle)]">Curriculum materials</p>
  <p class="text-xs text-[var(--fg-muted)]">
    Upload the textbook, teacher manual, or syllabus for this subject — the AI
    lesson-planning assistant grounds its answers in these instead of generic knowledge.
  </p>

  {#if materials.length > 0}
    <div class="space-y-1.5">
      {#each materials as m (m.id)}
        {@const status = statusLabel(m)}
        {@const unitStatus = unitStatusLabel(m)}
        <div class="rounded-xl border border-[var(--border)] bg-[var(--card)] px-3 py-2">
          <div class="flex items-center justify-between gap-2">
            <div class="min-w-0">
              <p class="truncate text-xs font-medium text-[var(--fg)]">{m.document_type} — {m.file_name}</p>
              <p class="text-[11px] {status.cls}">
                {status.text}
                {#if m.extraction_status === 'EMPTY' || m.extraction_status === 'FAILED'}
                  {#if m.extraction_error}<span class="text-[var(--fg-subtle)]"> — {m.extraction_error}</span>{/if}
                {/if}
              </p>
              {#if unitStatus}
                <p class="text-[11px] {unitStatus.cls}">
                  {unitStatus.text}
                  {#if m.unit_extraction_status === 'FAILED' && m.unit_extraction_error}
                    <span class="text-[var(--fg-subtle)]"> — {m.unit_extraction_error}</span>
                  {/if}
                </p>
              {/if}
            </div>
            <div class="flex shrink-0 items-center gap-1">
              {#if m.extraction_status === 'DONE'}
                {#if m.unit_extraction_status === 'DONE' || m.unit_extraction_status === 'FAILED'}
                  <button onclick={() => expandedUnitsId = expandedUnitsId === m.id ? null : m.id}
                    class="min-h-[36px] rounded-lg border border-[var(--border)] px-2.5 text-[11px] font-semibold text-[var(--fg-muted)] hover:bg-[var(--hover)]">
                    {expandedUnitsId === m.id ? 'Hide' : 'Review'}
                  </button>
                {/if}
                <button onclick={() => $extractUnitsMut.mutate(m.id)} disabled={$extractUnitsMut.isPending}
                  class="min-h-[36px] rounded-lg border border-[var(--border)] px-2.5 text-[11px] font-semibold text-[var(--fg-muted)] hover:bg-[var(--hover)] disabled:opacity-50">
                  {m.unit_extraction_status === 'DONE' || m.unit_extraction_status === 'FAILED' ? 'Re-extract' : 'Extract week-by-week content'}
                </button>
              {/if}
              <button onclick={() => deleteTarget = m} aria-label="Remove"
                class="flex min-h-[44px] min-w-[44px] shrink-0 items-center justify-center rounded-lg text-[var(--fg-muted)] transition hover:bg-red-50 hover:text-red-500 dark:hover:bg-red-950/30">
                <svg class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="1.75" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M14.74 9l-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 01-2.244 2.077H8.084a2.25 2.25 0 01-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 00-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 013.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 00-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 00-7.5 0"/></svg>
              </button>
            </div>
          </div>
          {#if expandedUnitsId === m.id}
            <div class="mt-2 border-t border-[var(--border)] pt-2">
              <CurriculumUnitsAdmin materialId={m.id} />
            </div>
          {/if}
        </div>
      {/each}
    </div>
  {/if}

  <div class="flex flex-wrap items-center gap-2">
    <select bind:value={documentType} class="min-h-[44px] rounded-xl border border-[var(--border)] bg-[var(--bg)] px-2 text-xs text-[var(--fg)] focus:border-[var(--brand)] focus:outline-none">
      {#each DOCUMENT_TYPES as t}<option value={t}>{t}</option>{/each}
    </select>
    <label class="relative min-h-[44px] cursor-pointer rounded-xl border border-[var(--border)] px-3 py-2 text-xs font-semibold text-[var(--fg-muted)] transition hover:bg-[var(--hover)]">
      {$uploadMut.isPending ? 'Uploading…' : '+ Upload PDF'}
      <input bind:this={fileInput} type="file" accept="application/pdf" onchange={handleFileChange}
        disabled={$uploadMut.isPending}
        class="absolute inset-0 h-full w-full cursor-pointer opacity-0" />
    </label>
  </div>
</div>

<ConfirmModal
  open={!!deleteTarget}
  title="Remove this material?"
  message="{deleteTarget?.file_name} will be permanently removed, along with everything the AI assistant learned from it."
  confirmLabel="Remove"
  variant="danger"
  isPending={$deleteMut.isPending}
  onConfirm={() => deleteTarget && $deleteMut.mutate(deleteTarget.id)}
  onCancel={() => deleteTarget = null}
/>
