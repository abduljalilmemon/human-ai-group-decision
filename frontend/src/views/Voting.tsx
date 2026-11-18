import { useState } from "react";
import type { ServerState } from "../useSession";
import { Avatar, Check, ErrorLine, PhaseHeader, Spinner } from "../ui";

const ERROR_TEXT: Record<string, string> = {
  voting_closed: "Voting has closed.",
  already_voted: "Your vote for this round is already in.",
  invalid_target: "That choice is not valid.",
  not_connected: "Not connected right now. Try again in a moment.",
};

interface Props {
  state: ServerState;
  error: string | null;
  onVote: (target: string) => boolean;
}

// Mount with key={round} so the local choice resets each round. Votes cannot be changed, so a
// pick is only sent after an explicit confirm.
export default function Voting({ state, error, onVote }: Props) {
  const [choice, setChoice] = useState<string | null>(null);
  const [sent, setSent] = useState(false);
  const [localError, setLocalError] = useState<string | null>(null);
  const pending = sent && !state.has_voted && !error;
  const locked = state.has_voted || pending;
  const shownError = localError ?? error;

  const pick = (label: string) => {
    if (locked) return;
    setLocalError(null);
    setChoice(label);
  };

  const confirm = () => {
    if (!choice || locked) return;
    if (onVote(choice)) {
      setSent(true);
      setLocalError(null);
    } else {
      setLocalError("not_connected");
    }
  };

  return (
    <div>
      <PhaseHeader
        state={state}
        title={`Round ${state.round} vote`}
        hint="Who should be the Decision Maker? Your vote is secret. You may vote for yourself."
      />

      <ul className="mt-6 grid grid-cols-3 gap-2.5 sm:gap-3" aria-label="Players">
        {state.players.map((label) => {
          const selected = choice === label;
          return (
            <li key={label}>
              <button
                type="button"
                onClick={() => pick(label)}
                disabled={locked}
                aria-pressed={selected}
                className={`relative flex w-full flex-col items-center gap-2.5 rounded-2xl border-2 px-2 py-5 text-center transition duration-200 ease-out sm:gap-3 sm:py-6 ${
                  selected
                    ? "border-accent bg-accent-soft shadow-[0_10px_24px_-12px_oklch(49%_0.2_272/0.55)]"
                    : "border-line bg-surface enabled:hover:-translate-y-1 enabled:hover:border-accent/45 enabled:hover:shadow-[0_12px_28px_-14px_oklch(25%_0.03_264/0.35)]"
                } enabled:active:translate-y-0 enabled:active:scale-[0.96] disabled:cursor-default ${
                  locked && !selected ? "opacity-50" : ""
                }`}
              >
                {selected && (
                  <span className="absolute top-2 right-2 flex h-6 w-6 animate-pop items-center justify-center rounded-full bg-accent text-white sm:top-3 sm:right-3">
                    <Check />
                  </span>
                )}
                <Avatar label={label} size="md" />
                <span className="text-sm font-semibold text-ink sm:text-base">
                  {label}
                  {label === state.you && <span className="block text-xs font-normal text-muted">You</span>}
                </span>
              </button>
            </li>
          );
        })}
      </ul>

      <div className="mt-5 flex min-h-12 flex-col items-center justify-center gap-2 text-sm" aria-live="polite">
        {state.has_voted ? (
          <span className="flex animate-enter items-center gap-1.5 font-medium text-success">
            <Check className="h-4 w-4" />
            Vote recorded. Waiting for the others…
          </span>
        ) : pending ? (
          <span className="flex items-center gap-2 text-muted">
            <Spinner /> Sending vote…
          </span>
        ) : choice ? (
          <button
            type="button"
            onClick={confirm}
            className="animate-enter rounded-xl bg-accent px-6 py-3 font-semibold text-white shadow-[0_6px_16px_-6px_oklch(49%_0.2_272/0.6)] transition duration-150 hover:-translate-y-px hover:bg-accent-hover active:translate-y-0 active:scale-[0.97]"
          >
            Confirm vote for {choice}
          </button>
        ) : (
          <span className="text-muted">Choose one player, then confirm. Votes cannot be changed.</span>
        )}
        {shownError && !state.has_voted && <ErrorLine>{ERROR_TEXT[shownError] ?? shownError}</ErrorLine>}
      </div>
    </div>
  );
}
