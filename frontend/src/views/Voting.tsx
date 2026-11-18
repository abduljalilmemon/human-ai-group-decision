import { useState } from "react";
import Countdown from "../Countdown";
import type { ServerState } from "../useSession";

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
      <Countdown remainingMs={state.remaining_ms} serverNow={state.server_now} phaseKey={`${state.phase}-${state.round}`} />
      <div className="mt-3 flex items-baseline justify-between">
        <h1 className="text-lg font-semibold">Round {state.round} · Vote</h1>
        <span className="text-sm text-slate-500">
          You are <span className="font-semibold text-indigo-600">{state.you}</span>
        </span>
      </div>
      <p className="mt-1 text-sm text-slate-500">
        Who should be the Decision Maker? Your vote is secret. You may vote for yourself.
      </p>

      <ul className="mt-5 grid gap-3 sm:grid-cols-3">
        {state.players.map((label) => {
          const selected = choice === label && (state.has_voted || pending);
          return (
            <li key={label}>
              <button
                type="button"
                onClick={() => pick(label)}
                disabled={locked}
                aria-pressed={selected}
                className={`w-full rounded-xl border-2 px-4 py-5 text-center transition motion-reduce:transition-none ${
                  selected
                    ? "border-indigo-600 bg-indigo-50"
                    : "border-slate-200 bg-white enabled:hover:-translate-y-0.5 enabled:hover:border-indigo-300 enabled:hover:shadow-sm enabled:active:scale-95"
                } disabled:cursor-default ${locked && !selected ? "opacity-50" : ""}`}
              >
                <span className="block font-semibold">{label}</span>
                {label === state.you && <span className="mt-0.5 block text-xs text-slate-400">You</span>}
              </button>
            </li>
          );
        })}
      </ul>

      <p className="mt-4 min-h-5 text-center text-sm" aria-live="polite">
        {state.has_voted ? (
          <span className="text-emerald-600">Vote recorded. Waiting for the others…</span>
        ) : pending ? (
          <span className="text-slate-500">Sending vote…</span>
        ) : error ? (
          <span className="text-rose-600">{ERROR_TEXT[error] ?? error}</span>
        ) : (
          <span className="text-slate-400">Choose one player. Votes cannot be changed.</span>
        )}
      </p>
    </div>
  );
}
