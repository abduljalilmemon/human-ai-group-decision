import { useEffect, useLayoutEffect, useRef, useState } from "react";

const TICK_MS = 250;
const WARN_MS = 10_000;
const R = 24;
const CIRCUMFERENCE = 2 * Math.PI * R;

/**
 * Milliseconds left in the phase. Counts down from the server's remaining_ms using the local
 * monotonic clock, so a wrong client wall clock does not matter. Resyncs on every new state.
 * At zero it shows 0:00 and waits: the next phase comes only from the server.
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
  phaseKey: string; // e.g. "VOTING-1"; the full ring is the time left when this phase was first seen
}

/** A ring that empties as the phase runs out, with the time in the middle. */
export default function Countdown({ remainingMs, serverNow, phaseKey }: Props) {
  const left = useCountdown(remainingMs, serverNow);
  const total = useRef<{ key: string; ms: number } | null>(null);
  const arc = useRef<SVGCircleElement>(null);
  if (remainingMs !== null && total.current?.key !== phaseKey) {
    total.current = { key: phaseKey, ms: Math.max(remainingMs, 1) };
  }

  // The arc is written per frame outside React state (paint only, no layout); with reduced
  // motion it steps once per second instead. Layout effect, so the first frame is already right.
  useLayoutEffect(() => {
    const el = arc.current;
    const totalMs = total.current?.ms;
    if (remainingMs === null || !el || !totalMs) return;
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const deadline = performance.now() + remainingMs;
    let raf = 0;
    const frame = () => {
      let ms = Math.max(0, deadline - performance.now());
      if (reduce) ms = Math.ceil(ms / 1000) * 1000;
      el.style.strokeDashoffset = String(CIRCUMFERENCE * (1 - Math.min(1, ms / totalMs)));
      if (ms > 0) raf = requestAnimationFrame(frame);
    };
    frame();
    return () => cancelAnimationFrame(raf);
  }, [remainingMs, serverNow, phaseKey]);

  if (left === null || !total.current) return null;
  const warn = left <= WARN_MS;

  return (
    <div className="relative h-16 w-16 shrink-0">
      <svg viewBox="0 0 64 64" className="h-full w-full -rotate-90" aria-hidden>
        <circle cx="32" cy="32" r={R} fill="none" strokeWidth="5" className="stroke-track" />
        <circle
          ref={arc}
          cx="32"
          cy="32"
          r={R}
          fill="none"
          strokeWidth="5"
          strokeLinecap="round"
          strokeDasharray={CIRCUMFERENCE}
          className={`transition-[stroke] duration-300 ${warn ? "stroke-danger" : "stroke-accent"}`}
        />
      </svg>
      {/* role=timer is not announced on every change; the sr-only line below speaks once. */}
      <span
        role="timer"
        className={`absolute inset-0 flex items-center justify-center text-sm font-semibold tabular-nums transition-colors duration-300 ${
          warn ? "text-danger" : "text-ink"
        }`}
      >
        <span className="sr-only">Time left: </span>
        {format(left)}
      </span>
      <span className="sr-only" aria-live="polite">
        {warn && left > 0 ? "Less than ten seconds left." : ""}
      </span>
    </div>
  );
}
