<script lang="ts">
  import PageHeader from '$lib/components/PageHeader.svelte';
  import SubjectsTab from '../SubjectsTab.svelte';
  import { setPageTitle } from '$lib/stores/title';
  setPageTitle('Subjects');
</script>
<PageHeader title="Subjects" description="Define the subject catalogue available to all classes." />
<SubjectsTab />
