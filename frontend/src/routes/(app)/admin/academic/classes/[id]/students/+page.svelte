<script lang="ts">
  import { page } from '$app/stores';
  import { getContext } from 'svelte';
  import { createQuery } from '@tanstack/svelte-query';
  import { listClasses, type SchoolClass, type AcademicTerm } from '$lib/api/academic';
  import StudentsSection from '../StudentsSection.svelte';

  const classId = $derived($page.params.id);
  const termCtx = getContext<{ termId: string; terms: AcademicTerm[] }>('classTerm');
  const selectedTermId = $derived(termCtx.termId);
  const terms          = $derived(termCtx.terms);

  const classesQuery = createQuery({ queryKey: ['classes'], queryFn: listClasses, staleTime: 5 * 60_000 });
  const classes = $derived<SchoolClass[]>($classesQuery.data ?? []);
</script>

<StudentsSection {classId} {terms} {selectedTermId} {classes} />
