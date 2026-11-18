import Countdown from "../Countdown";
import type { FinalResult, RoundResult, ServerState, Tallies } from "../useSession";
import { Avatar, Spinner } from "../ui";

// Counts per label only: the server never sends who voted for whom.
function TallyBars({ tallies, players, you, highlight }: {
  tallies: Tallies;
  players: string[];
  you: string | null;
  highlight?: string;
}) {
  const max = Math.max(1, ...Object.values(tallies));
  return (
    <ul className="space-y-3">
      {players.map((label, i) => {
        const count = tallies[label] ?? 0;
        const win = label === highlight;
        return (
          <li key={label} className="flex items-center gap-3">
            <Avatar label={label} />
            <div className="min-w-0 flex-1">
              <div className="flex justify-between text-sm">
                <span className={win ? "font-semibold text-ink" : "text-ink"}>
                  {label}
                  {label === you && <span className="text-muted"> (you)</span>}
                </span>
                <span className="text-muted tabular-nums">
                  {count} {count === 1 ? "vote" : "votes"}
                </span>
              </div>
              <div className="mt-1.5 h-2 overflow-hidden rounded-full bg-track">
                <div
                  className={`h-full origin-left animate-grow rounded-full ${win ? "bg-accent" : "bg-muted/55"}`}
                  style={{ width: `${(count / max) * 100}%`, animationDelay: `${i * 80}ms` }}
                />
              </div>
            </div>
          </li>
        );
      })}
    </ul>
  );
}

function Counting() {
  return (
    <p className="flex items-center justify-center gap-2 py-6 text-sm text-muted">
      <Spinner /> Counting votes…
    </p>
  );
}

export function RoundTally({ state, result }: { state: ServerState; result: RoundResult | null }) {
  return (
    <div>
      <Countdown remainingMs={state.remaining_ms} serverNow={state.server_now} phaseKey={`${state.phase}-${state.round}`} />
      <h1 className="mt-4 text-xl font-semibold text-balance">Round {state.round} results</h1>
      <p className="mt-1.5 text-sm text-muted">
        A straw poll. Round {state.round + 1} starts shortly; its vote decides the Decision Maker.
      </p>
      <div className="mt-6">
        {result && result.round === state.round ? (
          <TallyBars tallies={result.tallies} players={state.players} you={state.you} />
        ) : (
          <Counting />
        )}
      </div>
    </div>
  );
}

const TIE_BREAK_TEXT: Record<FinalResult["tie_break"], string | null> = {
  none: null,
  round1: "Round 2 was tied; decided by Round 1 votes.",
  random: "The vote was tied; decided by a random draw.",
};

export function FinalResults({ state, result }: { state: ServerState; result: FinalResult | null }) {
  if (!result) return <Counting />;
  const tieNote = TIE_BREAK_TEXT[result.tie_break];
  const rounds = Object.keys(result.tallies_by_round).sort();
  return (
    <div>
      <div className="flex flex-col items-center text-center">
        <span className="animate-reveal rounded-full">
          <span className="block animate-halo rounded-full">
            <Avatar label={result.decision_maker} size="lg" />
          </span>
        </span>
        <h1 className="mt-5 animate-enter text-2xl font-semibold text-balance [animation-delay:250ms]">
          {result.decision_maker} is the Decision Maker
        </h1>
        {result.decision_maker === state.you && (
          <p className="mt-1.5 animate-enter text-sm font-medium text-accent [animation-delay:350ms]">That's you.</p>
        )}
        {tieNote && <p className="mt-2 animate-enter text-sm text-muted [animation-delay:350ms]">{tieNote}</p>}
      </div>
      <div className="mt-8 animate-fade space-y-6 border-t border-line pt-6 [animation-delay:500ms]">
        {rounds.map((r) => (
          <section key={r}>
            <h2 className="mb-3 text-sm font-semibold text-ink">Round {r}</h2>
            <TallyBars
              tallies={result.tallies_by_round[r]}
              players={state.players}
              you={state.you}
              highlight={r === rounds[rounds.length - 1] ? result.decision_maker : undefined}
            />
          </section>
        ))}
      </div>
      <p className="mt-8 text-center text-sm text-muted">The session is complete. Thank you for taking part.</p>
    </div>
  );
}
