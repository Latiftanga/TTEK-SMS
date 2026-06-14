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
    color = 'bg-gray-100 dark:bg-gray-800',
    iconColor = 'text-gray-500 dark:text-gray-400',
    trend, href, alert = false,
  }: Props = $props();
</script>

<svelte:element
  this={href ? 'a' : 'div'}
  {href}
  class="group relative overflow-hidden rounded-2xl border bg-[var(--card)] p-5 transition-all duration-200
         {alert ? 'border-amber-300 dark:border-amber-700/70' : 'border-[var(--border)]'}
         {href ? 'cursor-pointer hover:shadow-lg hover:shadow-black/5 dark:hover:shadow-black/20 hover:-translate-y-0.5 active:translate-y-0 active:scale-[0.99]' : ''}"
>
  {#if alert}
    <div class="absolute inset-x-0 top-0 h-0.5 rounded-t-2xl bg-gradient-to-r from-amber-400 to-orange-400"></div>
  {/if}

  <div class="flex items-start justify-between gap-3">
    <p class="text-[11px] font-semibold uppercase tracking-widest text-[var(--fg-muted)]">{label}</p>
    <div class="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl {color} transition-transform {href ? 'group-hover:scale-110' : ''}">
      <span class="{iconColor} text-sm leading-none">{icon}</span>
    </div>
  </div>

  <div class="mt-3">
    <p class="text-3xl font-bold tracking-tight {alert ? 'text-amber-500 dark:text-amber-400' : 'text-[var(--fg)]'}">{value}</p>
    {#if trend}
      <p class="mt-1 text-[11px] text-[var(--fg-muted)]">{trend}</p>
    {/if}
  </div>

  {#if href}
    <svg
      class="absolute bottom-4 right-4 h-4 w-4 text-gray-200 dark:text-gray-700 transition-all {href ? 'group-hover:text-gray-400 dark:group-hover:text-gray-500 group-hover:translate-x-0.5' : ''}"
      fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"
    >
      <polyline points="9 18 15 12 9 6"/>
    </svg>
  {/if}
</svelte:element>
