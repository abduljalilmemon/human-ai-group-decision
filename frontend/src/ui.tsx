import type { ReactNode } from "react";
import { m } from "motion/react";
import Countdown from "./Countdown";
import type { Phase, ServerState } from "./useSession";

// Colors come from the label letter only ("Player B" -> B). Labels are shuffled per session on the
// server, so a color never maps to a participant type.
const PLAYER_TINT: Record<string, string> = {
  A: "bg-player-a text-player-a-ink",
  B: "bg-player-b text-player-b-ink",
  C: "bg-player-c text-player-c-ink",
};

function letter(label: string): string {
  return label.trim().slice(-1).toUpperCase();
}

const AVATAR_SIZE = {
  xs: "h-5 w-5 text-[0.625rem]",
  sm: "h-7 w-7 text-xs",
  md: "h-12 w-12 text-lg",
  xl: "h-24 w-24 text-4xl",
};

export function Avatar({ label, size = "sm" }: { label: string; size?: keyof typeof AVATAR_SIZE }) {
  return (
    <span
      aria-hidden
      className={`inline-flex shrink-0 items-center justify-center rounded-full font-semibold ${AVATAR_SIZE[size]} ${
        PLAYER_TINT[letter(label)] ?? "bg-track text-muted"
      }`}
    >
      {letter(label)}
    </span>
  );
}

export function YouChip({ label }: { label: string | null }) {
  if (!label) return null;
  return (
    <span className="inline-flex items-center gap-2 rounded-full bg-surface py-1 pr-3 pl-1 text-sm text-muted ring-1 ring-line">
      <Avatar label={label} />
      <span>
        You are <span className="font-semibold text-ink">{label}</span>
      </span>
    </span>
  );
}

// The stepper always shows two rounds, matching the brief (config.yml: rounds: 2).
const STEPS = ["Round 1", "Vote", "Round 2", "Vote", "Result"];

function stepIndex(phase: Phase, round: number): number {
  switch (phase) {
    case "WAITING":
      return -1;
    case "DISCUSSION":
      return (round - 1) * 2;
    case "VOTING":
    case "ROUND_RESULT":
      return (round - 1) * 2 + 1;
    case "FINAL":
      return STEPS.length - 1;
  }
}

/** Where the session is: driven only by the server's phase and round. */
export function Stepper({ phase, round }: { phase: Phase; round: number }) {
  const active = stepIndex(phase, round);
  // During a round's results the track is already halfway to the next round.
  const fill = (Math.max(0, active) + (phase === "ROUND_RESULT" ? 0.5 : 0)) / (STEPS.length - 1);
  return (
    <nav aria-label="Session progress">
      <ol className="relative grid grid-cols-5">
        <span aria-hidden className="absolute top-[9px] right-[10%] left-[10%] h-0.5 overflow-hidden rounded-full bg-line">
          <span
            className="block h-full origin-left bg-accent-text transition-transform duration-700 ease-[var(--ease-out-expo)]"
            style={{ transform: `scaleX(${fill})` }}
          />
        </span>
        {STEPS.map((step, i) => {
          const done = i < active;
          const current = i === active;
          return (
            <li key={i} className="relative flex flex-col items-center gap-1.5" aria-current={current ? "step" : undefined}>
              <span className="relative flex h-5 w-5 items-center justify-center">
                {current && (
                  <span className="absolute inset-0 animate-pop rounded-full bg-accent-soft ring-2 ring-accent-text" />
                )}
                <span
                  className={`relative h-2.5 w-2.5 rounded-full transition-colors duration-500 ${
                    done || current ? "bg-accent-text" : "bg-canvas ring-2 ring-line"
                  }`}
                />
              </span>
              <span className={`text-[0.6875rem] font-semibold tracking-[0.14em] uppercase transition-colors duration-500 ${current ? "text-ink" : "text-muted"}`}>
                {step}
                {done && <span className="sr-only"> (done)</span>}
              </span>
            </li>
          );
        })}
      </ol>
    </nav>
  );
}

/** Title, hint, own label, and the countdown ring: the same frame on every timed screen. */
export function PhaseHeader({ state, title, hint }: { state: ServerState; title: string; hint: string }) {
  return (
    <header className="flex items-start justify-between gap-4">
      <div className="min-w-0">
        <h1 className="text-xl font-semibold tracking-tight text-balance sm:text-2xl">{title}</h1>
        <p className="mt-1 text-sm text-pretty text-muted">{hint}</p>
        <div className="mt-3">
          <YouChip label={state.you} />
        </div>
      </div>
      <Countdown
        remainingMs={state.remaining_ms}
        serverNow={state.server_now}
        phaseKey={`${state.phase}-${state.round}`}
        urgent={state.phase === "DISCUSSION" || state.phase === "VOTING"}
      />
    </header>
  );
}

export function ErrorLine({ children }: { children: ReactNode }) {
  return (
    <p role="alert" className="flex animate-enter items-center gap-1.5 text-sm text-danger">
      <svg viewBox="0 0 16 16" className="h-4 w-4 shrink-0" fill="none" stroke="currentColor" strokeWidth="1.6" aria-hidden>
        <circle cx="8" cy="8" r="6.25" />
        <path d="M8 4.75v3.75M8 10.9v.1" strokeLinecap="round" />
      </svg>
      {children}
    </p>
  );
}

export function Spinner({ className = "h-4 w-4" }: { className?: string }) {
  return (
    <svg viewBox="0 0 16 16" className={`${className} animate-spin`} fill="none" aria-hidden>
      <circle cx="8" cy="8" r="6" stroke="currentColor" strokeOpacity="0.25" strokeWidth="2" />
      <path d="M14 8a6 6 0 0 0-6-6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
    </svg>
  );
}

export function Check({ className = "h-3.5 w-3.5" }: { className?: string }) {
  return (
    <svg viewBox="0 0 16 16" className={className} fill="none" stroke="currentColor" strokeWidth="2.2" aria-hidden>
      <path d="M3.5 8.5l3 3 6-7" strokeLinecap="round" strokeLinejoin="round" strokeDasharray="16" className="animate-draw" />
    </svg>
  );
}

/** A notice that slides down from the top edge. Mount inside AnimatePresence. */
export function Banner({ tone, children }: { tone: "warn" | "info"; children: ReactNode }) {
  return (
    <m.div
      role="status"
      initial={{ y: -64, opacity: 0 }}
      animate={{ y: 0, opacity: 1 }}
      exit={{ y: -64, opacity: 0 }}
      transition={{ type: "spring", stiffness: 420, damping: 34 }}
      className="fixed inset-x-0 top-0 z-20 flex justify-center p-3"
    >
      <div
        className={`flex max-w-[calc(100vw-2rem)] items-center gap-2.5 rounded-full px-5 py-2.5 text-sm font-medium ${
          tone === "warn" ? "glass bg-warn-bg text-warn-ink" : "glass text-ink"
        }`}
      >
        {children}
      </div>
    </m.div>
  );
}
