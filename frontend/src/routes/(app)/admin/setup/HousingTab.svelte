<script lang="ts">
  import { createQuery, createMutation, useQueryClient } from '@tanstack/svelte-query';
  import { getMySchool, updateMySchool } from '$lib/api/schools';
  import {
    listHouses, createHouse, updateHouse, addRoom,
    type House, type HouseGender,
  } from '$lib/api/housing';
  import { toast } from '$lib/stores/toast';

  const qc = useQueryClient();

  const schoolQ = createQuery({ queryKey: ['my-school'], queryFn: getMySchool, staleTime: 60_000 });

  const hasBoarding = $derived($schoolQ.data?.has_boarding ?? false);

  // ── Enable boarding ───────────────────────────────────────────────────────────
  const enableMut = createMutation({
    mutationFn: () => updateMySchool({ has_boarding: true }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['my-school'] });
      qc.invalidateQueries({ queryKey: ['houses'] });
      toast.success('Boarding enabled.');
    },
    onError: () => toast.error('Could not enable boarding.'),
  });

  // ── Houses list ───────────────────────────────────────────────────────────────
  const housesQ = createQuery({
    queryKey: ['houses'],
    queryFn: listHouses,
    enabled: () => hasBoarding,
    staleTime: 60_000,
  });

  // ── Create house ──────────────────────────────────────────────────────────────
  let showHouseForm  = $state(false);
  let hName    = $state('');
  let hCode    = $state('');
  let hGender  = $state<HouseGender>('MIXED');
  let hCap     = $state('');
  let hColor   = $state('#1e40af');
  let hError   = $state('');

  const createMut = createMutation({
    mutationFn: () => createHouse({
      name: hName.trim(), code: hCode.trim().toUpperCase(), gender: hGender,
      capacity: hCap ? Number(hCap) : null, color: hColor,
    }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['houses'] });
      showHouseForm = false; hName = ''; hCode = ''; hGender = 'MIXED'; hCap = ''; hError = '';
      toast.success('House created.');
    },
    onError: (e: unknown) => {
      hError = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
        ?? 'Could not create house.';
    },
  });

  // ── Add room (per house) ──────────────────────────────────────────────────────
  let addRoomFor  = $state('');   // house id currently adding room to
  let rNum        = $state('');
  let rCap        = $state('');
  let rError      = $state('');

  const addRoomMut = createMutation({
    mutationFn: () => addRoom(addRoomFor, { room_number: rNum.trim(), capacity: rCap ? Number(rCap) : null }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['houses'] });
      addRoomFor = ''; rNum = ''; rCap = ''; rError = '';
      toast.success('Room added.');
    },
    onError: (e: unknown) => {
      rError = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
        ?? 'Could not add room.';
    },
  });

  // ── Toggle house active ───────────────────────────────────────────────────────
  const toggleMut = createMutation({
    mutationFn: (h: House) => updateHouse(h.id, { is_active: !h.is_active }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['houses'] }); },
    onError: () => toast.error('Could not update house.'),
  });

  let expandedHouse = $state('');

  const GENDER_LABEL: Record<HouseGender, string> = {
    MALE: 'Boys', FEMALE: 'Girls', MIXED: 'Mixed',
  };
</script>

