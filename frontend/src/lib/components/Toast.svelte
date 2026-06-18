<script lang="ts">
  import { fly } from 'svelte/transition';
  import { cubicOut } from 'svelte/easing';
  import { toast, type ToastKind } from '$lib/stores/toast';

  const KIND: Record<ToastKind, { bar: string; icon: string }> = {
    success: { bar: 'bg-emerald-500', icon: 'text-emerald-500' },
    error:   { bar: 'bg-red-500',     icon: 'text-red-500'     },
    warning: { bar: 'bg-amber-400',   icon: 'text-amber-500'   },
    info:    { bar: 'bg-[var(--brand)]', icon: 'text-[var(--brand)]' },
  };

  const ICONS: Record<ToastKind, string> = {
    success: `<path stroke-linecap="round" stroke-linejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>`,
    error:   `<path stroke-linecap="round" stroke-linejoin="round" d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z"/>`,
    warning: `<path stroke-linecap="round" stroke-linejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z"/>`,
    info:    `<path stroke-linecap="round" stroke-linejoin="round" d="M11.25 11.25l.041-.02a.75.75 0 011.063.852l-.708 2.836a.75.75 0 001.063.853l.041-.021M21 12a9 9 0 11-18 0 9 9 0 0118 0zm-9-3.75h.008v.008H12V8.25z"/>`,
  };
</script>

<!--
  Toasts stack bottom-right, newest on top.
  Shape: flat-left + rounded-right (like a file tab), achieved by
  rounded-r-xl + overflow-hidden on the outer shell.
  The colored accent bar is a child div that bleeds into the left edge.
-->
<div
  class="pointer-events-none fixed bottom-5 right-5 z-[200] flex flex-col-reverse gap-2"
  aria-live="polite"
>
  {#each $toast as t (t.id)}
    <div
      class="pointer-events-auto flex w-[320px] overflow-hidden rounded-r-xl
             bg-[var(--card)] shadow-xl ring-1 ring-[var(--border)]"
      transition:fly={{ x: 72, duration: 210, easing: cubicOut }}
      role="alert"
    >
      <!-- Accent bar — defines the left edge colour, square corners due to overflow-hidden -->
      <div class="w-1 shrink-0 {KIND[t.kind].bar}"></div>

      <!-- Icon -->
      <div class="flex shrink-0 items-center pl-3.5 pr-2.5">
        <svg class="h-[18px] w-[18px] {KIND[t.kind].icon}" fill="none"
             stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
          {@html ICONS[t.kind]}
        </svg>
      </div>

      <!-- Message -->
      <p class="flex-1 py-3.5 pr-2 text-sm font-medium leading-snug text-[var(--fg)]">
        {t.message}
      </p>

      <!-- Dismiss -->
      <button
        onclick={() => toast.dismiss(t.id)}
        aria-label="Dismiss notification"
        class="flex shrink-0 items-center px-3 text-[var(--fg-subtle)]
               transition hover:text-[var(--fg-muted)]"
      >
        <svg class="h-3.5 w-3.5" fill="none" stroke="currentColor"
             stroke-width="2.5" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12"/>
        </svg>
      </button>
    </div>
  {/each}
</div>
