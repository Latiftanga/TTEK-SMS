<script lang="ts">
  import { school } from '$lib/stores/school';
  import ClassesTab from '../ClassesTab.svelte';

  const schoolType = $derived($school?.schoolType ?? 'BASIC');
</script>

<ClassesTab {schoolType} />
