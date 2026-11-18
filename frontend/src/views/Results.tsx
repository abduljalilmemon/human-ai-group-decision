import type { FinalResult, RoundResult, ServerState, Tallies } from "../useSession";
import { Avatar, PhaseHeader, Spinner } from "../ui";

// The suspense beat is motion only: all results are in the DOM (and read by screen readers) at once;
// the visual reveal waits at most BEAT_MS, and reduced motion removes the wait entirely.
const BEAT_MS = 600;

// Counts per label only: the server never sends who voted for whom.
function TallyBars({ tallies, players, you, highlight, delayMs = 0 }: {
  tallies: Tallies;
  players: string[];
  you: string | null;
  highlight?: string;
  delayMs?: number;
}) {
  const max = Math.max(1, ...Object.values(tallies));
  return (
    <ul className="space-y-3.5">
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
              <div className="mt-1.5 h-2.5 overflow-hidden rounded-full bg-track">
                <div
                  className={`h-full origin-left animate-grow rounded-full ${win ? "bg-accent" : "bg-muted/55"}`}
                  style={{ width: `${(count / max) * 100}%`, animationDelay: `${delayMs + i * 90}ms` }}
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
    <p className="flex items-center justify-center gap-2 py-8 text-sm text-muted">
      <Spinner /> Counting votes…
    </p>
  );
}

export function RoundTally({ state, result }: { state: ServerState; result: RoundResult | null }) {
  return (
    <div>
      <PhaseHeader
        state={state}
        title={`Round ${state.round} results`}
        hint={`A straw poll. Round ${state.round + 1} starts shortly; its vote decides the Decision Maker.`}
      />
      <div className="mt-7">
        {result && result.round === state.round ? (
          <TallyBars tallies={result.tallies} players={state.players} you={state.you} delayMs={BEAT_MS / 2} />
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
  const at = (ms: number) => ({ animationDelay: `${BEAT_MS + ms}ms` });
  return (
    <div>
      {/* The counting line and the winner share one grid cell: one fades out as the other reveals. */}
      <div className="grid place-items-center text-center *:[grid-area:1/1]">
        <p aria-hidden className="flex animate-fade-out items-center gap-2 self-start pt-8 text-sm text-muted" style={{ animationDelay: `${BEAT_MS}ms` }}>
          <Spinner /> Counting votes…
        </p>
        <div className="flex flex-col items-center">
          <span className="animate-reveal rounded-full" style={at(0)}>
            <span className="block animate-halo rounded-full" style={at(350)}>
              <Avatar label={result.decision_maker} size="xl" />
            </span>
          </span>
          <h1 className="mt-6 animate-enter text-3xl font-semibold tracking-tight text-balance" style={at(250)}>
            {result.decision_maker} is the Decision Maker
          </h1>
          {result.decision_maker === state.you && (
            <p className="mt-2 animate-enter text-sm font-medium text-accent" style={at(400)}>
              That's you.
            </p>
          )}
          {tieNote && (
            <p className="mt-2 animate-enter text-sm text-muted" style={at(400)}>
              {tieNote}
            </p>
          )}
        </div>
      </div>
      <div className="mt-9 animate-enter space-y-6 border-t border-line pt-6" style={at(500)}>
        {rounds.map((r) => (
          <section key={r}>
            <h2 className="mb-3 text-sm font-semibold text-ink">Round {r}</h2>
            <TallyBars
              tallies={result.tallies_by_round[r]}
              players={state.players}
              you={state.you}
              highlight={r === rounds[rounds.length - 1] ? result.decision_maker : undefined}
              delayMs={BEAT_MS + 600}
            />
          </section>
        ))}
      </div>
      <p className="mt-8 text-center text-sm text-muted">The session is complete. Thank you for taking part.</p>
    </div>
  );
}
