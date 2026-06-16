<script lang="ts">
  interface Props {
    label: string;
    value: string | number;
    icon?: string;
    iconPath?: string;
    color?: string;
    iconColor?: string;
    trend?: string;
    href?: string;
    alert?: boolean;
  }

  const {
    label, value, icon,
    iconPath,
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
         {href ? 'cursor-pointer transition-shadow hover:shadow-md' : ''}
         "
  style="box-shadow: var(--shadow-sm);"
>
  <!-- Accent bar — animated on hover -->
  {#if alert}
    <div class="absolute inset-x-0 top-0 h-[3px] rounded-t-xl
                bg-gradient-to-r from-amber-400 via-orange-400 to-amber-500"></div>
  {:else if href}
    <div class="absolute inset-x-0 top-0 h-[3px] rounded-t-xl scale-x-0 origin-left
                bg-gradient-to-r from-[var(--brand)] to-[color-mix(in_oklab,var(--brand)_60%,#7c3aed)]
                transition-transform duration-300 ease-out group-hover:scale-x-100"></div>
  {/if}

  <!-- Top: label + icon -->
  <div class="flex items-start justify-between gap-2">
    <p class="text-[0.6875rem] font-semibold uppercase tracking-[0.07em] text-[var(--fg-muted)] leading-none pt-0.5">
      {label}
    </p>
    <div class="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl {color}
                transition-transform duration-200
                {href ? 'group-hover:scale-110 group-hover:-rotate-3' : ''}">
      {#if iconPath}
        <svg class="h-5 w-5 {iconColor}" fill="none" stroke="currentColor"
             stroke-width="1.75" viewBox="0 0 24 24" aria-hidden="true">
          {@html iconPath}
        </svg>
      {:else if icon}
        <span class="{iconColor} text-base leading-none select-none">{icon}</span>
      {/if}
    </div>
  </div>

  <!-- Value + trend -->
  <div class="mt-3">
    <p class="text-[1.625rem] font-bold leading-none tracking-tight
              {alert ? 'text-amber-500 dark:text-amber-400' : 'text-[var(--fg)]'}">
      {value}
    </p>
    {#if trend}
      <p class="mt-1.5 text-[0.6875rem] text-[var(--fg-muted)] leading-snug">{trend}</p>
    {/if}
  </div>

  <!-- Arrow on hover -->
  {#if href}
    <div class="absolute bottom-3 right-3 flex h-5 w-5 items-center justify-center rounded-lg
                opacity-0 transition-all duration-200 group-hover:opacity-100
                group-hover:translate-x-0.5 group-hover:-translate-y-0.5"
         style="background: var(--brand-dim); color: var(--brand)">
      <svg class="h-3 w-3" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" d="M7 17L17 7M17 7H7M17 7v10"/>
      </svg>
    </div>
  {/if}
</svelte:element>
