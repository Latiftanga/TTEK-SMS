<script lang="ts">
  import { createMutation, useQueryClient } from '@tanstack/svelte-query';
  import { upsertMedical, type MedicalRecord, type MedicalRecordUpsert } from '$lib/api/students';
  import { toast } from '$lib/stores/toast';

  interface Props { studentId: string; medical: MedicalRecord | null; canEdit?: boolean; }
  const { studentId, medical, canEdit = true }: Props = $props();

  const qc = useQueryClient();
  let editing = $state(false);
  let form    = $state<MedicalRecordUpsert>({
    blood_group:        medical?.blood_group ?? '',
    allergies:          medical?.allergies ?? '',
    chronic_conditions: medical?.chronic_conditions ?? '',
    medications:        medical?.medications ?? '',
    emergency_notes:    medical?.emergency_notes ?? '',
  });
  let error = $state('');

  const BLOOD_GROUPS = ['A+', 'A−', 'B+', 'B−', 'AB+', 'AB−', 'O+', 'O−'];

  const mut = createMutation({
    mutationFn: (data: MedicalRecordUpsert) => upsertMedical(studentId, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['student', studentId] });
      editing = false; error = '';
      toast.success('Medical record updated.');
    },
    onError: (e: unknown) => {
      error = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? 'Could not save.';
    },
  });

  function startEdit() {
    form = {
      blood_group:        medical?.blood_group ?? '',
      allergies:          medical?.allergies ?? '',
      chronic_conditions: medical?.chronic_conditions ?? '',
      medications:        medical?.medications ?? '',
      emergency_notes:    medical?.emergency_notes ?? '',
    };
    editing = true; error = '';
  }

  function save() {
    $mut.mutate({
      blood_group:        form.blood_group?.trim() || undefined,
      allergies:          form.allergies?.trim() || undefined,
      chronic_conditions: form.chronic_conditions?.trim() || undefined,
      medications:        form.medications?.trim() || undefined,
      emergency_notes:    form.emergency_notes?.trim() || undefined,
    });
  }
</script>

