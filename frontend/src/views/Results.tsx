import Countdown from "../Countdown";
import type { FinalResult, RoundResult, ServerState, Tallies } from "../useSession";

// Counts per label only: the server never sends who voted for whom.
function TallyBars({ tallies, players, you, highlight }: {
  tallies: Tallies;
  players: string[];
  you: string | null;
  highlight?: string;
}) {
  const max = Math.max(1, ...Object.values(tallies));
  return (
    <ul className="space-y-2">
      {players.map((label) => {
        const count = tallies[label] ?? 0;
        return (
          <li key={label}>
            <div className="flex justify-between text-sm">
              <span className={label === highlight ? "font-semibold text-indigo-600" : ""}>
                {label}
                {label === you && <span className="text-slate-400"> (you)</span>}
              </span>
              <span className="tabular-nums text-slate-500">
                {count} {count === 1 ? "vote" : "votes"}
              </span>
            </div>
            <div className="mt-1 h-2 overflow-hidden rounded-full bg-slate-100">
              <div
                className={`h-full rounded-full transition-[width] duration-500 motion-reduce:transition-none ${
                  label === highlight ? "bg-indigo-600" : "bg-slate-400"
                }`}
                style={{ width: `${(count / max) * 100}%` }}
              />
            </div>
          </li>
        );
      })}
    </ul>
  );
}

export function RoundTally({ state, result }: { state: ServerState; result: RoundResult | null }) {
  return (
    <div>
      <Countdown remainingMs={state.remaining_ms} serverNow={state.server_now} phaseKey={`${state.phase}-${state.round}`} />
      <h1 className="mt-3 text-lg font-semibold">Round {state.round} · Results</h1>
      <p className="mt-1 text-sm text-slate-500">
        A straw poll. Round {state.round + 1} starts shortly; its vote decides the Decision Maker.
      </p>
      <div className="mt-5">
        {result && result.round === state.round ? (
          <TallyBars tallies={result.tallies} players={state.players} you={state.you} />
        ) : (
          <p className="text-center text-sm text-slate-400">Counting votes…</p>
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
  if (!result) {
    return <p className="text-center text-slate-500">Counting votes…</p>;
  }
  const tieNote = TIE_BREAK_TEXT[result.tie_break];
  const rounds = Object.keys(result.tallies_by_round).sort();
  return (
    <div>
      <div className="animate-[fade-in_400ms_ease-out] text-center motion-reduce:animate-none">
        <p className="text-sm uppercase tracking-wide text-slate-400">Decision Maker</p>
        <h1 className="mt-1 text-3xl font-semibold text-indigo-600">{result.decision_maker}</h1>
        {result.decision_maker === state.you && <p className="mt-1 text-sm text-slate-500">That's you.</p>}
        {tieNote && <p className="mt-2 text-sm text-slate-500">{tieNote}</p>}
      </div>
      <div className="mt-6 space-y-5">
        {rounds.map((r) => (
          <section key={r}>
            <h2 className="mb-2 text-sm font-medium text-slate-600">Round {r}</h2>
            <TallyBars
              tallies={result.tallies_by_round[r]}
              players={state.players}
              you={state.you}
              highlight={r === rounds[rounds.length - 1] ? result.decision_maker : undefined}
            />
          </section>
        ))}
      </div>
      <p className="mt-6 text-center text-sm text-slate-400">The session is complete. Thank you for taking part.</p>
    </div>
  );
}
