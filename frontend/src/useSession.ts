import { useCallback, useEffect, useRef, useState } from "react";

export type Phase = "WAITING" | "DISCUSSION" | "VOTING" | "ROUND_RESULT" | "FINAL";

export interface ServerState {
  phase: Phase;
  round: number;
  phase_ends_at: number | null; // epoch ms
  server_now: number;
  remaining_ms: number | null;
  you: string | null;
  players: string[];
  has_voted: boolean;
}

export interface ChatMessage {
  id: number;
  from: string; // player label
  text: string;
  sent_at: number; // epoch ms
}

export const MAX_CHAT_CHARS = 500; // mirrors the server limit

export type Status = "idle" | "joining" | "connecting" | "connected" | "closed" | "error";

// sessionStorage, not localStorage: each tab is its own participant, and a refresh keeps the seat.
const TOKEN_KEY = "playerToken";

function readToken(): string | null {
  try {
    return sessionStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

function writeToken(token: string | null) {
  try {
    if (token) sessionStorage.setItem(TOKEN_KEY, token);
    else sessionStorage.removeItem(TOKEN_KEY);
  } catch {
    // storage unavailable: the session still works until the tab is refreshed
  }
}

export function useSession() {
  const [token, setToken] = useState<string | null>(readToken);
  const [status, setStatus] = useState<Status>(token ? "connecting" : "idle");
  const [state, setState] = useState<ServerState | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const socket = useRef<WebSocket | null>(null);

  useEffect(() => {
    if (!token) return;
    let disposed = false;
    setStatus("connecting");
    const scheme = location.protocol === "https:" ? "wss" : "ws";
    const ws = new WebSocket(`${scheme}://${location.host}/ws?token=${encodeURIComponent(token)}`);
    socket.current = ws;

    ws.onopen = () => !disposed && setStatus("connected");
    ws.onmessage = (event) => {
      if (disposed) return;
      const msg = JSON.parse(event.data);
      if (msg.type === "state") {
        setState(msg as ServerState);
        setError(null); // state arrives on phase changes; an old chat error no longer applies
      } else if (msg.type === "message") {
        const m: ChatMessage = { id: msg.id, from: msg.from, text: msg.text, sent_at: msg.sent_at };
        setMessages((list) => (list.some((x) => x.id === m.id) ? list : [...list, m]));
      } else if (msg.type === "error" && msg.reason === "unknown_token") {
        // e.g. the server restarted: the old seat is gone, so offer a fresh join.
        writeToken(null);
        setToken(null);
        setState(null);
        setStatus("error");
        setError("Your previous session is no longer available.");
      } else if (msg.type === "error") {
        setError(msg.reason);
      }
    };
    ws.onclose = () => {
      if (!disposed) setStatus((s) => (s === "error" ? s : "closed"));
    };
    return () => {
      disposed = true;
      if (socket.current === ws) socket.current = null;
      ws.close();
    };
  }, [token]);

  const join = useCallback(async () => {
    setStatus("joining");
    setError(null);
    try {
      const res = await fetch("/api/join", { method: "POST" });
      if (!res.ok) throw new Error(`Could not join (HTTP ${res.status}).`);
      const body: { token: string } = await res.json();
      writeToken(body.token);
      setToken(body.token);
    } catch (e) {
      setStatus("error");
      setError(e instanceof Error ? e.message : "Could not join.");
    }
  }, []);

  // The server validates and may answer with an error; the message only appears once it is broadcast.
  const sendChat = useCallback((text: string): boolean => {
    const ws = socket.current;
    if (!ws || ws.readyState !== WebSocket.OPEN) return false;
    setError(null);
    ws.send(JSON.stringify({ type: "chat", text }));
    return true;
  }, []);

  return { status, state, error, messages, join, sendChat };
}
