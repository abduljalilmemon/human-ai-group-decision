import type { ReactNode } from "react";
import { useSession } from "./useSession";
import Discussion from "./views/Discussion";
import { FinalResults, RoundTally } from "./views/Results";
import Voting from "./views/Voting";
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

export default function App() {
  const { status, state, error, messages, roundResult, finalResult, join, sendChat, sendVote } = useSession();

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
  switch (state.phase) {
    case "WAITING":
      return (
        <Card>
          <Waiting />
        </Card>
      );
    case "DISCUSSION":
      return (
        <Card wide>
          <Discussion state={state} messages={messages} error={error} onSend={sendChat} />
        </Card>
      );
    case "VOTING":
      return (
        <Card wide>
          <Voting key={state.round} state={state} error={error} onVote={sendVote} />
        </Card>
      );
    case "ROUND_RESULT":
      return (
        <Card>
          <RoundTally state={state} result={roundResult} />
        </Card>
      );
    case "FINAL":
      return (
        <Card>
          <FinalResults state={state} result={finalResult} />
        </Card>
      );
  }
}
