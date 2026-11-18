import type { ReactNode } from "react";
import Countdown from "./Countdown";
import type { ServerState } from "./useSession";

// Colors come from the label letter only ("Player B" -> b). Labels are shuffled per session on the
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
  sm: "h-7 w-7 text-xs",
  md: "h-12 w-12 text-lg",
  lg: "h-20 w-20 text-3xl",
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
    <span className="inline-flex items-center gap-2 rounded-full bg-canvas py-1 pr-3 pl-1 text-sm text-muted ring-1 ring-line">
      <Avatar label={label} />
      <span>
        You are <span className="font-semibold text-ink">{label}</span>
      </span>
    </span>
  );
}

const PHASE_TITLE: Record<ServerState["phase"], string> = {
  WAITING: "Waiting room",
  DISCUSSION: "Discussion",
  VOTING: "Vote",
  ROUND_RESULT: "Results",
  FINAL: "Final results",
};

/** Countdown, round and phase, and the player's own label: the same frame on every timed screen. */
export function PhaseHeader({ state, hint }: { state: ServerState; hint: string }) {
  return (
    <header>
      <Countdown remainingMs={state.remaining_ms} serverNow={state.server_now} phaseKey={`${state.phase}-${state.round}`} />
      <div className="mt-4 flex flex-wrap items-center justify-between gap-x-4 gap-y-2">
        <h1 className="text-xl font-semibold text-balance">
          <span className="text-muted">Round {state.round}</span>
          <span aria-hidden className="mx-2 text-line">/</span>
          {PHASE_TITLE[state.phase]}
        </h1>
        <YouChip label={state.you} />
      </div>
      <p className="mt-1.5 text-sm text-muted">{hint}</p>
    </header>
  );
}

export function ErrorLine({ children }: { children: ReactNode }) {
  return (
    <p role="alert" className="flex items-center gap-1.5 text-sm text-danger">
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
