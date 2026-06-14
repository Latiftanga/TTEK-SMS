<script lang="ts">
  import { goto } from '$app/navigation';
  import { onMount } from 'svelte';
  import { auth, isAuthenticated } from '$lib/stores/auth';
  import { login, getMe } from '$lib/api/auth';
  import { get } from 'svelte/store';

  let email = $state('');
  let password = $state('');
  let error = $state('');
  let loading = $state(false);

  onMount(() => {
    if (get(isAuthenticated)) goto('/dashboard');
  });

  async function handleLogin() {
    if (!email.trim() || !password) { error = 'Enter your email and password'; return; }
    error = '';
    loading = true;
    try {
      const tokens = await login({
        login_type: 'EMAIL',
        identifier: email.trim(),
        password,
      });
      auth.setToken(tokens.access_token);
      const user = await getMe();
      auth.setAuth(user, tokens.access_token, tokens.refresh_token);
      goto(user.is_superadmin ? '/superadmin' : '/dashboard');
    } catch (e: any) {
      error = e?.response?.data?.detail ?? 'Login failed. Check your credentials.';
    } finally {
      loading = false;
    }
  }

  function handleKey(e: KeyboardEvent) {
    if (e.key === 'Enter') handleLogin();
  }
</script>

<svelte:head><title>TTEK-SMS — Platform Login</title></svelte:head>

<div class="min-h-screen flex flex-col items-center justify-center bg-[var(--bg)] p-4">
  <div class="w-full max-w-sm">

    <!-- Platform mark -->
    <div class="mb-8 text-center">
      <div class="mx-auto h-16 w-16 rounded-2xl bg-gray-900 dark:bg-gray-800 flex items-center
                  justify-center text-white text-2xl font-black tracking-tight mb-4 shadow-lg">
        T
      </div>
      <h1 class="text-xl font-bold text-[var(--fg)]">TTEK-SMS</h1>
      <p class="text-xs text-[var(--fg-muted)] mt-1">Platform Administration</p>
    </div>

    <div class="bg-[var(--card)] rounded-2xl shadow-sm border border-[var(--border)] p-6">
      <h2 class="text-base font-semibold text-[var(--fg)] mb-1">Platform sign in</h2>
      <p class="text-xs text-[var(--fg-muted)] mb-5">Superadmin access only.</p>

      <label class="block text-sm font-medium text-[var(--fg)] mb-1" for="email">Email</label>
      <input
        id="email"
        type="email"
        bind:value={email}
        onkeydown={handleKey}
        placeholder="admin@tagnatek.com"
        autocomplete="username"
        class="w-full rounded-xl border border-[var(--border)] bg-[var(--input-bg)]
               px-4 py-3 text-sm text-[var(--fg)] placeholder:text-[var(--fg-muted)]
               focus:outline-none focus:ring-2 focus:ring-brand/40 focus:border-brand transition"
      />

      <label class="block text-sm font-medium text-[var(--fg)] mt-3 mb-1" for="password">Password</label>
      <input
        id="password"
        type="password"
        bind:value={password}
        onkeydown={handleKey}
        placeholder="••••••••"
        autocomplete="current-password"
        class="w-full rounded-xl border border-[var(--border)] bg-[var(--input-bg)]
               px-4 py-3 text-sm text-[var(--fg)] placeholder:text-[var(--fg-muted)]
               focus:outline-none focus:ring-2 focus:ring-brand/40 focus:border-brand transition"
      />

      {#if error}
        <p class="mt-2 text-sm text-red-600 dark:text-red-400">{error}</p>
      {/if}

      <button
        onclick={handleLogin}
        disabled={loading}
        class="mt-5 w-full rounded-xl py-3 text-sm font-semibold text-white
               bg-gray-900 dark:bg-gray-700 hover:bg-gray-800 dark:hover:bg-gray-600
               transition active:scale-95 disabled:opacity-60"
      >
        {loading ? 'Signing in…' : 'Sign in'}
      </button>
    </div>

    <p class="mt-6 text-center text-xs text-[var(--fg-muted)]">
      School staff?
      <a href="/login" class="font-medium underline hover:text-[var(--fg)] transition">
        Sign in here →
      </a>
    </p>
  </div>
</div>
