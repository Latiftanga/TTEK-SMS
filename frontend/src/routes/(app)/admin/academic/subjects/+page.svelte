<script lang="ts">
  import PageHeader from '$lib/components/PageHeader.svelte';
  import SubjectsTab from '../SubjectsTab.svelte';
  import { setPageTitle } from '$lib/stores/title';
  import { school } from '$lib/stores/school';
  setPageTitle('Subjects');
  const schoolType = $derived($school?.schoolType ?? 'BASIC');
</script>
<PageHeader title="Subjects" description="Define the subject catalogue available to all classes." />
<SubjectsTab {schoolType} />
