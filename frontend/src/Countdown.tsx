import { useEffect, useRef, useState } from "react";

const TICK_MS = 250;
const WARN_MS = 10_000;

/**
 * Milliseconds left in the phase. Counts down from the server's remaining_ms using the local
 * monotonic clock, so a wrong client wall clock does not matter. Resyncs on every new state.
 */
function useCountdown(remainingMs: number | null, syncKey: number): number | null {
  const [left, setLeft] = useState(remainingMs);
  useEffect(() => {
    if (remainingMs === null) {
      setLeft(null);
      return;
    }
    const deadline = performance.now() + remainingMs;
    const tick = () => setLeft(Math.max(0, deadline - performance.now()));
    tick();
    const id = setInterval(tick, TICK_MS);
    return () => clearInterval(id);
  }, [remainingMs, syncKey]);
  return left;
}

function format(ms: number): string {
  const total = Math.ceil(ms / 1000);
  return `${Math.floor(total / 60)}:${String(total % 60).padStart(2, "0")}`;
}

interface Props {
  remainingMs: number | null;
  serverNow: number; // changes with every state message, which triggers a resync
  phaseKey: string; // e.g. "VOTING-1"; the bar's full width is the time left when this phase was first seen
}

export default function Countdown({ remainingMs, serverNow, phaseKey }: Props) {
  const left = useCountdown(remainingMs, serverNow);
  const total = useRef<{ key: string; ms: number } | null>(null);
  const bar = useRef<HTMLDivElement>(null);
  if (remainingMs !== null && total.current?.key !== phaseKey) {
    total.current = { key: phaseKey, ms: Math.max(remainingMs, 1) };
  }

  // The bar is driven per frame outside React state so it moves smoothly; with reduced motion it
  // steps once per second instead.
  useEffect(() => {
    const el = bar.current;
    const totalMs = total.current?.ms;
    if (remainingMs === null || !el || !totalMs) return;
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const deadline = performance.now() + remainingMs;
    let raf = 0;
    const frame = () => {
      let ms = Math.max(0, deadline - performance.now());
      if (reduce) ms = Math.ceil(ms / 1000) * 1000;
      el.style.transform = `scaleX(${Math.min(1, ms / totalMs)})`;
      if (ms > 0) raf = requestAnimationFrame(frame);
    };
    frame();
    return () => cancelAnimationFrame(raf);
  }, [remainingMs, serverNow, phaseKey]);

  if (left === null || !total.current) return null;
  const warn = left <= WARN_MS;

  return (
    <div>
      <div className="flex items-center justify-between text-sm">
        <span className="text-muted">Time left</span>
        {/* role=timer is not announced on every change; the sr-only line below speaks once at 10 s. */}
        <span
          role="timer"
          className={`font-semibold tabular-nums transition-colors duration-300 ${warn ? "text-danger" : "text-ink"}`}
        >
          {format(left)}
        </span>
      </div>
      <div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-track">
        <div
          ref={bar}
          className={`h-full origin-left rounded-full transition-colors duration-300 ${warn ? "bg-danger" : "bg-accent"}`}
        />
      </div>
      <span className="sr-only" aria-live="polite">
        {warn && left > 0 ? "Less than ten seconds left." : ""}
      </span>
    </div>
  );
}
