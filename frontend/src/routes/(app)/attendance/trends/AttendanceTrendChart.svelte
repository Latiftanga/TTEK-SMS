<script lang="ts">
  import type { AttendanceTrendPoint } from '$lib/api/attendance';

  interface Props { points: AttendanceTrendPoint[]; }
  const { points }: Props = $props();

  // Hand-rolled inline SVG — no charting library, matching this codebase's
  // existing convention of hand-rolled CSS/SVG "charts" (StatCard's trend
  // text, MyClassesCard's progress bars) rather than pulling in a dependency.
  const W = 640, H = 180, PAD_L = 32, PAD_B = 20, PAD_T = 10;
  const chartW = W - PAD_L - 8;
  const chartH = H - PAD_T - PAD_B;

  function x(i: number): number {
    if (points.length <= 1) return PAD_L;
    return PAD_L + (i / (points.length - 1)) * chartW;
  }
  function y(rate: number): number {
    return PAD_T + (1 - rate / 100) * chartH;
  }

  const pathD = $derived(
    points.length === 0 ? '' : points.map((p, i) => `${i === 0 ? 'M' : 'L'} ${x(i).toFixed(1)} ${y(p.rate).toFixed(1)}`).join(' '),
  );

  const GRID = [0, 25, 50, 75, 100];

  function fmtDate(d: string): string {
    return new Date(d).toLocaleDateString('en-GB', { day: 'numeric', month: 'short' });
  }
</script>

{#if points.length === 0}
  <div class="flex h-[180px] items-center justify-center text-sm text-[var(--fg-muted)]">
    No markable days in this term yet.
  </div>
{:else}
  <svg viewBox="0 0 {W} {H}" class="w-full" role="img" aria-label="Attendance rate over time">
    {#each GRID as g}
      <line x1={PAD_L} x2={W - 8} y1={y(g)} y2={y(g)} stroke="var(--border)" stroke-width="1" />
      <text x={PAD_L - 6} y={y(g) + 3} text-anchor="end" font-size="9" fill="var(--fg-subtle)">{g}%</text>
    {/each}
    <!-- 90% (AT_RISK boundary) reference line, a touch more visible -->
    <line x1={PAD_L} x2={W - 8} y1={y(90)} y2={y(90)} stroke="#f59e0b" stroke-width="1" stroke-dasharray="3 3" opacity="0.6" />

    <path d={pathD} fill="none" stroke="var(--brand)" stroke-width="2" />
    {#each points as p, i}
      <circle cx={x(i)} cy={y(p.rate)} r="2.5" fill="var(--brand)">
        <title>{fmtDate(p.date)}: {p.rate}% ({p.present}/{p.total})</title>
      </circle>
    {/each}

    <text x={PAD_L} y={H - 4} font-size="9" fill="var(--fg-subtle)">{fmtDate(points[0].date)}</text>
    <text x={W - 8} y={H - 4} text-anchor="end" font-size="9" fill="var(--fg-subtle)">{fmtDate(points[points.length - 1].date)}</text>
  </svg>
{/if}
