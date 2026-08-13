<script lang="ts">
  import { createMutation, createQuery, useQueryClient } from '@tanstack/svelte-query';
  import { reactiveQuery } from '$lib/query.svelte';
  import { createSchool, updateSchool, listRegions, listDistricts, type SchoolRead, type DistrictRead } from '$lib/api/schools';
  import { toast } from '$lib/stores/toast';
  import { portal } from '$lib/actions/portal';
  import { apiError } from '$lib/utils';
  import ConfirmModal from '$lib/components/ConfirmModal.svelte';

  interface Props {
    open: boolean;
    school?: SchoolRead | null;   // present => edit mode, absent => create mode
    onSuccess: (school: SchoolRead) => void;
    onCancel: () => void;
  }
  const { open, school = null, onSuccess, onCancel }: Props = $props();
  const isEdit = $derived(!!school);

  const qc = useQueryClient();

  const regionsQuery = createQuery({ queryKey: ['regions'], queryFn: listRegions, staleTime: 60 * 60_000 });

  function emptyForm() {
    return {
      name: '', short_name: '', school_code: '',
      school_type: '' as '' | 'BASIC' | 'SHS',
      region_id: '', district_id: '',
      phone: '', email: '', address: '', motto: '',
      established_year: '', subdomain: '', custom_domain: '',
      has_boarding: false, is_active: true,
    };
  }
  function formFromSchool(s: SchoolRead) {
    return {
      name: s.name, short_name: s.short_name ?? '', school_code: s.school_code,
      school_type: s.school_type as '' | 'BASIC' | 'SHS',
      region_id: s.region_id, district_id: s.district_id,
      phone: s.phone ?? '', email: s.email ?? '', address: s.address ?? '', motto: s.motto ?? '',
      established_year: s.established_year != null ? String(s.established_year) : '',
      subdomain: s.subdomain ?? '', custom_domain: s.custom_domain ?? '',
      has_boarding: s.has_boarding, is_active: s.is_active,
    };
  }

  let form = $state(emptyForm());
  let original = emptyForm();
  let formError = $state('');

  // A district only makes sense for the region it belongs to — tracks the
  // region a fresh region×district pair was last seeded/confirmed for, so
  // the effect below can tell "user picked a different region" (clear the
  // district) apart from "form was just seeded with a region+district that
  // already came paired together" (leave it alone).
  let lastRegionId = $state('');

  // Re-seed the form whenever the drawer opens — fresh blank for "create",
  // a snapshot of the target school for "edit" (also used as the unsaved-
  // changes baseline below).
  $effect(() => {
    if (open) {
      const seed = school ? formFromSchool(school) : emptyForm();
      form = { ...seed };
      original = seed;
      lastRegionId = seed.region_id;
      formError = '';
    }
  });

  const districtsQuery = reactiveQuery<DistrictRead[]>(() => ({
    queryKey: ['districts', form.region_id],
    queryFn: () => listDistricts(form.region_id),
    enabled: !!form.region_id,
    staleTime: 60 * 60_000,
  }));

  $effect(() => {
    if (form.region_id !== lastRegionId) {
      lastRegionId = form.region_id;
      form.district_id = '';
    }
  });

  const hasUnsaved = $derived(
    isEdit
      ? JSON.stringify(form) !== JSON.stringify(original)
      : Object.entries(form).some(([k, v]) => k !== 'has_boarding' && k !== 'is_active' && v !== ''),
  );
  let confirmDiscard = $state(false);

  function requestClose() {
    if (hasUnsaved) confirmDiscard = true;
    else onCancel();
  }

  const createMut = createMutation({
    mutationFn: createSchool,
    onSuccess: (data: SchoolRead) => {
      qc.invalidateQueries({ queryKey: ['schools'] });
      formError = '';
      toast.success('School created.');
      onSuccess(data);
    },
    onError: (e) => {
      formError = apiError(e, 'Failed to create school.');
      toast.error(formError);
    },
  });

  const updateMut = createMutation({
    mutationFn: (payload: Parameters<typeof updateSchool>[1]) => updateSchool(school!.id, payload),
    onSuccess: (data: SchoolRead) => {
      qc.invalidateQueries({ queryKey: ['schools'] });
      formError = '';
      toast.success('School updated.');
      onSuccess(data);
    },
    onError: (e) => {
      formError = apiError(e, 'Failed to update school.');
      toast.error(formError);
    },
  });

  const isPending = $derived($createMut.isPending || $updateMut.isPending);

  function submit() {
    formError = '';
    if (!form.name || !form.school_code || !form.school_type || !form.region_id || !form.district_id) {
      formError = 'Name, school code, type, region, and district are required.';
      return;
    }
    if (isEdit) {
      $updateMut.mutate({
        name: form.name,
        short_name: form.short_name || undefined,
        phone: form.phone || undefined,
        email: form.email || undefined,
        address: form.address || undefined,
        motto: form.motto || undefined,
        established_year: form.established_year ? parseInt(form.established_year) : undefined,
        subdomain: form.subdomain || undefined,
        custom_domain: form.custom_domain || undefined,
        has_boarding: form.has_boarding,
        is_active: form.is_active,
      });
    } else {
      $createMut.mutate({
        name: form.name,
        short_name: form.short_name || undefined,
        school_code: form.school_code,
        school_type: form.school_type,
        region_id: form.region_id,
        district_id: form.district_id,
        phone: form.phone || undefined,
        email: form.email || undefined,
        address: form.address || undefined,
        motto: form.motto || undefined,
        established_year: form.established_year ? parseInt(form.established_year) : undefined,
        subdomain: form.subdomain || undefined,
        has_boarding: form.has_boarding,
      });
    }
  }

  const inp = 'w-full min-h-[44px] rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--fg)] placeholder:text-[var(--fg-muted)] focus:border-[var(--brand)] focus:outline-none disabled:opacity-50';
  const lbl = 'mb-1 block text-xs font-medium text-[var(--fg-muted)]';
