<script lang="ts">
  import type { SchoolBranding } from '$lib/api/schools';

  interface Props {
    isSubdomain: boolean;
    schoolCode: string;
    identifier: string;
    password: string;
    showPassword: boolean;
    rememberMe: boolean;
    branding: SchoolBranding | null;
    brandingState: 'idle' | 'loading' | 'found' | 'not-found';
    formError: string;
    loadingLogin: boolean;
    onSchoolCodeBlur: () => void;
    onKeydown: (e: KeyboardEvent) => void;
    onSubmit: () => void;
  }

  let {
    isSubdomain,
    schoolCode = $bindable(),
    identifier = $bindable(),
    password = $bindable(),
    showPassword = $bindable(),
    rememberMe = $bindable(),
    branding,
    brandingState,
    formError,
    loadingLogin,
    onSchoolCodeBlur,
    onKeydown,
    onSubmit,
  }: Props = $props();
</script>

<!-- School identity header -->
<div class="mb-8 text-center">
  {#if branding?.logo_url}
    <img src={branding.logo_url} alt={branding.school_name}
         class="mx-auto h-16 w-auto object-contain mb-4" />
  {:else}
    <div class="mx-auto h-16 w-16 rounded-2xl flex items-center justify-center
                text-white text-2xl font-bold mb-4 shadow-lg"
         style="background: linear-gradient(135deg, var(--brand) 0%, color-mix(in oklab, var(--brand) 65%, #7c3aed) 100%)">
      {branding ? (branding.short_name ?? branding.school_name).slice(0, 2).toUpperCase() : 'S'}
    </div>
  {/if}
  <h1 class="text-xl font-bold tracking-tight text-[var(--fg)]">
    {branding?.school_name ?? 'Welcome back'}
  </h1>
  {#if branding?.motto}
    <p class="text-xs text-[var(--fg-muted)] mt-1 italic">{branding.motto}</p>
  {:else if !branding}
    <p class="text-sm text-[var(--fg-muted)] mt-1">Sign in to your school portal</p>
  {/if}
</div>

<!-- Card -->
<div class="rounded-2xl border border-[var(--border)] bg-[var(--card)] p-6 space-y-4"
     style="box-shadow: var(--shadow-lg), 0 0 0 1px var(--border);">

  {#if !isSubdomain}
    <div>
      <label class="block text-[0.8125rem] font-semibold text-[var(--fg)] mb-1.5" for="school-code">
        School code
      </label>
      <div class="relative">
        <input
          id="school-code"
          type="text"
          bind:value={schoolCode}
          onblur={onSchoolCodeBlur}
          onkeydown={onKeydown}
          placeholder="e.g. presec"
          autocomplete="off"
          spellcheck={false}
          class="w-full rounded-xl border border-[var(--border-strong)] bg-[var(--input-bg)]
                 px-4 py-3 pr-10 text-sm text-[var(--fg)] placeholder:text-[var(--fg-subtle)]
                 focus:outline-none focus:ring-2 focus:ring-[var(--brand)]/20
                 focus:border-[var(--brand)] transition lowercase"
        />
        <span class="absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none">
          {#if brandingState === 'loading'}
            <svg class="h-4 w-4 animate-spin text-[var(--fg-muted)]" fill="none" viewBox="0 0 24 24">
              <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/>
              <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z"/>
            </svg>
          {:else if brandingState === 'found'}
            <svg class="h-4 w-4 text-emerald-500" fill="none" viewBox="0 0 24 24"
                 stroke="currentColor" stroke-width="2.5">
              <path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7"/>
            </svg>
          {:else if brandingState === 'not-found'}
            <svg class="h-4 w-4 text-red-400" fill="none" viewBox="0 0 24 24"
                 stroke="currentColor" stroke-width="2.5">
              <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12"/>
            </svg>
          {/if}
        </span>
      </div>
      {#if brandingState === 'not-found'}
        <p class="mt-1.5 text-xs text-red-500">School not found — check the code and try again.</p>
      {/if}
    </div>
  {/if}

  <div>
    <label class="block text-[0.8125rem] font-semibold text-[var(--fg)] mb-1.5" for="identifier">
      Email / Phone / Student ID
    </label>
    <input
      id="identifier"
      type="text"
      bind:value={identifier}
      onkeydown={onKeydown}
      placeholder="you@example.com or 0244…"
      autocomplete="username"
      class="w-full rounded-xl border border-[var(--border-strong)] bg-[var(--input-bg)]
             px-4 py-3 text-sm text-[var(--fg)] placeholder:text-[var(--fg-subtle)]
             focus:outline-none focus:ring-2 focus:ring-[var(--brand)]/20
             focus:border-[var(--brand)] transition"
    />
  </div>

  <div>
    <label class="block text-[0.8125rem] font-semibold text-[var(--fg)] mb-1.5" for="password">
      Password
    </label>
    <div class="relative">
      <input
        id="password"
        type={showPassword ? 'text' : 'password'}
        bind:value={password}
        onkeydown={onKeydown}
        placeholder="••••••••"
        autocomplete="current-password"
        class="w-full rounded-xl border border-[var(--border-strong)] bg-[var(--input-bg)]
               px-4 py-3 pr-10 text-sm text-[var(--fg)] placeholder:text-[var(--fg-subtle)]
               focus:outline-none focus:ring-2 focus:ring-[var(--brand)]/20
               focus:border-[var(--brand)] transition"
      />
      <button
        type="button"
        onclick={() => showPassword = !showPassword}
        class="absolute right-3 top-1/2 -translate-y-1/2 text-[var(--fg-subtle)]
               hover:text-[var(--fg-muted)] transition"
        aria-label={showPassword ? 'Hide password' : 'Show password'}
      >
        {#if showPassword}
          <svg class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round"
              d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7
                 a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878
                 l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l3.59
                 3.59m0 0A9.953 9.953 0 0112 5c4.478 0 8.268 2.943 9.543 7a10.025
                 10.025 0 01-4.132 5.411m0 0L21 21"/>
          </svg>
        {:else}
          <svg class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"/>
            <path stroke-linecap="round" stroke-linejoin="round"
              d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943
                 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"/>
          </svg>
        {/if}
      </button>
    </div>
  </div>

  <!-- Remember me -->
  <label class="flex items-center gap-2.5 cursor-pointer select-none">
    <div class="relative">
      <input type="checkbox" bind:checked={rememberMe} class="sr-only peer" />
      <div class="h-4.5 w-4.5 rounded-[5px] border border-[var(--border-strong)]
                  bg-[var(--input-bg)] transition peer-checked:border-transparent
                  peer-focus-visible:ring-2 peer-focus-visible:ring-[var(--brand)]/30"
           style="background: {rememberMe ? 'var(--brand)' : ''}">
        {#if rememberMe}
          <svg class="absolute inset-0 m-auto h-3 w-3 text-white" fill="none" viewBox="0 0 24 24"
               stroke="currentColor" stroke-width="3.5">
            <path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7"/>
          </svg>
        {/if}
      </div>
    </div>
    <span class="text-sm text-[var(--fg-muted)]">Keep me signed in for 30 days</span>
  </label>

  {#if formError}
    <div class="rounded-xl border border-red-100 dark:border-red-900 bg-red-50 dark:bg-red-950/40
                px-4 py-3 text-sm text-red-600 dark:text-red-400">
      {formError}
    </div>
  {/if}

  <button
    onclick={onSubmit}
    disabled={loadingLogin}
    class="relative w-full overflow-hidden rounded-xl py-3 text-sm font-semibold text-white
           transition active:scale-[0.98] disabled:opacity-60"
    style="background: linear-gradient(135deg, var(--brand) 0%, color-mix(in oklab, var(--brand) 70%, #7c3aed) 100%);
           box-shadow: 0 2px 12px rgba(var(--brand-rgb), 0.35);"
  >
    {#if loadingLogin}
      <span class="flex items-center justify-center gap-2">
        <svg class="h-4 w-4 animate-spin" fill="none" viewBox="0 0 24 24">
          <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/>
          <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z"/>
        </svg>
        Signing in…
      </span>
    {:else}
      Sign in
    {/if}
  </button>

  <p class="text-center text-xs text-[var(--fg-subtle)]">
    <a href="/forgot-password" class="text-[var(--fg-muted)] transition hover:text-[var(--fg)] hover:underline">
      Forgot your password?
    </a>
  </p>

</div>
