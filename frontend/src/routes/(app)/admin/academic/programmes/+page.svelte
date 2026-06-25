<script lang="ts">
  import PageHeader from '$lib/components/PageHeader.svelte';
  import ProgrammesTab from '../ProgrammesTab.svelte';
  import { setPageTitle } from '$lib/stores/title';
  setPageTitle('Programmes');
</script>
<PageHeader title="Programmes" description="Configure SHS programmes (Science, Arts, Business, etc.)." />
<ProgrammesTab />