</script>

{#if open}
  <div use:portal class="contents">
  <div class="fixed inset-0 z-40 bg-black/40 backdrop-blur-sm" onclick={requestClose} role="none"></div>

  <div class="fixed inset-y-0 right-0 z-50 flex w-full max-w-[440px] flex-col
              border-l border-[var(--border)] bg-[var(--card)]"
       style="box-shadow: -8px 0 40px rgba(0,0,0,0.14);">

    <!-- Drawer header -->
    <div class="flex shrink-0 items-center justify-between border-b border-[var(--border)] px-6 py-4">
      <div>
        <h2 class="text-sm font-semibold text-[var(--fg)]">{isEdit ? school?.name : 'Onboard a school'}</h2>
        <p class="mt-0.5 text-xs text-[var(--fg-muted)]">
          {isEdit ? 'Update this school\'s details.' : "They'll get their own branded sign-in link once created."}
        </p>
      </div>
      <button onclick={requestClose} aria-label="Close"
        class="flex min-h-[44px] min-w-[44px] items-center justify-center rounded-lg text-[var(--fg-muted)]
               transition hover:bg-[var(--hover)] hover:text-[var(--fg)]">
        <svg class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12"/>
        </svg>
      </button>
    </div>

    <!-- Scrollable body -->
    <div class="flex-1 space-y-6 overflow-y-auto px-6 py-5">

      <!-- Identity -->
      <div>
        <p class="mb-3 text-[11px] font-semibold uppercase tracking-widest text-[var(--fg-muted)]">Identity</p>
        <div class="space-y-3">
          <div>
            <label class={lbl} for="sf-name">School name *</label>
            <input id="sf-name" bind:value={form.name} placeholder="e.g. Achimota School"
              class={inp} />
          </div>
          <div class="grid grid-cols-2 gap-3">
            <div>
              <label class={lbl} for="sf-short">Short name</label>
              <input id="sf-short" bind:value={form.short_name} placeholder="e.g. Achimota"
                class={inp} />
            </div>
            <div>
              <label class={lbl} for="sf-code">School code {isEdit ? '' : '*'}</label>
              <input id="sf-code" bind:value={form.school_code} placeholder="e.g. ACHIMOTA"
                disabled={isEdit} title={isEdit ? "School code can't be changed after creation" : undefined}
                class="{inp} uppercase" />
            </div>
          </div>
          <div>
            <label class={lbl} for="sf-type">School type {isEdit ? '' : '*'}</label>
            <select id="sf-type" bind:value={form.school_type} disabled={isEdit}
              title={isEdit ? "School type can't be changed after creation" : undefined} class={inp}>
              <option value="">Select…</option>
              <option value="BASIC">Basic</option>
              <option value="SHS">Senior High School</option>
            </select>
          </div>
        </div>
      </div>

      <!-- Location -->
      <div>
        <p class="mb-3 text-[11px] font-semibold uppercase tracking-widest text-[var(--fg-muted)]">Location</p>
        <div class="grid grid-cols-2 gap-3">
          <div>
            <label class={lbl} for="sf-region">Region *</label>
            <select id="sf-region" bind:value={form.region_id} class={inp}>
              <option value="">Select…</option>
              {#each $regionsQuery.data ?? [] as r (r.id)}
                <option value={r.id}>{r.name}</option>
              {/each}
            </select>
          </div>
          <div>
            <label class={lbl} for="sf-district">District *</label>
            <select id="sf-district" bind:value={form.district_id} disabled={!form.region_id} class={inp}>
              <option value="">{form.region_id ? 'Select…' : 'Select a region first'}</option>
              {#each $districtsQuery.data ?? [] as d (d.id)}
                <option value={d.id}>{d.name}</option>
              {/each}
            </select>
          </div>
        </div>
      </div>

      <!-- Sign-in page -->
      <div>
        <p class="mb-3 text-[11px] font-semibold uppercase tracking-widest text-[var(--fg-muted)]">Sign-in page</p>
        <div class="space-y-3">
          <div>
            <label class={lbl} for="sf-subdomain">Subdomain</label>
            <input id="sf-subdomain" bind:value={form.subdomain} placeholder="leave blank to auto-generate from the name"
              class="{inp} lowercase" />
            {#if !isEdit}
              <p class="mt-1 text-[11px] text-[var(--fg-subtle)]">
                Every school gets a branded sign-in link automatically — only set this if you want a specific address instead.
              </p>
            {/if}
          </div>
          {#if isEdit}
            <div>
              <label class={lbl} for="sf-customdomain">Custom domain</label>
              <input id="sf-customdomain" bind:value={form.custom_domain} placeholder="e.g. portal.theirschool.edu.gh"
                class="{inp} lowercase" />
              <p class="mt-1 text-[11px] text-[var(--fg-subtle)]">
                Only set this once the school has pointed their own domain at this platform — self-declared, not verified automatically.
              </p>
            </div>
            <label class="flex min-h-[44px] cursor-pointer items-center gap-2 text-sm text-[var(--fg)]">
              <input type="checkbox" bind:checked={form.is_active} class="h-4 w-4 rounded accent-[var(--brand)]" />
              Active
            </label>
            {#if !form.is_active}
              <p class="rounded-lg bg-amber-50 px-3 py-2 text-[11px] text-amber-700 dark:bg-amber-950/30 dark:text-amber-400">
                Deactivating blocks sign-in for every account at this school immediately — nobody there will be able to log in until it's reactivated.
              </p>
            {/if}
          {/if}
        </div>
      </div>

      <!-- Contact -->
      <div>
        <p class="mb-3 text-[11px] font-semibold uppercase tracking-widest text-[var(--fg-muted)]">Contact</p>
        <div class="space-y-3">
          <div class="grid grid-cols-2 gap-3">
            <div>
              <label class={lbl} for="sf-phone">Phone</label>
              <input id="sf-phone" bind:value={form.phone} placeholder="0XX XXX XXXX" class={inp} />
            </div>
            <div>
              <label class={lbl} for="sf-email">Email</label>
              <input id="sf-email" bind:value={form.email} placeholder="school@example.edu.gh" class={inp} />
            </div>
          </div>
          <div>
            <label class={lbl} for="sf-address">Address</label>
            <input id="sf-address" bind:value={form.address} placeholder="Physical address" class={inp} />
          </div>
        </div>
      </div>

      <!-- Profile -->
      <div>
        <p class="mb-3 text-[11px] font-semibold uppercase tracking-widest text-[var(--fg-muted)]">Profile</p>
        <div class="space-y-3">
          <div>
            <label class={lbl} for="sf-motto">Motto</label>
            <input id="sf-motto" bind:value={form.motto} placeholder="e.g. Excellence in Service" class={inp} />
          </div>
          <div class="grid grid-cols-2 gap-3">
            <div>
              <label class={lbl} for="sf-year">Established year</label>
              <input id="sf-year" type="number" min="1800" max="2100" bind:value={form.established_year}
                placeholder="e.g. 1968" class={inp} />
            </div>
            <div class="flex items-end pb-1">
              <label class="flex min-h-[44px] cursor-pointer items-center gap-2 text-sm text-[var(--fg)]">
                <input type="checkbox" bind:checked={form.has_boarding} class="h-4 w-4 rounded accent-[var(--brand)]" />
                Boarding school
              </label>
            </div>
          </div>
        </div>
      </div>

    </div>

    <!-- Footer -->
    <div class="shrink-0 border-t border-[var(--border)] px-6 py-4">
      {#if formError}
        <p class="mb-3 text-xs text-red-500">{formError}</p>
      {/if}
      <div class="flex gap-2">
        <button onclick={submit} disabled={isPending}
          class="min-h-[44px] flex-1 rounded-xl py-2.5 text-sm font-semibold text-white transition
                 hover:opacity-90 disabled:opacity-50"
          style="background-color: var(--brand)">
          {#if isPending}
            {isEdit ? 'Saving…' : 'Creating…'}
          {:else}
            {isEdit ? 'Save changes' : 'Create school'}
          {/if}
        </button>
        <button onclick={requestClose}
          class="min-h-[44px] rounded-xl border border-[var(--border)] px-4 py-2 text-sm font-medium
                 text-[var(--fg-muted)] transition hover:bg-[var(--hover)]">
          Cancel
        </button>
      </div>
    </div>

  </div>
  </div>

  <ConfirmModal
    open={confirmDiscard}
    title={isEdit ? 'Discard changes?' : 'Discard new school?'}
    message="You've made changes that haven't been saved yet. Closing now will lose them."
    confirmLabel="Discard"
    variant="warning"
    onConfirm={() => { confirmDiscard = false; onCancel(); }}
    onCancel={() => confirmDiscard = false}
  />
{/if}
