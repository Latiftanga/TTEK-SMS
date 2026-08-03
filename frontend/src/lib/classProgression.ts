/**
 * Whether a target class continues a student's existing programme/stream
 * track — mirrors backend/app/services/class_progression.py's rules exactly
 * (single source of truth for the actual decision; the backend always
 * re-validates independently, this module only drives the picker UI).
 *
 * Ghana Basic schools ladder Creche -> Nursery -> KG -> Basic 1..9, so
 * "KG 2 -> Basic 1" is a genuine promotion with a *decreasing* year_group —
 * comparing raw year_group alone would reject the most common Basic-school
 * promotion in the country. Direction always compares the composite
 * (levelRank, year_group) ordinal below instead.
 */
import type { SchoolClass } from './api/academic';

export const CLASS_LEVEL_ORDER = ['Creche', 'Nursery', 'KG', 'Basic', 'SHS'];

export function levelRank(level: string): number {
  return CLASS_LEVEL_ORDER.indexOf(level);
}

export function classOrdinal(cls: SchoolClass): [number, number] {
  return [levelRank(cls.level), cls.year_group];
}

function ordinalCompare(a: [number, number], b: [number, number]): number {
  return a[0] !== b[0] ? a[0] - b[0] : a[1] - b[1];
}

export type PromotionMode = 'promote' | 'repeat' | 'demote';

/** None-safe: two Basic-school classes (programme_id null on both) match. */
export function programmeMismatch(from: SchoolClass, to: SchoolClass): boolean {
  return (from.programme_id ?? null) !== (to.programme_id ?? null);
}

/** Normalizes an empty string to null first, same as the backend. */
export function streamMismatch(from: SchoolClass, to: SchoolClass): boolean {
  return (from.stream || null) !== (to.stream || null);
}

function directionOk(from: SchoolClass, to: SchoolClass, mode: PromotionMode): boolean {
  const fRank = levelRank(from.level);
  const tRank = levelRank(to.level);
  if (fRank === -1 || tRank === -1) return true; // not comparable — don't block on an unrecognized level
  const cmp = ordinalCompare(classOrdinal(to), classOrdinal(from));
  if (mode === 'promote') return cmp > 0;
  if (mode === 'demote') return cmp < 0;
  return cmp === 0; // repeat
}

/** Classes that continue `from`'s programme/stream track in the right
 * direction for `mode` — the default (filtered) picker list. Excludes
 * `from` itself for promote/demote (a real progression needs a different
 * class); *includes* it for repeat, since Class isn't year-scoped in this
 * data model — "repeating" a year means a new StudentClassAssignment
 * against the very same class_id, so `from` is the only valid target. */
export function compatibleClasses(from: SchoolClass | null, classes: SchoolClass[], mode: PromotionMode): SchoolClass[] {
  if (!from) return [];
  return classes.filter(c =>
    (mode === 'repeat' || c.id !== from.id)
    && !programmeMismatch(from, c)
    && !streamMismatch(from, c)
    && directionOk(from, c, mode)
  );
}

/** Single best match — the picker's pre-selected default. Repeat always
 * resolves to `from` itself; promote/demote pick the (normally unique)
 * matching class one step in the right direction. */
export function suggestTargetClass(from: SchoolClass | null, classes: SchoolClass[], mode: PromotionMode): SchoolClass | null {
  if (!from) return null;
  if (mode === 'repeat') return from;
  return compatibleClasses(from, classes, mode)[0] ?? null;
}

export interface Mismatch {
  programme: boolean;
  stream: boolean;
  direction: 'forward' | 'same' | 'backward' | null;
}

/** Pre-submit warning info — never a gate, the server's 423 always drives
 * the actual override-reason prompt. */
export function describeMismatch(from: SchoolClass | null, to: SchoolClass | null): Mismatch {
  if (!from || !to) return { programme: false, stream: false, direction: null };
  const fRank = levelRank(from.level);
  const tRank = levelRank(to.level);
  let direction: Mismatch['direction'] = null;
  if (fRank !== -1 && tRank !== -1) {
    const cmp = ordinalCompare(classOrdinal(to), classOrdinal(from));
    direction = cmp > 0 ? 'forward' : cmp === 0 ? 'same' : 'backward';
  }
  return { programme: programmeMismatch(from, to), stream: streamMismatch(from, to), direction };
}
