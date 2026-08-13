<script lang="ts">
  import { createQuery, createMutation, useQueryClient } from '@tanstack/svelte-query';
  import { getPlatformDomain } from '$lib/platformDomain';
  import { getMySchool, updateMySchool, uploadMyLogo, applyBranding, type SchoolUpdatePayload, type SchoolRead } from '$lib/api/schools';
  import { school as schoolStore } from '$lib/stores/school';

  const qc = useQueryClient();
  const platformDomain = getPlatformDomain();

  const schoolQ = createQuery({ queryKey: ['my-school'], queryFn: getMySchool, staleTime: 60_000 });

  let profileForm = $state<SchoolUpdatePayload & { name: string }>({
    name: '', short_name: '', phone: '', email: '',
    address: '', motto: '', established_year: undefined, brand_color: '#1e40af', subdomain: '',
  });
  let profileDirty = $state(false);
  let profileError = $state('');
  let profileOk    = $state(false);

  $effect(() => {
    const s = $schoolQ.data;
    if (s && !profileDirty) {
      profileForm = {
        name:             s.name,
        short_name:       s.short_name ?? '',
        phone:            s.phone ?? '',
        email:            s.email ?? '',
        address:          s.address ?? '',
        motto:            s.motto ?? '',
        established_year: s.established_year ?? undefined,
        brand_color:      s.brand_color,
        subdomain:        s.subdomain ?? '',
      };
    }
  });

  const profileMut = createMutation({
    mutationFn: () => updateMySchool({
      ...profileForm,
      short_name:       profileForm.short_name       || undefined,
      phone:            profileForm.phone            || undefined,
      email:            profileForm.email            || undefined,
      address:          profileForm.address          || undefined,
      motto:            profileForm.motto            || undefined,
      established_year: profileForm.established_year || undefined,
      // Blank never clears it — every school keeps a subdomain once it has
      // one (auto-assigned at creation), same "don't send empty" pattern
      // as every other optional field above.
      subdomain:        profileForm.subdomain         || undefined,
    }),
    onSuccess: (updated: SchoolRead) => {
      qc.invalidateQueries({ queryKey: ['my-school'] });
      qc.invalidateQueries({ queryKey: ['my-branding'] });
      // Immediately propagate brand colour change to CSS vars and the school store.
      applyBranding({
        school_name:  updated.name,
        short_name:   updated.short_name,
        school_type:  updated.school_type,
        motto:        updated.motto,
        logo_url:     updated.logo_url,
        brand_color:  updated.brand_color,
        school_code:  updated.school_code,
      });
      schoolStore.set({
        name:        updated.name,
        shortName:   updated.short_name ?? updated.name,
        subdomain:   updated.subdomain ?? '',
        schoolCode:  updated.school_code,
        schoolType:  updated.school_type,
        brandColor:  updated.brand_color,
        logoUrl:     updated.logo_url,
        motto:       updated.motto,
      });
      profileDirty = false; profileOk = true;
      setTimeout(() => profileOk = false, 3000);
    },
    onError: (e: unknown) => {
      profileError = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? 'Failed to save.';
    },
  });

  // ── Logo upload ────────────────────────────────────────────────────────────────
  let logoInput: HTMLInputElement;
  let logoUploading = $state(false);
  let logoError     = $state('');

  async function handleLogoChange(e: Event) {
    const file = (e.target as HTMLInputElement).files?.[0];
    if (!file) return;
    logoUploading = true; logoError = '';
    try {
      const updated = await uploadMyLogo(file);
      qc.invalidateQueries({ queryKey: ['my-school'] });
      qc.invalidateQueries({ queryKey: ['my-branding'] });
      applyBranding({
        school_name:  updated.name,
        short_name:   updated.short_name,
        school_type:  updated.school_type,
        motto:        updated.motto,
        logo_url:     updated.logo_url,
        brand_color:  updated.brand_color,
        school_code:  updated.school_code,
      });
      schoolStore.set({
        name:       updated.name,
        shortName:  updated.short_name ?? updated.name,
        subdomain:  updated.subdomain ?? '',
        schoolCode: updated.school_code,
        schoolType: updated.school_type,
        brandColor: updated.brand_color,
        logoUrl:    updated.logo_url,
        motto:      updated.motto,
      });
    } catch (err: unknown) {
      logoError = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
        ?? 'Upload failed. Try again in a moment.';
    } finally {
      logoUploading = false;
    }
  }
