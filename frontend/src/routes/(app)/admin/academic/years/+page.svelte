<script lang="ts">
  import PageHeader from '$lib/components/PageHeader.svelte';
  import YearsTab from '../YearsTab.svelte';
  import { setPageTitle } from '$lib/stores/title';
  setPageTitle('Years & Terms');
</script>
<PageHeader title="Years & Terms" description="Set up academic years, terms, and the school calendar." />
<YearsTab />
