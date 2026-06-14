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
  class="group relative flex flex-col justify-between overflow-hidden rounded-xl p-4
         bg-[var(--card)] ring-1 ring-[var(--border)]
         {alert ? 'ring-amber-300/60 dark:ring-amber-600/40' : ''}
         {href ? 'cursor-pointer' : ''}
         "
  style="box-shadow: var(--shadow-sm);"
>
  <!-- Accent bar -->
  {#if alert}
    <div class="absolute inset-x-0 top-0 h-[2px] rounded-t-xl bg-gradient-to-r from-amber-400 via-orange-400 to-amber-500"></div>
  {:else if href}
    <div class="absolute inset-x-0 top-0 h-[2px] rounded-t-xl scale-x-0 origin-left bg-gradient-to-r
                from-[var(--brand)] to-[color-mix(in_oklab,var(--brand)_60%,#7c3aed)]
                transition-transform duration-300 ease-out group-hover:scale-x-100"></div>
  {/if}

  <!-- Top row: label + icon -->
  <div class="flex items-start justify-between gap-2">
    <p class="text-[10px] font-semibold uppercase tracking-[0.08em] text-[var(--fg-muted)] leading-none pt-0.5">
      {label}
    </p>
    <div class="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg {color}
                transition-transform duration-200 {href ? 'group-hover:scale-110 group-hover:rotate-[-4deg]' : ''}">
      <span class="{iconColor} text-xs leading-none select-none">{icon}</span>
    </div>
  </div>

  <!-- Value -->
  <div class="mt-2.5">
    <p class="text-2xl font-bold leading-none tracking-tight
              {alert ? 'text-amber-500 dark:text-amber-400' : 'text-[var(--fg)]'}">
      {value}
    </p>
    {#if trend}
      <p class="mt-1 text-[11px] text-[var(--fg-muted)] leading-snug">{trend}</p>
    {/if}
  </div>

  <!-- Arrow on hover -->
  {#if href}
    <div class="absolute bottom-3 right-3 flex h-5 w-5 items-center justify-center rounded-md
                opacity-0 transition-all duration-200 group-hover:opacity-100 group-hover:translate-x-0.5
                group-hover:-translate-y-0.5"
         style="background: var(--brand-dim); color: var(--brand)">
      <svg class="h-3 w-3" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" d="M7 17L17 7M17 7H7M17 7v10"/>
      </svg>
    </div>
  {/if}
</svelte:element>
