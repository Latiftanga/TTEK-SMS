<script lang="ts">
  import type { InviteResult } from '$lib/api/staff';

  interface Props {
    result: InviteResult | null;
    phone: string | null | undefined;
    displayName: string;
    schoolLoginUrl: string | null;
    onDismiss: () => void;
  }
  const { result, phone, displayName, schoolLoginUrl, onDismiss }: Props = $props();

  let linkCopied = $state(false);
  function copyLink() {
    if (!result) return;
    navigator.clipboard.writeText(result.invite_link).then(() => {
      linkCopied = true;
      setTimeout(() => linkCopied = false, 2000);
    });
  }
</script>

{#if result}
  <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
    <div class="w-full max-w-sm rounded-2xl border border-[var(--border)] bg-[var(--card)] p-6 shadow-2xl">
      <div class="mb-4 flex h-10 w-10 items-center justify-center rounded-full bg-emerald-100 dark:bg-emerald-900/40">
        <svg class="h-5 w-5 text-emerald-600 dark:text-emerald-400" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
        </svg>
      </div>

      <h2 class="text-base font-semibold text-[var(--fg)]">Invitation created</h2>

      {#if result.sms_sent}
        <p class="mt-1 text-sm text-[var(--fg-muted)]">
          An SMS with the link was sent to <span class="font-medium text-[var(--fg)]">{phone}</span>.
          You can also share this link directly:
        </p>
      {:else}
        <p class="mt-1 text-sm text-[var(--fg-muted)]">
          Share this link with <span class="font-medium text-[var(--fg)]">{displayName}</span>.
          They'll use it to set their password and activate their account.
          {#if phone}
            <span class="text-amber-600 dark:text-amber-400"> (No SMS provider configured — share manually.)</span>
          {/if}
        </p>
      {/if}

      <div class="mt-4 flex items-center gap-2 rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2.5">
        <p class="flex-1 truncate font-mono text-xs text-[var(--fg)]">{result.invite_link}</p>
        <button onclick={copyLink}
          class="shrink-0 rounded-lg border border-[var(--border)] px-3 py-1 text-xs font-medium
                 text-[var(--fg-muted)] transition hover:bg-[var(--hover)]">
          {linkCopied ? '✓ Copied' : 'Copy'}
        </button>
      </div>

      <p class="mt-3 text-xs text-[var(--fg-subtle)]">Link expires in 72 hours.</p>

      {#if schoolLoginUrl}
        <p class="mt-4 rounded-xl bg-[var(--hover)]/50 px-3 py-2.5 text-xs text-[var(--fg-muted)]">
          Once they've set a password, tell them to bookmark
          <span class="font-mono font-medium text-[var(--fg)]">{schoolLoginUrl}</span>
          — their school's own sign-in page. No school code to remember, ever.
        </p>
      {/if}

      <div class="mt-5 flex justify-end">
        <button onclick={onDismiss}
          class="rounded-xl px-4 py-2 text-sm font-semibold text-white hover:opacity-90"
          style="background-color: var(--brand)">
          Done
        </button>
      </div>
    </div>
  </div>
{/if}
