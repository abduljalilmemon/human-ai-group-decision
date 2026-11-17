import { useCallback, useEffect, useState } from "react";

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

  useEffect(() => {
    if (!token) return;
    let disposed = false;
    setStatus("connecting");
    const scheme = location.protocol === "https:" ? "wss" : "ws";
    const ws = new WebSocket(`${scheme}://${location.host}/ws?token=${encodeURIComponent(token)}`);

    ws.onopen = () => !disposed && setStatus("connected");
    ws.onmessage = (event) => {
      if (disposed) return;
      const msg = JSON.parse(event.data);
      if (msg.type === "state") {
        setState(msg as ServerState);
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

  return { status, state, error, join };
}
