import { useState } from "react";
import type { ServerState } from "../useSession";
import { Avatar, ErrorLine, PhaseHeader, Spinner } from "../ui";

const ERROR_TEXT: Record<string, string> = {
  voting_closed: "Voting has closed.",
  already_voted: "Your vote for this round is already in.",
  invalid_target: "That choice is not valid.",
};

interface Props {
  state: ServerState;
  error: string | null;
  onVote: (target: string) => boolean;
}

// Mount with key={round} so the local choice resets each round.
export default function Voting({ state, error, onVote }: Props) {
  const [choice, setChoice] = useState<string | null>(null);
  const pending = choice !== null && !state.has_voted && !error;
  const locked = state.has_voted || pending;

  const pick = (label: string) => {
    if (locked) return;
    if (onVote(label)) setChoice(label);
  };

  return (
    <div>
      <PhaseHeader state={state} hint="Who should be the Decision Maker? Your vote is secret. You may vote for yourself." />

      <ul className="mt-6 grid gap-3 sm:grid-cols-3" aria-label="Players">
        {state.players.map((label) => {
          const selected = choice === label && (state.has_voted || pending);
          return (
            <li key={label}>
              <button
                type="button"
                onClick={() => pick(label)}
                disabled={locked}
                aria-pressed={selected}
                className={`group relative flex w-full flex-col items-center gap-3 rounded-2xl border-2 px-4 py-6 text-center transition duration-200 ease-out ${
                  selected
                    ? "border-accent bg-accent-soft shadow-[0_6px_20px_-8px_oklch(49%_0.2_272/0.45)]"
                    : "border-line bg-surface enabled:hover:-translate-y-1 enabled:hover:border-accent/50 enabled:hover:shadow-[0_8px_24px_-12px_oklch(26%_0.025_262/0.3)] enabled:active:translate-y-0 enabled:active:scale-[0.97]"
                } disabled:cursor-default ${locked && !selected ? "opacity-55" : ""}`}
              >
                {selected && (
                  <span className="absolute top-3 right-3 flex h-6 w-6 animate-enter items-center justify-center rounded-full bg-accent text-white">
                    <svg viewBox="0 0 16 16" className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth="2.2" aria-hidden>
                      <path d="M3.5 8.5l3 3 6-7" strokeLinecap="round" strokeLinejoin="round" />
                    </svg>
                  </span>
                )}
                <Avatar label={label} size="md" />
                <span className="text-base font-semibold text-ink">
                  {label}
                  {label === state.you && <span className="block text-xs font-normal text-muted">You</span>}
                </span>
              </button>
            </li>
          );
        })}
      </ul>

      <div className="mt-5 flex min-h-6 justify-center text-sm" aria-live="polite">
        {state.has_voted ? (
          <span className="flex items-center gap-1.5 font-medium text-success">
            <svg viewBox="0 0 16 16" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden>
              <path d="M3.5 8.5l3 3 6-7" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
            Vote recorded. Waiting for the others…
          </span>
        ) : pending ? (
          <span className="flex items-center gap-2 text-muted">
            <Spinner /> Sending vote…
          </span>
        ) : error ? (
          <ErrorLine>{ERROR_TEXT[error] ?? error}</ErrorLine>
        ) : (
          <span className="text-muted">Choose one player. Votes cannot be changed.</span>
        )}
      </div>
    </div>
  );
}
