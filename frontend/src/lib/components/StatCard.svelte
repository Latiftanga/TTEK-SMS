<script lang="ts">
  interface Props {
    label: string;
    value: string | number;
    icon: string;
    color?: string;
    iconColor?: string;
    trend?: string;
    href?: string;
    alert?: boolean;
  }

  const {
    label, value, icon,
    color = 'bg-zinc-100 dark:bg-zinc-800',
    iconColor = 'text-zinc-500',
    trend, href, alert = false,
  }: Props = $props();
</script>

<svelte:element
  this={href ? 'a' : 'div'}
  {href}
  class="group relative flex flex-col justify-between overflow-hidden rounded-2xl p-5
         bg-[var(--card)] ring-1 ring-[var(--border)]
         {alert ? 'ring-amber-300/60 dark:ring-amber-600/40' : ''}
         {href ? 'cursor-pointer' : ''}
         "
  style="box-shadow: var(--shadow-sm);"
>
  <!-- Alert accent bar -->
  {#if alert}
    <div class="absolute inset-x-0 top-0 h-[3px] rounded-t-2xl bg-gradient-to-r from-amber-400 via-orange-400 to-amber-500"></div>
  {:else if href}
    <div class="absolute inset-x-0 top-0 h-[3px] rounded-t-2xl scale-x-0 origin-left bg-gradient-to-r
                from-[var(--brand)] to-[color-mix(in_oklab,var(--brand)_60%,#7c3aed)]
                transition-transform duration-300 ease-out group-hover:scale-x-100"></div>
  {/if}

  <!-- Top row: label + icon -->
  <div class="flex items-start justify-between gap-2">
    <p class="text-[11px] font-semibold uppercase tracking-[0.08em] text-[var(--fg-muted)] leading-none pt-0.5">
      {label}
    </p>
    <div class="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl {color}
                transition-transform duration-200 {href ? 'group-hover:scale-110 group-hover:rotate-[-4deg]' : ''}">
      <span class="{iconColor} text-sm leading-none select-none">{icon}</span>
    </div>
  </div>

  <!-- Value -->
  <div class="mt-3">
    <p class="text-[2rem] font-bold leading-none tracking-tight
              {alert ? 'text-amber-500 dark:text-amber-400' : 'text-[var(--fg)]'}
              transition-none">
      {value}
    </p>
    {#if trend}
      <p class="mt-1.5 text-xs text-[var(--fg-muted)] leading-snug">{trend}</p>
    {/if}
  </div>

  <!-- Arrow on hover (linked cards only) -->
  {#if href}
    <div class="absolute bottom-4 right-4 flex h-6 w-6 items-center justify-center rounded-lg
                opacity-0 transition-all duration-200 group-hover:opacity-100 group-hover:translate-x-0.5
                group-hover:-translate-y-0.5"
         style="background: var(--brand-dim); color: var(--brand)">
      <svg class="h-3.5 w-3.5" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" d="M7 17L17 7M17 7H7M17 7v10"/>
      </svg>
    </div>
  {/if}
</svelte:element>
