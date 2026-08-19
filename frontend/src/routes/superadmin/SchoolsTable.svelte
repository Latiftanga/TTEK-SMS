<script lang="ts">
  import type { SchoolSummary } from '$lib/api/schools';

  interface Props {
    schools: SchoolSummary[];
    platformDomain: string | null;
    loginUrl: (subdomain: string | null) => string | null;
    togglingId: string | null;
    onEdit: (s: SchoolSummary) => void;
    onToggleActive: (s: SchoolSummary) => void;
    onDelete: (s: SchoolSummary) => void;
  }
  const { schools, platformDomain, loginUrl, togglingId, onEdit, onToggleActive, onDelete }: Props = $props();

  function fmtLastLogin(iso: string | null): string {
    if (!iso) return 'Never';
    return new Date(iso).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' });
  }

  // Delete is only ever a live option for an already-disabled, genuinely
  // empty school — matches the backend's own hard preconditions exactly
  // (services/school.py::delete_school). Disabled elsewhere with a tooltip
  // explaining why, rather than hidden, so it's discoverable.
  function deletable(s: SchoolSummary): boolean {
    return !s.is_active && s.student_count === 0 && s.staff_count === 0;
  }
  function deleteDisabledReason(s: SchoolSummary): string {
    if (s.is_active) return 'Disable this school before it can be deleted.';
    return `Cannot delete: ${s.student_count} student(s), ${s.staff_count} staff member(s) still on record.`;
  }
</script>

<div class="overflow-x-auto">
  <table class="w-full text-sm">
    <thead>
      <tr class="border-b border-[var(--border)] bg-[var(--hover)]/30 text-left text-[10px] font-semibold uppercase tracking-widest text-[var(--fg-subtle)]">
        <th class="px-4 py-2.5">School</th>
        <th class="hidden px-4 py-2.5 sm:table-cell">Type</th>
        <th class="px-4 py-2.5">Sign-in link</th>
        <th class="hidden px-4 py-2.5 md:table-cell">Students</th>
        <th class="hidden px-4 py-2.5 md:table-cell">Staff</th>
        <th class="hidden px-4 py-2.5 lg:table-cell">Last login</th>
        <th class="px-4 py-2.5">Status</th>
        <th class="px-4 py-2.5"><span class="sr-only">Actions</span></th>
      </tr>
    </thead>
    <tbody class="divide-y divide-[var(--border)]">
      {#each schools as s (s.id)}
        <tr>
          <td class="px-4 py-3">
            <p class="font-medium text-[var(--fg)]">{s.name}</p>
            <p class="font-mono text-[10px] text-[var(--fg-subtle)]">{s.school_code}</p>
          </td>
          <td class="hidden px-4 py-3 text-xs text-[var(--fg-muted)] sm:table-cell">{s.school_type}</td>
          <td class="px-4 py-3">
            {#if loginUrl(s.subdomain)}
              <a href={loginUrl(s.subdomain)} target="_blank" rel="noopener noreferrer"
                class="font-mono text-xs text-[var(--brand)] hover:underline">
                {s.subdomain}.{platformDomain}
              </a>
            {:else if s.subdomain && !platformDomain}
              <span class="text-xs text-[var(--fg-subtle)]" title="Set PUBLIC_PLATFORM_DOMAIN to show a real link">
                {s.subdomain}.<em class="not-italic">(domain not set)</em>
              </span>
            {:else}
              <span class="text-xs text-[var(--fg-subtle)]">—</span>
            {/if}
          </td>
          <td class="hidden px-4 py-3 text-xs text-[var(--fg-muted)] md:table-cell">{s.student_count}</td>
          <td class="hidden px-4 py-3 text-xs text-[var(--fg-muted)] md:table-cell">{s.staff_count}</td>
          <td class="hidden px-4 py-3 text-xs text-[var(--fg-muted)] lg:table-cell">{fmtLastLogin(s.last_login_at)}</td>
          <td class="px-4 py-3">
            <button onclick={() => onToggleActive(s)} disabled={togglingId === s.id}
              class="min-h-[44px] rounded-full px-2.5 py-0.5 text-[10px] font-semibold transition disabled:opacity-50
                {s.is_active ? 'bg-green-50 text-green-700 hover:bg-green-100 dark:bg-green-950/40 dark:text-green-400' : 'bg-[var(--hover)] text-[var(--fg-muted)] hover:bg-[var(--border)]'}">
              {togglingId === s.id ? '…' : s.is_active ? 'Active' : 'Inactive'}
            </button>
          </td>
          <td class="px-4 py-3 text-right whitespace-nowrap">
            <button onclick={() => onEdit(s)}
              class="min-h-[44px] rounded-lg px-3 py-1.5 text-xs font-medium text-[var(--fg-muted)]
                     transition hover:bg-[var(--hover)] hover:text-[var(--fg)]">
              Edit
            </button>
            <button onclick={() => onDelete(s)} disabled={!deletable(s)}
              title={deletable(s) ? undefined : deleteDisabledReason(s)}
              class="min-h-[44px] rounded-lg px-3 py-1.5 text-xs font-medium transition
                     {deletable(s)
                       ? 'text-red-600 hover:bg-red-50 dark:text-red-400 dark:hover:bg-red-950/30'
                       : 'cursor-not-allowed text-[var(--fg-subtle)] opacity-50'}">
              Delete
            </button>
          </td>
        </tr>
      {/each}
    </tbody>
  </table>
</div>
