<script lang="ts">
  import { userRole } from '$lib/stores/permissions';
  import { setPageTitle } from '$lib/stores/title';
  import AdminStudentsView   from './AdminStudentsView.svelte';
  import TeacherStudentsView from './TeacherStudentsView.svelte';
  setPageTitle('Students');
</script>

{#if $userRole === 'teacher'}
  <TeacherStudentsView />
{:else}
  <AdminStudentsView />
{/if}
