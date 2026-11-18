import { useEffect, useRef, useState } from "react";

const TICK_MS = 200;

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
  if (remainingMs !== null && total.current?.key !== phaseKey) {
    total.current = { key: phaseKey, ms: Math.max(remainingMs, 1) };
  }
  if (left === null || !total.current) return null;

  const fraction = Math.min(1, left / total.current.ms);
  return (
    <div aria-label="Time remaining">
      <div className="flex justify-end">
        <span className={`font-mono text-sm tabular-nums ${left <= 5000 ? "text-rose-600" : "text-slate-500"}`}>
          {format(left)}
        </span>
      </div>
      <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-slate-100">
        <div
          className="h-full rounded-full bg-indigo-500 transition-[width] duration-200 ease-linear motion-reduce:transition-none"
          style={{ width: `${fraction * 100}%` }}
        />
      </div>
    </div>
  );
}
