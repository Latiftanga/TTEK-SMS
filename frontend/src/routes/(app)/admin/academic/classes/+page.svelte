<script lang="ts">
  import { school } from '$lib/stores/school';
  import PageHeader from '$lib/components/PageHeader.svelte';
  import ClassesTab from '../ClassesTab.svelte';
  import { setPageTitle } from '$lib/stores/title';

  const schoolType = $derived($school?.schoolType ?? 'BASIC');
  setPageTitle('Classes');
</script>
<PageHeader title="Classes" description="Manage class groups, assign teachers, and enrol students." />
<ClassesTab {schoolType} />
