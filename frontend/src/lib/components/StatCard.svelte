<script lang="ts">
  // Color is reserved for meaning (alert = amber, the brand accent on
  // hover), never for pure decoration — every icon box is the same neutral
  // tone regardless of which stat it is, so a page with 4+ cards doesn't
  // read as a rainbow of unrelated tints.
  interface Props {
    label: string;
    value: string | number;
    icon?: string;
    iconPath?: string;
    trend?: string;
    href?: string;
    alert?: boolean;
  }

  const { label, value, icon, iconPath, trend, href, alert = false }: Props = $props();
</script>

<svelte:element
  this={href ? 'a' : 'div'}
  {href}
  class="group relative flex flex-col justify-between overflow-hidden rounded-[1.25rem] p-5
         bg-[var(--card)] ring-1 ring-[var(--border)]
         {alert ? 'ring-amber-300/60 dark:ring-amber-600/40' : ''}
         {href ? 'cursor-pointer transition-shadow hover:shadow-md' : ''}
         "
  style="box-shadow: var(--shadow-sm);"
>
  <!-- Accent bar — solid, not a multi-hue gradient; amber when this stat needs attention, brand on hover otherwise -->
  {#if alert}
    <div class="absolute inset-x-0 top-0 h-[3px]" style="background-color: #f59e0b"></div>
  {:else if href}
    <div class="absolute inset-x-0 top-0 h-[3px] scale-x-0 origin-left
                transition-transform duration-300 ease-out group-hover:scale-x-100"
         style="background-color: var(--brand)"></div>
  {/if}

  <!-- Top: label + icon -->
  <div class="flex items-start justify-between gap-2">
    <p class="text-[0.6875rem] font-semibold uppercase tracking-[0.07em] text-[var(--fg-muted)] leading-none pt-0.5">
      {label}
    </p>
    <div class="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl
                {alert ? 'bg-amber-50 dark:bg-amber-950/40' : 'bg-[var(--hover)]'}
                transition-transform duration-200
                {href ? 'group-hover:scale-105' : ''}">
      {#if iconPath}
        <svg class="h-4.5 w-4.5 {alert ? 'text-amber-600 dark:text-amber-400' : 'text-[var(--fg-muted)]'}"
             fill="none" stroke="currentColor" stroke-width="1.75" viewBox="0 0 24 24" aria-hidden="true">
          {@html iconPath}
        </svg>
      {:else if icon}
        <span class="{alert ? 'text-amber-600 dark:text-amber-400' : 'text-[var(--fg-muted)]'} text-base leading-none select-none">{icon}</span>
      {/if}
    </div>
  </div>

  <!-- Value + trend -->
  <div class="mt-3.5">
    <p class="text-[1.75rem] font-bold leading-none tracking-tight
              {alert ? 'text-amber-500 dark:text-amber-400' : 'text-[var(--fg)]'}">
      {value}
    </p>
    {#if trend}
      <p class="mt-2 text-[0.6875rem] text-[var(--fg-muted)] leading-snug">{trend}</p>
    {/if}
  </div>

  <!-- Arrow on hover -->
  {#if href}
    <div class="absolute bottom-3.5 right-3.5 flex h-5 w-5 items-center justify-center rounded-lg
                opacity-0 transition-all duration-200 group-hover:opacity-100
                group-hover:translate-x-0.5 group-hover:-translate-y-0.5"
         style="background: var(--brand-dim); color: var(--brand)">
      <svg class="h-3 w-3" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" d="M7 17L17 7M17 7H7M17 7v10"/>
      </svg>
    </div>
  {/if}
</svelte:element>
