import type { AudioResponse, CoachMessage, PlayerSetup, TurnResponse } from "./types";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(`${path} failed (${res.status}): ${detail.slice(0, 300)}`);
  }
  return res.json() as Promise<T>;
}

export function startGame(playerSetup: PlayerSetup, planText: string): Promise<TurnResponse> {
  return post<TurnResponse>("/api/turn", {
    player_setup: playerSetup,
    action: "setup",
    plan_text: planText,
    new_player_input: "",
  });
}

export function declareAction(sessionId: string, actionText: string): Promise<TurnResponse> {
  return post<TurnResponse>("/api/turn", {
    session_id: sessionId,
    action: "declare_action",
    new_player_input: actionText,
  });
}

export function sendSceneMessage(sessionId: string, input: string): Promise<TurnResponse> {
  return post<TurnResponse>("/api/turn", {
    session_id: sessionId,
    action: "scene",
    new_player_input: input,
  });
}

export function getAudio(characterId: string, dialogue: string): Promise<AudioResponse> {
  return post<AudioResponse>("/api/audio", { character_id: characterId, dialogue });
}

export function askCoach(
  sessionId: string,
  message: string,
  history: CoachMessage[],
): Promise<{ reply: string }> {
  return post<{ reply: string }>("/api/coach", {
    session_id: sessionId,
    message,
    history: history.map((h) => ({ role: h.role, content: h.content })),
  });
}
