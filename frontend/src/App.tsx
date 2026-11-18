import type { ReactNode } from "react";
import Countdown from "./Countdown";
import { useSession, type ServerState } from "./useSession";
import Discussion from "./views/Discussion";
import Waiting from "./views/Waiting";

function Card({ children, wide = false }: { children: ReactNode; wide?: boolean }) {
  return (
    <main className="flex min-h-screen items-center justify-center bg-slate-50 p-4 text-slate-800 sm:p-6">
      <div className={`w-full ${wide ? "max-w-xl p-5 sm:p-6" : "max-w-md p-8"} rounded-2xl bg-white shadow-sm ring-1 ring-slate-200`}>
        {children}
      </div>
    </main>
  );
}

function Join({ onJoin, busy, error }: { onJoin: () => void; busy: boolean; error: string | null }) {
  return (
    <div className="text-center">
      <h1 className="text-2xl font-semibold">Group Decision Study</h1>
      <p className="mt-2 text-slate-500">
        You will chat with two other participants for two short rounds and vote for a Decision Maker.
      </p>
      {error && <p className="mt-4 text-sm text-rose-600">{error}</p>}
      <button
        onClick={onJoin}
        disabled={busy}
        className="mt-6 rounded-lg bg-indigo-600 px-5 py-2.5 font-medium text-white transition hover:bg-indigo-500 active:scale-95 disabled:opacity-60"
      >
        {busy ? "Joining…" : "Join"}
      </button>
    </div>
  );
}

function phaseTitle({ phase, round }: ServerState): string {
  switch (phase) {
    case "DISCUSSION":
      return `Round ${round} · Discussion`;
    case "VOTING":
      return `Round ${round} · Vote`;
    case "ROUND_RESULT":
      return `Round ${round} · Results`;
    default:
      return "Session complete";
  }
}

// Shell for the phases without their own view yet. Voting and results views fill it in slice 5.
function Started({ state }: { state: ServerState }) {
  return (
    <div className="text-center">
      <Countdown
        remainingMs={state.remaining_ms}
        serverNow={state.server_now}
        phaseKey={`${state.phase}-${state.round}`}
      />
      <h1 className="mt-4 text-2xl font-semibold">
        {phaseTitle(state)}
      </h1>
      <p className="mt-2 text-slate-500">
        You are <span className="font-semibold text-indigo-600">{state.you}</span>.
      </p>
      <ul className="mt-6 flex justify-center gap-2">
        {state.players.map((p) => (
          <li key={p} className="rounded-full bg-slate-100 px-3 py-1 text-sm">
            {p}
          </li>
        ))}
      </ul>
    </div>
  );
}

export default function App() {
  const { status, state, error, messages, join, sendChat } = useSession();

  if (status === "idle" || status === "joining" || (status === "error" && !state)) {
    return (
      <Card>
        <Join onJoin={join} busy={status === "joining"} error={error} />
      </Card>
    );
  }
  if (status === "closed") {
    return (
      <Card>
        <p className="text-center text-slate-500">Connection lost. Refresh the page to reconnect.</p>
      </Card>
    );
  }
  if (!state) {
    return (
      <Card>
        <p className="text-center text-slate-500">Connecting…</p>
      </Card>
    );
  }
  if (state.phase === "DISCUSSION") {
    return (
      <Card wide>
        <Discussion state={state} messages={messages} error={error} onSend={sendChat} />
      </Card>
    );
  }
  return <Card>{state.phase === "WAITING" ? <Waiting /> : <Started state={state} />}</Card>;
}
