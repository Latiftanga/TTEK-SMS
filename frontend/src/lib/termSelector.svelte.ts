import { createQuery } from '@tanstack/svelte-query';
import { listAllTerms, type AcademicTerm } from './api/academic';

/**
 * Fetch every term, sorted newest-first, and default the selection to the
 * current term once terms load — the exact block duplicated verbatim across
 * FeesTab.svelte and BehaviourTab.svelte before this was extracted.
 */
export function useTermSelector() {
  const termsQ = createQuery({ queryKey: ['all-terms'], queryFn: listAllTerms, staleTime: 5 * 60_000 });

  // `$store` auto-subscription sugar only applies at the top level of a
  // component/.svelte.ts module, not inside a factory function like this one
  // — subscribe manually and mirror the value into a rune instead.
  let termsData = $state<AcademicTerm[] | undefined>(undefined);
  $effect(() => termsQ.subscribe(v => { termsData = v.data; }));

  const terms = $derived<AcademicTerm[]>([...(termsData ?? [])].sort((a, b) => b.start_date.localeCompare(a.start_date)));

  let termId = $state('');
  $effect(() => {
    if (!termId && terms.length) termId = terms.find(t => t.is_current)?.id ?? terms[0]?.id ?? '';
  });

  return {
    get terms() { return terms; },
    get termId() { return termId; },
    set termId(v: string) { termId = v; },
  };
}
