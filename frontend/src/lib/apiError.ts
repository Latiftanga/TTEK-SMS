/** Shared axios-error helpers — the same shape already duplicated across
 * attendance/+page.svelte, SubjectRegistrationPanel.svelte, BehaviourTab.svelte,
 * SubjectRosterPanel.svelte. New call sites should use these; retrofitting
 * the existing copies is a separate, optional cleanup. */

export function detailOf(e: unknown): string | undefined {
  return (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
}

export function isLocked(e: unknown): boolean {
  return (e as { response?: { status?: number } })?.response?.status === 423;
}
