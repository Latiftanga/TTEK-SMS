<script lang="ts">
  import { goto } from '$app/navigation';
  import { auth } from '$lib/stores/auth';
  import { get } from 'svelte/store';

  const staffId = get(auth).user?.staff_member_id;
  if (staffId) {
    goto(`/admin/staff/${staffId}`, { replaceState: true });
  }
</script>

{#if !staffId}
  <!-- Non-staff users (superadmin, student portal) — show minimal account page -->
  <div class="mx-auto max-w-lg py-10 text-center text-sm text-[var(--fg-muted)]">
    No staff profile linked to this account.
    <a href="/change-password" class="ml-1 text-[var(--brand)] underline">Change password</a>
  </div>
{/if}
