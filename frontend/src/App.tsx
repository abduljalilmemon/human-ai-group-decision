import type { ReactNode } from "react";
import { useSession, type ServerState } from "./useSession";
import Waiting from "./views/Waiting";

function Card({ children }: { children: ReactNode }) {
  return (
    <main className="flex min-h-screen items-center justify-center bg-slate-50 p-4 text-slate-800 sm:p-6">
      <div className="w-full max-w-md rounded-2xl bg-white p-8 shadow-sm ring-1 ring-slate-200">
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

// Placeholder until the session engine and discussion view arrive (slices 3 and 4).
function Started({ state }: { state: ServerState }) {
  return (
    <div className="text-center">
      <h1 className="text-2xl font-semibold">Session started</h1>
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
  const { status, state, error, join } = useSession();

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
  return <Card>{state.phase === "WAITING" ? <Waiting /> : <Started state={state} />}</Card>;
}
