import type { AcademicYear, AcademicTerm } from './api/academic';

// AcademicYear and AcademicTerm both carry id/is_current/start_date — one
// shared implementation instead of the same .find(is_current)/sort-desc
// chain retyped at ~30 call sites across the app.
//
// Two deliberate resolution policies, kept as separately-named functions
// rather than one function plus a boolean flag, so a call site can't
// silently drift from one category to the other by mistyping an option:
//
// - "Current" (findCurrentTerm/findCurrentYear): never guess. Used by
//   operational call sites (attendance, assessments, roster/registration
//   panels, dashboard) where landing on the wrong term could mean real
//   data entered against the wrong period. No current period resolves to
//   undefined — the caller shows an explicit "no current term/year" state.
// - "Default" (resolveDefaultTerm/resolveDefaultYear): current if set,
//   else the latest-dated one. Used by browsing/picker call sites (Fees,
//   Behaviour, bulk promote/graduate) where the whole point is picking
//   any period freely, so a sensible starting point beats an empty picker.
//
// Generic over T so callers that decorate terms/years with extra display
// fields (e.g. { ...term, yearName }) keep those fields through a sort or
// find — narrowing to the bare AcademicTerm/AcademicYear shape would
// silently drop them.

interface Period {
  is_current: boolean;
  start_date: string;
}

function sortDesc<T extends Period>(items: T[]): T[] {
  return [...items].sort((a, b) => b.start_date.localeCompare(a.start_date));
}

export function findCurrentTerm<T extends Period>(terms: T[]): T | undefined {
  return terms.find(t => t.is_current);
}

export function findCurrentYear<T extends Period>(years: T[]): T | undefined {
  return years.find(y => y.is_current);
}

export function sortTermsDesc<T extends Period>(terms: T[]): T[] {
  return sortDesc(terms);
}

export function sortYearsDesc<T extends Period>(years: T[]): T[] {
  return sortDesc(years);
}

export function findLatestTerm<T extends Period>(terms: T[]): T | undefined {
  return sortDesc(terms)[0];
}

export function findLatestYear<T extends Period>(years: T[]): T | undefined {
  return sortDesc(years)[0];
}

export function resolveDefaultTerm<T extends Period>(terms: T[]): T | undefined {
  return findCurrentTerm(terms) ?? findLatestTerm(terms);
}

export function resolveDefaultYear<T extends Period>(years: T[]): T | undefined {
  return findCurrentYear(years) ?? findLatestYear(years);
}

// The shape most term-level call sites actually want when they only have
// listYears()'s nested result (years[].terms).
export function flattenTerms(years: AcademicYear[]): AcademicTerm[] {
  return years.flatMap(y => y.terms);
}
