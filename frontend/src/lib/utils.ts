export function apiError(e: unknown, fallback = 'Something went wrong.'): string {
  return (
    (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? fallback
  );
}
