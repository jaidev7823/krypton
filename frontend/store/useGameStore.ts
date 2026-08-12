"use client";

import { create } from "zustand";
import { enterMission, getAudio, nextTurn, startGame, submitPlan } from "@/lib/api";
import type {
  ChatEntry,
  GameState,
  GameTurnCharacter,
  GameTurnMission,
  Mission,
  PlayerSetup,
  Skill,
  TurnResponse,
  WorldBible,
} from "@/lib/types";

interface GameStateStore {
  player: PlayerSetup | null;
  sessionId: string | null;
  gameState: GameState;
  entries: ChatEntry[];
  characters: GameTurnCharacter[];
  mission: GameTurnMission | null;
  missionChain: Mission[];
  world: WorldBible | null;
  isLoading: boolean;
  error: string | null;
  audioMuted: boolean;
  audioPaths: Record<string, string>;
  selectedCharacterId: string | null;
  coachSkill: Skill | null;

  setupPlayer: (p: PlayerSetup) => Promise<void>;
  submitPlayerPlan: (planText: string) => Promise<void>;
  startMission: () => Promise<void>;
  sendMessage: (text: string) => Promise<void>;
  selectCharacter: (id: string | null) => void;
  toggleAudio: () => void;
  openCoach: (skill: Skill | null) => void;
}

let entryId = 0;

function applyTurn(set: (fn: (s: GameStateStore) => Partial<GameStateStore>) => void, res: TurnResponse) {
  const narration = res.turn.narration;
  const newEntries: ChatEntry[] = [
    {
      kind: "narration",
      id: `n-${res.turn.turn_id}`,
      text: narration.text,
      where: narration.where,
      why_here: narration.why_here,
    },
    ...res.turn.messages.map<ChatEntry>((m) => ({
      kind: "message",
      id: `m-${res.turn.turn_id}-${entryId++}`,
      speaker: m.speaker,
      text: m.text,
      inner_thought: m.inner_thought,
      skill_feedback: m.skill_feedback,
    })),
  ];

  set((s) => {
    // Append entries only for turns that carry real game content. Pure lobby /
    // elicitation responses are screens, not chat. A won live turn still
    // returns mission_lobby but carries the debrief exchange -> append it.
    const hasContent =
      res.game_state === "live_mission" ||
      res.game_state === "complete" ||
      res.turn.messages.length > 0;
    let entries = s.entries;
    if (res.game_state === "plan_elicitation") {
      entries = [];
    } else if (hasContent) {
      entries = [...s.entries, ...newEntries];
    }
    return {
      sessionId: res.session_id,
      gameState: res.game_state,
      missionChain: res.mission_chain ?? s.missionChain,
      world: res.world ?? s.world,
      entries,
      characters: res.turn.characters,
      mission: res.turn.mission,
      coachSkill: res.turn.coach ?? null,
    };
  });
}

export const useGameStore = create<GameStateStore>((set, get) => ({
  player: null,
  sessionId: null,
  gameState: "plan_elicitation",
  entries: [],
  characters: [],
  mission: null,
  missionChain: [],
  world: null,
  isLoading: false,
  error: null,
  audioMuted: false,
  audioPaths: {},
  selectedCharacterId: null,
  coachSkill: null,

  setupPlayer: async (p) => {
    set({ isLoading: true, error: null, player: p });
    try {
      const res = await startGame(p);
      applyTurn(set, res);
    } catch (e) {
      set({ error: e instanceof Error ? e.message : String(e) });
    } finally {
      set({ isLoading: false });
    }
  },

  submitPlayerPlan: async (planText) => {
    const { sessionId } = get();
    if (!sessionId || !planText.trim() || get().isLoading) return;
    set({ isLoading: true, error: null });
    try {
      const res = await submitPlan(sessionId, planText.trim());
      applyTurn(set, res);
    } catch (e) {
      set({ error: e instanceof Error ? e.message : String(e) });
    } finally {
      set({ isLoading: false });
    }
  },

  startMission: async () => {
    const { sessionId } = get();
    if (!sessionId || get().isLoading) return;
    set({ isLoading: true, error: null });
    try {
      const res = await enterMission(sessionId);
      applyTurn(set, res);
    } catch (e) {
      set({ error: e instanceof Error ? e.message : String(e) });
    } finally {
      set({ isLoading: false });
    }
  },

  sendMessage: async (text) => {
    const { player, sessionId } = get();
    if (!player || !text.trim() || get().isLoading) return;

    set({ isLoading: true, error: null });
    const input = text.trim();
    try {
      const res = sessionId
        ? await nextTurn(sessionId, input)
        : await startGame(player);
      applyTurn(set, res);
    } catch (e) {
      set({ error: e instanceof Error ? e.message : String(e) });
    } finally {
      set({ isLoading: false });
    }
  },

  selectCharacter: (id) => set({ selectedCharacterId: id }),

  toggleAudio: () => set({ audioMuted: !get().audioMuted }),

  openCoach: (skill) => set({ coachSkill: skill }),
}));

// Audio helper shared by CharacterMessage
export async function ensureAudioPath(
  audioPaths: Record<string, string>,
  speaker: string,
  text: string,
): Promise<string | null> {
  const key = `${speaker}:${text.slice(0, 80)}`;
  if (audioPaths[key]) return audioPaths[key];
  try {
    const res = await getAudio(speaker, text);
    if (res.audio_path) {
      useGameStore.setState({
        audioPaths: { ...useGameStore.getState().audioPaths, [key]: res.audio_path },
      });
      return res.audio_path;
    }
  } catch {
    /* TTS unavailable - skip playback */
  }
  return null;
}
