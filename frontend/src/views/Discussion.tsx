import { useEffect, useRef, useState, type FormEvent } from "react";
import Countdown from "../Countdown";
import { MAX_CHAT_CHARS, type ChatMessage, type ServerState } from "../useSession";

const ERROR_TEXT: Record<string, string> = {
  chat_closed: "The discussion has ended.",
  empty_message: "Type a message first.",
  message_too_long: `Messages can be at most ${MAX_CHAT_CHARS} characters.`,
  invalid_message: "That message could not be sent.",
};

interface Props {
  state: ServerState;
  messages: ChatMessage[];
  error: string | null;
  onSend: (text: string) => boolean;
}

// Every message renders through the same markup and animation; only "you" vs "others" differs.
// Text is rendered as a React text node, never as HTML. No typing indicators, by design.
function Bubble({ message, mine }: { message: ChatMessage; mine: boolean }) {
  return (
    <li className={`flex animate-[fade-in_200ms_ease-out] flex-col motion-reduce:animate-none ${mine ? "items-end" : "items-start"}`}>
      <span className="mb-0.5 px-1 text-xs text-slate-400">{mine ? "You" : message.from}</span>
      <p
        className={`max-w-[85%] whitespace-pre-wrap break-words rounded-2xl px-3.5 py-2 text-sm ${
          mine ? "rounded-br-sm bg-indigo-600 text-white" : "rounded-bl-sm bg-slate-100 text-slate-800"
        }`}
      >
        {message.text}
      </p>
    </li>
  );
}

export default function Discussion({ state, messages, error, onSend }: Props) {
  const [draft, setDraft] = useState("");
  const listEnd = useRef<HTMLLIElement>(null);

  useEffect(() => {
    listEnd.current?.scrollIntoView({ block: "end", behavior: "smooth" });
  }, [messages.length]);

  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (!draft.trim()) return;
    if (onSend(draft)) setDraft("");
  };

  return (
    <div>
      <Countdown remainingMs={state.remaining_ms} serverNow={state.server_now} phaseKey={`${state.phase}-${state.round}`} />
      <div className="mt-3 flex items-baseline justify-between">
        <h1 className="text-lg font-semibold">Round {state.round} · Discussion</h1>
        <span className="text-sm text-slate-500">
          You are <span className="font-semibold text-indigo-600">{state.you}</span>
        </span>
      </div>
      <p className="mt-1 text-sm text-slate-500">Discuss who should be the Decision Maker.</p>

      <ul className="mt-4 flex h-80 flex-col gap-3 overflow-y-auto rounded-xl border border-slate-200 p-3" aria-live="polite">
        {messages.length === 0 && <li className="m-auto text-sm text-slate-400">No messages yet.</li>}
        {messages.map((m) => (
          <Bubble key={m.id} message={m} mine={m.from === state.you} />
        ))}
        <li ref={listEnd} aria-hidden />
      </ul>

      <form onSubmit={submit} className="mt-3 flex gap-2">
        <input
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          maxLength={MAX_CHAT_CHARS}
          placeholder="Type a message…"
          aria-label="Message"
          autoFocus
          className="min-w-0 flex-1 rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100"
        />
        <button
          type="submit"
          disabled={!draft.trim()}
          className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-indigo-500 active:scale-95 disabled:opacity-50"
        >
          Send
        </button>
      </form>
      {error && <p className="mt-2 text-sm text-rose-600">{ERROR_TEXT[error] ?? error}</p>}
    </div>
  );
}
