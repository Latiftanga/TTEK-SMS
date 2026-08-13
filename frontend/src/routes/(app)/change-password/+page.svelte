<script lang="ts">
  import { setPageTitle } from '$lib/stores/title';
  import ChangePasswordForm from '$lib/components/ChangePasswordForm.svelte';
  setPageTitle('Change Password');
</script>

<div class="mx-auto max-w-md">
  <div class="mb-6">
    <h1 class="text-2xl font-bold text-[var(--fg)]">Change Password</h1>
    <p class="mt-1 text-sm text-[var(--fg-muted)]">Update your account password. You'll stay signed in on this device.</p>
  </div>

  <ChangePasswordForm />
</div>
