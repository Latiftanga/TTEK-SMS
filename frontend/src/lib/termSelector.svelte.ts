import { createQuery } from '@tanstack/svelte-query';
import { listAllTerms, type AcademicTerm } from './api/academic';
import { sortTermsDesc, resolveDefaultTerm, findCurrentTerm } from './academicPeriod';

export interface TermSelectorOptions {
  /** 'latest' (default) = current-else-latest picker default (Fees,
   * Behaviour — the whole point is browsing any term freely). 'none' =
   * never guess, leave termId empty until a current term exists
   * (matches the "operational" category elsewhere in the app). */
  fallback?: 'latest' | 'none';
}

/**
 * Fetch every term, sorted newest-first, and default the selection to the
 * current term once terms load — the exact block duplicated verbatim across
 * FeesTab.svelte and BehaviourTab.svelte before this was extracted.
 */
export function useTermSelector(opts: TermSelectorOptions = {}) {
  const fallback = opts.fallback ?? 'latest';
  const termsQ = createQuery({ queryKey: ['all-terms'], queryFn: listAllTerms, staleTime: 5 * 60_000 });

  // `$store` auto-subscription sugar only applies at the top level of a
  // component/.svelte.ts module, not inside a factory function like this one
  // — subscribe manually and mirror the value into a rune instead.
  let termsData = $state<AcademicTerm[] | undefined>(undefined);
  $effect(() => termsQ.subscribe(v => { termsData = v.data; }));

  const terms = $derived<AcademicTerm[]>(sortTermsDesc(termsData ?? []));

  let termId = $state('');
  $effect(() => {
    if (termId || !terms.length) return;
    termId = (fallback === 'latest' ? resolveDefaultTerm(terms) : findCurrentTerm(terms))?.id ?? '';
  });

  return {
    get terms() { return terms; },
    get termId() { return termId; },
    set termId(v: string) { termId = v; },
  };
}
