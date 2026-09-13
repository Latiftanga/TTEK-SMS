<script lang="ts">
  import { setPageTitle } from '$lib/stores/title';
  import TimetableImportModal from './TimetableImportModal.svelte';

  setPageTitle('Timetable');

  let importOpen = $state(false);
</script>

<div class="space-y-6">
  <div class="flex flex-wrap items-center justify-between gap-3">
    <div>
      <h1 class="text-xl font-bold text-[var(--fg)]">Timetable</h1>
      <p class="mt-0.5 text-sm text-[var(--fg-muted)]">
        Bulk-import the whole school's weekly timetable from a FET (Free Timetabling Software) CSV export.
      </p>
    </div>
    <button onclick={() => importOpen = true}
      class="flex min-h-[44px] items-center gap-2 rounded-lg bg-[var(--brand)] px-4 py-2 text-sm font-medium text-white hover:opacity-90">
      <svg class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5"/>
      </svg>
      Import Timetable
    </button>
  </div>

  <div class="rounded-2xl border border-[var(--border)] bg-[var(--card)] p-5">
    <p class="text-sm text-[var(--fg)]">
      Set up a full timetable one class at a time is tedious once you already have a solved
      timetable in FET — export it as CSV and upload it here instead. This creates or updates
      every class's timetable slots for the academic year you choose in one pass.
    </p>
    <p class="mt-3 text-sm text-[var(--fg-muted)]">
      Before importing: each class's subjects must already be on its curriculum, and a teacher
      must already be assigned to each (class, subject) pair — a row without one is reported
      as an error so you can fix it and re-run the same file (re-importing is safe and won't
      create duplicates).
    </p>
    <p class="mt-3 text-sm text-[var(--fg-muted)]">
      To review or hand-edit a single class's timetable after importing, open that class under
      <a href="/admin/academic/classes" class="font-medium" style="color: var(--brand)">Classes</a>.
    </p>
  </div>
</div>

<TimetableImportModal open={importOpen} onClose={() => importOpen = false} />