</script>

{#if $schoolQ.isPending}
  <div class="space-y-4">{#each [1,2,3] as _}<div class="h-12 animate-pulse rounded-xl bg-[var(--card)]"></div>{/each}</div>
{:else}
  <div class="grid gap-6 lg:grid-cols-[1fr_280px]">
    <div class="space-y-5">

      <div class="rounded-xl border border-[var(--border)] bg-[var(--card)] p-5">
        <h2 class="mb-4 text-sm font-semibold text-[var(--fg)]">Identity</h2>
        <div class="grid gap-4 sm:grid-cols-2">
          <div>
            <label class="mb-1 block text-xs font-medium text-[var(--fg-muted)]">School Name <span class="text-red-500">*</span></label>
            <input bind:value={profileForm.name} oninput={() => profileDirty = true}
              class="w-full rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--fg)] focus:border-[var(--brand)] focus:outline-none" />
          </div>
          <div>
            <label class="mb-1 block text-xs font-medium text-[var(--fg-muted)]">Short Name</label>
            <input bind:value={profileForm.short_name} oninput={() => profileDirty = true} placeholder="e.g. PRESEC"
              class="w-full rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--fg)] placeholder:text-[var(--fg-muted)] focus:border-[var(--brand)] focus:outline-none" />
          </div>
          <div class="sm:col-span-2">
            <label class="mb-1 block text-xs font-medium text-[var(--fg-muted)]">Motto</label>
            <input bind:value={profileForm.motto} oninput={() => profileDirty = true} placeholder="e.g. Excellence in Service"
              class="w-full rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--fg)] placeholder:text-[var(--fg-muted)] focus:border-[var(--brand)] focus:outline-none" />
          </div>
          <div>
            <label class="mb-1 block text-xs font-medium text-[var(--fg-muted)]">Established Year</label>
            <input bind:value={profileForm.established_year} type="number" min="1800" max="2100" oninput={() => profileDirty = true} placeholder="e.g. 1968"
              class="w-full rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--fg)] placeholder:text-[var(--fg-muted)] focus:border-[var(--brand)] focus:outline-none" />
          </div>
          <div>
            <label class="mb-1 block text-xs font-medium text-[var(--fg-muted)]">Brand Colour</label>
            <div class="flex items-center gap-2">
              <input type="color" bind:value={profileForm.brand_color} oninput={() => profileDirty = true}
                class="h-9 w-12 cursor-pointer rounded-lg border border-[var(--border)] bg-[var(--bg)] p-1" />
              <input bind:value={profileForm.brand_color} oninput={() => profileDirty = true} placeholder="#1e40af"
                class="min-w-0 flex-1 rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 font-mono text-sm text-[var(--fg)] focus:border-[var(--brand)] focus:outline-none" />
            </div>
          </div>
        </div>
      </div>

      <div class="rounded-xl border border-[var(--border)] bg-[var(--card)] p-5">
        <h2 class="mb-1 text-sm font-semibold text-[var(--fg)]">Sign-in page</h2>
        <p class="mb-4 text-xs text-[var(--fg-muted)]">
          Staff and students use this link to reach your own branded sign-in page — no school code to remember.
          Every school gets one automatically; change it here if you'd prefer a different address.
        </p>
        <div class="flex items-center overflow-hidden rounded-xl border border-[var(--border)] bg-[var(--bg)] focus-within:border-[var(--brand)]">
          <span class="shrink-0 pl-3 text-sm text-[var(--fg-muted)]">https://</span>
          <input bind:value={profileForm.subdomain} oninput={() => profileDirty = true}
            placeholder="yourschool" autocomplete="off" spellcheck={false}
            class="min-w-0 flex-1 bg-transparent px-1 py-2 text-sm text-[var(--fg)] placeholder:text-[var(--fg-muted)] focus:outline-none lowercase" />
          {#if platformDomain}
            <span class="shrink-0 pr-3 text-sm text-[var(--fg-muted)]">.{platformDomain}</span>
          {/if}
        </div>
        {#if !platformDomain}
          <p class="mt-2 text-xs text-[var(--fg-subtle)]">
            Platform domain not configured yet — this link will preview once it's set.
          </p>
        {/if}
      </div>

      <div class="rounded-xl border border-[var(--border)] bg-[var(--card)] p-5">
        <h2 class="mb-4 text-sm font-semibold text-[var(--fg)]">Contact</h2>
        <div class="grid gap-4 sm:grid-cols-2">
          <div>
            <label class="mb-1 block text-xs font-medium text-[var(--fg-muted)]">Phone</label>
            <input bind:value={profileForm.phone} oninput={() => profileDirty = true} placeholder="e.g. 0302000000"
              class="w-full rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--fg)] placeholder:text-[var(--fg-muted)] focus:border-[var(--brand)] focus:outline-none" />
          </div>
          <div>
            <label class="mb-1 block text-xs font-medium text-[var(--fg-muted)]">Email</label>
            <input bind:value={profileForm.email} type="email" oninput={() => profileDirty = true} placeholder="e.g. admin@school.edu.gh"
              class="w-full rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--fg)] placeholder:text-[var(--fg-muted)] focus:border-[var(--brand)] focus:outline-none" />
          </div>
          <div class="sm:col-span-2">
            <label class="mb-1 block text-xs font-medium text-[var(--fg-muted)]">Address</label>
            <textarea bind:value={profileForm.address} rows="2" oninput={() => profileDirty = true} placeholder="Physical address"
              class="w-full resize-none rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--fg)] placeholder:text-[var(--fg-muted)] focus:border-[var(--brand)] focus:outline-none"></textarea>
          </div>
        </div>
      </div>

      {#if profileError}<p class="text-sm text-red-500">{profileError}</p>{/if}
      {#if profileOk}
        <p class="flex items-center gap-1.5 text-sm text-green-600">
          <svg class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>
          Changes saved.
        </p>
      {/if}
      <button onclick={() => $profileMut.mutate()} disabled={$profileMut.isPending || !profileDirty} class="btn-primary">
        {$profileMut.isPending ? 'Saving…' : 'Save changes'}
      </button>
    </div>

    <!-- Logo panel -->
    <div class="rounded-xl border border-[var(--border)] bg-[var(--card)] p-5">
      <h2 class="mb-4 text-sm font-semibold text-[var(--fg)]">School Logo</h2>
      <div class="mb-4 flex justify-center">
        {#if $schoolQ.data?.logo_url}
          <img src={$schoolQ.data.logo_url} alt="School logo"
            class="h-28 w-28 rounded-xl object-contain ring-1 ring-[var(--border)]" />
        {:else}
          <div class="flex h-28 w-28 items-center justify-center rounded-xl text-3xl font-bold text-white"
               style="background: linear-gradient(135deg, var(--brand) 0%, color-mix(in oklab, var(--brand) 60%, #7c3aed) 100%)">
            {($schoolQ.data?.short_name ?? $schoolQ.data?.name ?? 'S').slice(0, 2).toUpperCase()}
          </div>
        {/if}
      </div>
      <input bind:this={logoInput} type="file" accept="image/jpeg,image/png,image/webp" class="hidden" onchange={handleLogoChange} />
      <button onclick={() => logoInput.click()} disabled={logoUploading}
        class="btn-ghost w-full justify-center">
        {#if logoUploading}
          <svg class="h-4 w-4 animate-spin" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/></svg>
          Uploading…
        {:else}
          <svg class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="1.75" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5"/></svg>
          Upload logo
        {/if}
      </button>
      {#if logoError}<p class="mt-2 text-xs text-red-500">{logoError}</p>{/if}
      <p class="mt-2 text-center text-[10px] text-[var(--fg-muted)]">JPEG, PNG or WebP · max 2 MB</p>
    </div>
  </div>
{/if}
