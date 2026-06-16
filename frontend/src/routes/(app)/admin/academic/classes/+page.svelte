<script lang="ts">
  import { school } from '$lib/stores/school';
  import ClassesTab from '../ClassesTab.svelte';

  const schoolType = $derived($school?.schoolType ?? 'BASIC');
</script>

<h1 class="mb-5 text-2xl font-bold tracking-tight text-[var(--fg)]">Classes</h1>
<ClassesTab {schoolType} />
