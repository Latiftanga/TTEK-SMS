<script lang="ts">
  import { createMutation, useQueryClient } from '@tanstack/svelte-query';
  import { reactiveQuery } from '$lib/query.svelte';
  import {
    listChatMessages, sendChatMessage, finalizeChat, type LessonPlan,
  } from '$lib/api/lessonPlans';
  import { apiError } from '$lib/utils';
  import { toast } from '$lib/stores/toast';
  import { isOnline } from '$lib/offline/sync';

  interface Props {
    plan: LessonPlan;
    classId: string; subjectId: string; academicTermId: string; weekStart: string;
  }
  const { plan, classId, subjectId, academicTermId, weekStart }: Props = $props();

  const messagesQ = reactiveQuery(() => ({
    queryKey: ['lesson-plan-chat', plan.id] as const,
    queryFn: () => listChatMessages(plan.id),
    staleTime: 10_000,
  }));
  const messages = $derived($messagesQ.data ?? []);

  let draft = $state('');

  const qc = useQueryClient();
  function invalidateChat() {
    qc.invalidateQueries({ queryKey: ['lesson-plan-chat', plan.id] });
  }
  function invalidatePlan() {
    qc.invalidateQueries({ queryKey: ['lesson-plans', classId, subjectId, academicTermId, weekStart] });
  }

  const sendMut = createMutation({
    mutationFn: (message: string) => sendChatMessage(plan.id, message),
    onSuccess: () => { invalidateChat(); draft = ''; },
    onError: (e: unknown) => toast.error(apiError(e, 'Could not send that message.')),
  });

  const finalizeMut = createMutation({
    mutationFn: () => finalizeChat(plan.id),
    onSuccess: () => { invalidatePlan(); toast.success('Lesson plan generated from this conversation.'); },
    onError: (e: unknown) => toast.error(apiError(e, 'Could not finalize this conversation.')),
  });

  function handleSend() {
    if (!draft.trim() || $sendMut.isPending) return;
    $sendMut.mutate(draft.trim());
  }
</script>

<div class="mt-6 space-y-3 rounded-2xl border border-[var(--border)] bg-[var(--card)] p-5">
  <div class="flex items-center justify-between gap-2">
    <h3 class="text-sm font-semibold text-[var(--fg)]">Chat with the AI assistant</h3>
    {#if !$isOnline}
      <span class="text-xs font-medium text-[var(--fg-muted)]">Offline — connect to chat</span>
    {/if}
  </div>
  <p class="text-xs text-[var(--fg-muted)]">
    Ask about this topic — the assistant grounds its answers in any curriculum
    materials uploaded for this class and subject. When you're happy with the
    plan, use "Generate lesson plan from this conversation" below.
  </p>

  <div class="max-h-96 space-y-3 overflow-y-auto rounded-xl border border-[var(--border)] bg-[var(--bg)] p-3">
    {#if $messagesQ.isPending}
      <div class="h-16 animate-pulse rounded-xl bg-[var(--hover)]"></div>
    {:else if messages.length === 0}
      <p class="py-6 text-center text-xs text-[var(--fg-subtle)]">No messages yet — ask your first question below.</p>
    {:else}
      {#each messages as m (m.id)}
        <div class="flex {m.role === 'USER' ? 'justify-end' : 'justify-start'}">
          <div class="max-w-[85%] rounded-xl px-3 py-2 text-sm {m.role === 'USER'
            ? 'text-white'
            : 'border border-[var(--border)] bg-[var(--card)] text-[var(--fg)]'}"
            style={m.role === 'USER' ? 'background: var(--brand)' : ''}>
            {m.content}
          </div>
        </div>
      {/each}
    {/if}
    {#if $sendMut.isPending}
      <div class="flex justify-start">
        <div class="rounded-xl border border-[var(--border)] bg-[var(--card)] px-3 py-2 text-sm text-[var(--fg-muted)]">Thinking…</div>
      </div>
    {/if}
  </div>

  <div class="flex gap-2">
    <textarea bind:value={draft} rows="2" placeholder="Ask the assistant something…"
      onkeydown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend(); } }}
      class="flex-1 rounded-xl border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--fg)] focus:border-[var(--brand)] focus:outline-none transition"></textarea>
    <button onclick={handleSend} disabled={!draft.trim() || $sendMut.isPending || !$isOnline}
      class="min-h-[44px] shrink-0 rounded-xl px-4 py-2 text-sm font-semibold text-white transition hover:opacity-90 disabled:opacity-50"
      style="background: var(--brand)">
      Send
    </button>
  </div>

  {#if messages.length > 0}
    <button onclick={() => $finalizeMut.mutate()} disabled={$finalizeMut.isPending || !$isOnline}
      class="min-h-[44px] w-full rounded-xl border border-[var(--border)] px-4 py-2 text-sm font-semibold text-[var(--fg)] transition hover:bg-[var(--hover)] disabled:opacity-50">
      {$finalizeMut.isPending ? 'Generating…' : 'Generate lesson plan from this conversation →'}
    </button>
  {/if}
</div>
