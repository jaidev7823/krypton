import type { AudioResponse, PlayerSetup, TurnResponse } from "./types";

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

export function startGame(playerSetup: PlayerSetup): Promise<TurnResponse> {
  return post<TurnResponse>("/api/turn", {
    player_setup: playerSetup,
    action: "submit_plan",
    plan_text: playerSetup.own_plan,
    new_player_input: "",
  });
}

export function enterMission(sessionId: string): Promise<TurnResponse> {
  return post<TurnResponse>("/api/turn", {
    session_id: sessionId,
    action: "enter_mission",
    new_player_input: "",
  });
}

export function revisePlan(sessionId: string, planText: string): Promise<TurnResponse> {
  return post<TurnResponse>("/api/turn", {
    session_id: sessionId,
    action: "submit_plan",
    plan_text: planText,
    new_player_input: "",
  });
}

export function nextTurn(sessionId: string, input: string): Promise<TurnResponse> {
  return post<TurnResponse>("/api/turn", { session_id: sessionId, new_player_input: input });
}

export function getAudio(characterId: string, dialogue: string): Promise<AudioResponse> {
  return post<AudioResponse>("/api/audio", { character_id: characterId, dialogue });
}
