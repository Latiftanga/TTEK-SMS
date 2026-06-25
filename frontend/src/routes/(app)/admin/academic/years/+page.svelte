<script lang="ts">
  import PageHeader from '$lib/components/PageHeader.svelte';
  import YearsTab from '../YearsTab.svelte';
  import { setPageTitle } from '$lib/stores/title';
  setPageTitle('Calendar');
</script>
<PageHeader title="Calendar" description="Set up academic years, terms, and the school calendar." />
<YearsTab />
