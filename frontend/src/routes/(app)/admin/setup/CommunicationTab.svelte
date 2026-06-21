<script lang="ts">
  import SmsTab   from './SmsTab.svelte';
  import EmailTab from './EmailTab.svelte';
</script>

<div class="space-y-10">

  <!-- ── SMS ─────────────────────────────────────────────────────────────────── -->
  <section>
    <div class="mb-5 flex items-center gap-3">
      <div class="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-[var(--hover)]">
        <svg class="h-5 w-5 text-[var(--fg-muted)]" fill="none" stroke="currentColor" stroke-width="1.75" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" d="M10.5 1.5H8.25A2.25 2.25 0 006 3.75v16.5a2.25 2.25 0 002.25 2.25h7.5A2.25 2.25 0 0018 20.25V3.75a2.25 2.25 0 00-2.25-2.25H13.5m-3 0V3h3V1.5m-3 0h3m-3 8.25h3"/>
        </svg>
      </div>
      <div>
        <h2 class="text-sm font-semibold text-[var(--fg)]">SMS</h2>
        <p class="text-xs text-[var(--fg-muted)]">Providers for parent notifications via text message</p>
      </div>
    </div>
    <SmsTab />
  </section>

  <div class="border-t border-[var(--border)]"></div>

  <!-- ── Email ────────────────────────────────────────────────────────────────── -->
  <section>
    <div class="mb-5 flex items-center gap-3">
      <div class="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-[var(--hover)]">
        <svg class="h-5 w-5 text-[var(--fg-muted)]" fill="none" stroke="currentColor" stroke-width="1.75" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" d="M21.75 6.75v10.5a2.25 2.25 0 01-2.25 2.25h-15a2.25 2.25 0 01-2.25-2.25V6.75m19.5 0A2.25 2.25 0 0019.5 4.5h-15a2.25 2.25 0 00-2.25 2.25m19.5 0v.243a2.25 2.25 0 01-1.07 1.916l-7.5 4.615a2.25 2.25 0 01-2.36 0L3.32 8.91a2.25 2.25 0 01-1.07-1.916V6.75"/>
        </svg>
      </div>
      <div>
        <h2 class="text-sm font-semibold text-[var(--fg)]">Email</h2>
        <p class="text-xs text-[var(--fg-muted)]">Providers for receipts, report card alerts, and other notifications</p>
      </div>
    </div>
    <EmailTab />
  </section>

</div>