<!-- Not enabled ─────────────────────────────────────────────────────────────── -->
{#if $schoolQ.isPending}
  <div class="h-24 animate-pulse rounded-xl bg-[var(--card)]"></div>
{:else if !hasBoarding}
  <div class="rounded-xl border border-[var(--border)] bg-[var(--card)] p-8 text-center">
    <svg class="mx-auto mb-3 h-10 w-10 text-[var(--fg-subtle)]" fill="none" stroke="currentColor" stroke-width="1.5" viewBox="0 0 24 24">
      <path stroke-linecap="round" stroke-linejoin="round" d="M2.25 12l8.954-8.955c.44-.439 1.152-.439 1.591 0L21.75 12M4.5 9.75v10.125c0 .621.504 1.125 1.125 1.125H9.75v-4.875c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125V21h4.125c.621 0 1.125-.504 1.125-1.125V9.75"/>
    </svg>
    <p class="text-sm font-semibold text-[var(--fg)]">Boarding not enabled</p>
    <p class="mt-1 text-xs text-[var(--fg-muted)]">Enable boarding to manage houses, rooms, and student assignments.</p>
    <button onclick={() => $enableMut.mutate()} disabled={$enableMut.isPending}
      class="mt-4 btn-primary">
      {$enableMut.isPending ? 'Enabling…' : 'Enable boarding'}
    </button>
  </div>

<!-- Boarding enabled ─────────────────────────────────────────────────────────── -->
{:else}
  <div class="space-y-4">
    <div class="flex items-center justify-between">
      <p class="text-sm text-[var(--fg-muted)]">
        {($housesQ.data ?? []).length} house{($housesQ.data ?? []).length !== 1 ? 's' : ''} configured
      </p>
      {#if !showHouseForm}
        <button onclick={() => showHouseForm = true} class="btn-primary text-xs">+ Add house</button>
      {/if}
    </div>

    <!-- ── Create house form ──────────────────────────────────────────────────── -->
    {#if showHouseForm}
      <div class="rounded-xl border border-[var(--border)] bg-[var(--card)] p-5 space-y-4">
        <h2 class="text-sm font-semibold text-[var(--fg)]">New House</h2>
        <div class="grid gap-3 sm:grid-cols-2">
          <div>
            <label class="mb-1 block text-xs font-medium text-[var(--fg-muted)]">House Name <span class="text-red-500">*</span></label>
            <input bind:value={hName} placeholder="e.g. Volta House" class="inp" />
          </div>
          <div>
            <label class="mb-1 block text-xs font-medium text-[var(--fg-muted)]">Code <span class="text-red-500">*</span></label>
            <input bind:value={hCode} placeholder="e.g. VH" maxlength="5" class="inp" />
          </div>
          <div>
            <label class="mb-1 block text-xs font-medium text-[var(--fg-muted)]">Gender</label>
            <select bind:value={hGender} class="inp">
              <option value="MALE">Boys</option>
              <option value="FEMALE">Girls</option>
              <option value="MIXED">Mixed</option>
            </select>
          </div>
          <div>
            <label class="mb-1 block text-xs font-medium text-[var(--fg-muted)]">Capacity</label>
            <input bind:value={hCap} type="number" min="1" placeholder="e.g. 120" class="inp" />
          </div>
          <div class="sm:col-span-2">
            <label class="mb-1 block text-xs font-medium text-[var(--fg-muted)]">House colour</label>
            <div class="flex items-center gap-2">
              <input type="color" bind:value={hColor} class="h-9 w-12 cursor-pointer rounded-lg border border-[var(--border)] bg-[var(--bg)] p-1" />
              <input bind:value={hColor} class="inp flex-1" placeholder="#1e40af" />
            </div>
          </div>
        </div>
        {#if hError}<p class="text-xs text-red-500">{hError}</p>{/if}
        <div class="flex gap-2">
          <button onclick={() => $createMut.mutate()} disabled={!hName || !hCode || $createMut.isPending} class="btn-primary">
            {$createMut.isPending ? 'Creating…' : 'Create house'}
          </button>
          <button onclick={() => { showHouseForm = false; hError = ''; }} class="btn-ghost">Cancel</button>
        </div>
      </div>
    {/if}

    <!-- ── House cards ────────────────────────────────────────────────────────── -->
    {#if $housesQ.isPending}
      <div class="space-y-2">{#each [1,2,3] as _}<div class="h-16 animate-pulse rounded-xl bg-[var(--card)]"></div>{/each}</div>
    {:else if ($housesQ.data ?? []).length === 0 && !showHouseForm}
      <div class="rounded-xl border border-dashed border-[var(--border)] p-8 text-center text-sm text-[var(--fg-muted)]">
        No houses yet. Add your first house to get started.
      </div>
    {:else}
      <div class="space-y-2">
        {#each $housesQ.data ?? [] as house (house.id)}
          {@const isOpen = expandedHouse === house.id}
          <div class="overflow-hidden rounded-xl border bg-[var(--card)] transition-all
            {isOpen ? 'border-[var(--brand)]/40' : 'border-[var(--border)]'}">

            <!-- House header -->
            <button onclick={() => expandedHouse = isOpen ? '' : house.id}
              class="flex w-full items-center gap-3 px-5 py-4 text-left transition hover:bg-[var(--hover)]">
              <div class="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-xs font-bold text-white"
                   style="background-color: {house.color ?? 'var(--brand)'}">
                {house.code.slice(0, 2)}
              </div>
              <div class="min-w-0 flex-1">
                <span class="font-semibold text-[var(--fg)]">{house.name}</span>
                <span class="ml-2 text-xs text-[var(--fg-muted)]">{GENDER_LABEL[house.gender]}</span>
                {#if house.capacity}
                  <span class="ml-2 text-xs text-[var(--fg-muted)]">· {house.capacity} cap.</span>
                {/if}
                <span class="ml-2 text-xs text-[var(--fg-muted)]">· {house.rooms.length} room{house.rooms.length !== 1 ? 's' : ''}</span>
              </div>
              {#if !house.is_active}
                <span class="shrink-0 rounded-full bg-[var(--hover)] px-2.5 py-0.5 text-xs text-[var(--fg-muted)]">Inactive</span>
              {/if}
              <svg class="h-4 w-4 shrink-0 text-[var(--fg-muted)] transition-transform {isOpen ? 'rotate-90' : ''}"
                fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" d="M9 5l7 7-7 7"/>
              </svg>
            </button>

            <!-- Rooms (expanded) -->
            {#if isOpen}
              <div class="border-t border-[var(--border)] px-5 pb-4 pt-3 space-y-3">

                {#if house.rooms.length > 0}
                  <div class="grid grid-cols-2 gap-1.5 sm:grid-cols-3 lg:grid-cols-4">
                    {#each house.rooms as room (room.id)}
                      <div class="rounded-lg border border-[var(--border)] px-3 py-2">
                        <p class="text-xs font-semibold text-[var(--fg)]">Room {room.room_number}</p>
                        {#if room.capacity}
                          <p class="text-[10px] text-[var(--fg-muted)]">{room.capacity} beds</p>
                        {/if}
                      </div>
                    {/each}
                  </div>
                {/if}

                <!-- Add room form -->
                {#if addRoomFor === house.id}
                  <div class="rounded-xl border border-[var(--border)] p-3 space-y-2">
                    <p class="text-xs font-medium text-[var(--fg-muted)]">Add room</p>
                    <div class="flex gap-2">
                      <input bind:value={rNum} placeholder="Room number" class="inp flex-1" />
                      <input bind:value={rCap} type="number" min="1" placeholder="Beds" class="inp w-20" />
                    </div>
                    {#if rError}<p class="text-xs text-red-500">{rError}</p>{/if}
                    <div class="flex gap-2">
                      <button onclick={() => $addRoomMut.mutate()} disabled={!rNum || $addRoomMut.isPending} class="btn-primary text-xs">
                        {$addRoomMut.isPending ? '…' : 'Add'}
                      </button>
                      <button onclick={() => { addRoomFor = ''; rError = ''; }} class="btn-ghost text-xs">Cancel</button>
                    </div>
                  </div>
                {:else}
                  <div class="flex items-center justify-between">
                    <button onclick={() => { addRoomFor = house.id; rNum = ''; rCap = ''; rError = ''; }}
                      class="text-xs font-semibold transition hover:underline" style="color: var(--brand)">
                      + Add room
                    </button>
                    <button onclick={() => $toggleMut.mutate(house)} disabled={$toggleMut.isPending}
                      class="text-xs text-[var(--fg-muted)] transition hover:text-[var(--fg)]">
                      {house.is_active ? 'Deactivate' : 'Reactivate'}
                    </button>
                  </div>
                {/if}
              </div>
            {/if}
          </div>
        {/each}
      </div>
    {/if}
  </div>
{/if}

<style>
  @reference "tailwindcss";
  .inp { @apply w-full rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--fg)] focus:border-[var(--brand)] focus:outline-none transition; }
</style>
