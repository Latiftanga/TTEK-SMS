<script lang="ts">
  import { createMutation, useQueryClient } from '@tanstack/svelte-query';
  import { toast } from '$lib/stores/toast';
  import { uploadStudentPhoto, deleteStudentPhoto } from '$lib/api/students';

  interface Props {
    studentId: string;
    firstName: string;
    lastName: string;
    photoUrl: string | null;
  }
  const { studentId, firstName, lastName, photoUrl }: Props = $props();

  const qc = useQueryClient();
  const invalidate = () => qc.invalidateQueries({ queryKey: ['student', studentId] });

  let fileInput: HTMLInputElement | undefined = $state();

  function initials(first: string, last: string) {
    return (first[0] + last[0]).toUpperCase();
  }

  const uploadMut = createMutation({
    mutationFn: (file: File) => uploadStudentPhoto(studentId, file),
    onSuccess: () => { invalidate(); toast.success('Photo updated.'); },
    onError: (e: unknown) => {
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? 'Could not upload photo.';
      toast.error(msg);
    },
  });

  const deleteMut = createMutation({
    mutationFn: () => deleteStudentPhoto(studentId),
    onSuccess: () => { invalidate(); toast.success('Photo removed.'); },
    onError: () => toast.error('Could not remove photo.'),
  });

  function onFileChange(e: Event) {
    const file = (e.target as HTMLInputElement).files?.[0];
    if (file) $uploadMut.mutate(file);
    if (fileInput) fileInput.value = '';
  }
</script>

<div class="group relative h-16 w-16 shrink-0">
  {#if photoUrl}
    <img src={photoUrl} alt="{firstName} {lastName}"
      class="h-16 w-16 rounded-2xl object-cover shadow" />
  {:else}
    <div class="flex h-16 w-16 items-center justify-center rounded-2xl text-xl font-bold text-white shadow"
         style="background: linear-gradient(135deg, var(--brand) 0%, color-mix(in oklab, var(--brand) 65%, #7c3aed) 100%)">
      {initials(firstName, lastName)}
    </div>
  {/if}

  <button onclick={() => fileInput?.click()} disabled={$uploadMut.isPending}
    aria-label="Upload photo"
    class="absolute inset-0 flex items-center justify-center rounded-2xl bg-black/50 opacity-0 transition group-hover:opacity-100 disabled:opacity-100">
    <svg class="h-5 w-5 text-white" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
      <path stroke-linecap="round" stroke-linejoin="round" d="M3 9a2 2 0 012-2h.93a2 2 0 001.664-.89l.812-1.22A2 2 0 0110.07 4h3.86a2 2 0 011.664.89l.812 1.22A2 2 0 0018.07 7H19a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V9z"/>
      <circle cx="12" cy="13" r="3.5" stroke-linecap="round" stroke-linejoin="round"/>
    </svg>
  </button>

  {#if photoUrl}
    <button onclick={() => $deleteMut.mutate()} disabled={$deleteMut.isPending}
      aria-label="Remove photo"
      class="absolute -right-1.5 -top-1.5 hidden h-5 w-5 items-center justify-center rounded-full bg-red-600 text-white shadow group-hover:flex hover:bg-red-700 disabled:opacity-50">
      <svg class="h-3 w-3" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12"/>
      </svg>
    </button>
  {/if}

  <input bind:this={fileInput} type="file" accept="image/jpeg,image/png,image/webp" class="hidden" onchange={onFileChange} />
</div>
