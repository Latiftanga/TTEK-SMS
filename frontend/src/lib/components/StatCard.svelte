<script lang="ts">
  interface Props {
    label: string;
    value: string | number;
    icon: string;          // emoji or short text icon
    color?: string;        // Tailwind bg class for icon badge, e.g. 'bg-blue-100'
    iconColor?: string;    // Tailwind text class, e.g. 'text-blue-600'
    trend?: string;        // e.g. '+3 today', 'vs last term'
    href?: string;         // if set, card is clickable
    alert?: boolean;       // highlight card in amber when true
  }

  const { label, value, icon, color = 'bg-gray-100', iconColor = 'text-gray-600', trend, href, alert = false }: Props = $props();
</script>

<svelte:element
  this={href ? 'a' : 'div'}
  {href}
  class="flex flex-col gap-3 rounded-2xl bg-white border p-5 transition hover:shadow-md
         {alert ? 'border-amber-200 bg-amber-50' : 'border-gray-100'}
         {href ? 'cursor-pointer active:scale-[0.98]' : ''}"
>
  <div class="flex items-center justify-between">
    <span class="text-sm font-medium text-gray-500">{label}</span>
    <span class="flex h-9 w-9 items-center justify-center rounded-xl text-lg {color} {iconColor}">
      {icon}
    </span>
  </div>
  <div>
    <span class="text-3xl font-bold {alert ? 'text-amber-700' : 'text-gray-900'}">{value}</span>
    {#if trend}
      <p class="mt-0.5 text-xs text-gray-400">{trend}</p>
    {/if}
  </div>
</svelte:element>