<div class="rounded-2xl border border-[var(--border)] bg-[var(--card)] p-6">
  <div class="mb-4 flex items-center justify-between">
    <h2 class="text-sm font-semibold text-[var(--fg)]">Medical information</h2>
    {#if !editing && canEdit}
      <button onclick={startEdit}
        class="flex items-center gap-1.5 rounded-xl border border-[var(--border)] px-3 py-1.5 text-xs font-medium text-[var(--fg-muted)] transition hover:bg-[var(--hover)]">
        <svg class="h-3.5 w-3.5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" d="M16.862 4.487l1.687-1.688a1.875 1.875 0 112.652 2.652L10.582 16.07a4.5 4.5 0 01-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 011.13-1.897l8.932-8.931zm0 0L19.5 7.125"/>
        </svg>
        Edit
      </button>
    {/if}
  </div>

  {#if !medical && !editing}
    <div class="rounded-xl border border-dashed border-[var(--border)] p-6 text-center">
      <svg class="mx-auto mb-2 h-8 w-8 text-[var(--fg-subtle)]" fill="none" stroke="currentColor" stroke-width="1.5" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" d="M9 12h3.75M9 15h3.75M9 18h3.75m3 .75H18a2.25 2.25 0 002.25-2.25V6.108c0-1.135-.845-2.098-1.976-2.192a48.424 48.424 0 00-1.123-.08m-5.801 0c-.065.21-.1.433-.1.664 0 .414.336.75.75.75h4.5a.75.75 0 00.75-.75 2.25 2.25 0 00-.1-.664m-5.8 0A2.251 2.251 0 0113.5 2.25H15c1.012 0 1.867.668 2.15 1.586m-5.8 0c-.376.023-.75.05-1.124.08C9.095 4.01 8.25 4.973 8.25 6.108V8.25m0 0H4.875c-.621 0-1.125.504-1.125 1.125v11.25c0 .621.504 1.125 1.125 1.125h9.75c.621 0 1.125-.504 1.125-1.125V9.375c0-.621-.504-1.125-1.125-1.125H8.25zM6.75 12h.008v.008H6.75V12zm0 3h.008v.008H6.75V15zm0 3h.008v.008H6.75V18z"/>
      </svg>
      <p class="text-sm text-[var(--fg-muted)]">No medical record yet.</p>
      {#if canEdit}
        <button onclick={startEdit}
          class="mt-2 text-xs font-medium text-[var(--brand)] hover:underline transition">
          Add medical information
        </button>
      {/if}
    </div>
  {:else if editing && canEdit}
    <div class="grid gap-4 sm:grid-cols-2">
      <div>
        <label for="mt-blood" class="label">Blood group</label>
        <select id="mt-blood" bind:value={form.blood_group} class="input">
          <option value="">Not recorded</option>
          {#each BLOOD_GROUPS as bg}<option value={bg}>{bg}</option>{/each}
        </select>
      </div>
      <div>
        <label for="mt-allergies" class="label">Known allergies</label>
        <input id="mt-allergies" bind:value={form.allergies} placeholder="e.g. Penicillin, peanuts" class="input" />
      </div>
      <div>
        <label for="mt-conditions" class="label">Chronic conditions</label>
        <input id="mt-conditions" bind:value={form.chronic_conditions} placeholder="e.g. Asthma, diabetes" class="input" />
      </div>
      <div>
        <label for="mt-medications" class="label">Current medications</label>
        <input id="mt-medications" bind:value={form.medications} placeholder="Optional" class="input" />
      </div>
      <div class="sm:col-span-2">
        <label for="mt-notes" class="label">Emergency notes</label>
        <textarea id="mt-notes" bind:value={form.emergency_notes} rows="3" placeholder="Any critical information first-aiders must know…"
          class="input resize-none"></textarea>
      </div>
    </div>
    {#if error}<p class="mt-2 text-xs text-red-500">{error}</p>{/if}
    <div class="mt-4 flex gap-2">
      <button onclick={save} disabled={$mut.isPending}
        class="rounded-xl px-4 py-2 text-sm font-semibold text-white disabled:opacity-50 transition hover:opacity-90" style="background: var(--brand)">
        {$mut.isPending ? 'Saving…' : 'Save'}
      </button>
      <button onclick={() => { editing = false; error = ''; }}
        class="rounded-xl border border-[var(--border)] px-4 py-2 text-sm text-[var(--fg-muted)] hover:bg-[var(--hover)] transition">
        Cancel
      </button>
    </div>
  {:else}
    <dl class="grid gap-x-6 gap-y-4 sm:grid-cols-2">
      <div>
        <dt class="label-read">Blood group</dt>
        <dd class="dd">{medical?.blood_group ?? '—'}</dd>
      </div>
      <div>
        <dt class="label-read">Allergies</dt>
        <dd class="dd">{medical?.allergies ?? '—'}</dd>
      </div>
      <div>
        <dt class="label-read">Chronic conditions</dt>
        <dd class="dd">{medical?.chronic_conditions ?? '—'}</dd>
      </div>
      <div>
        <dt class="label-read">Medications</dt>
        <dd class="dd">{medical?.medications ?? '—'}</dd>
      </div>
      {#if medical?.emergency_notes}
        <div class="sm:col-span-2">
          <dt class="label-read">Emergency notes</dt>
          <dd class="dd whitespace-pre-wrap">{medical.emergency_notes}</dd>
        </div>
      {/if}
    </dl>
  {/if}
</div>

<style>
  @reference "tailwindcss";
  .label      { @apply block text-xs font-medium text-[var(--fg-muted)] mb-1; }
  .label-read { @apply text-[10px] font-semibold uppercase tracking-widest text-[var(--fg-subtle)]; }
  .dd         { @apply mt-0.5 text-sm text-[var(--fg)]; }
  .input      { @apply w-full rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--fg)] placeholder:text-[var(--fg-subtle)] focus:border-[var(--brand)] focus:outline-none transition; }
</style>
