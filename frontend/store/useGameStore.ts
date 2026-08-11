"use client";

import { create } from "zustand";
import { getAudio, nextTurn, startTurn } from "@/lib/api";
import type {
  ChatEntry,
  GameTurnCharacter,
  GameTurnMission,
  PlayerSetup,
  Skill,
} from "@/lib/types";

interface GameState {
  player: PlayerSetup | null;
  sessionId: string | null;
  entries: ChatEntry[];
  characters: GameTurnCharacter[];
  mission: GameTurnMission | null;
  isLoading: boolean;
  error: string | null;
  audioMuted: boolean;
  audioPaths: Record<string, string>;
  selectedCharacterId: string | null;
  coachSkill: Skill | null;

  setupPlayer: (p: PlayerSetup) => void;
  sendMessage: (text: string) => Promise<void>;
  selectCharacter: (id: string | null) => void;
  toggleAudio: () => void;
  openCoach: (skill: Skill | null) => void;
}

let entryId = 0;

export const useGameStore = create<GameState>((set, get) => ({
  player: null,
  sessionId: null,
  entries: [],
  characters: [],
  mission: null,
  isLoading: false,
  error: null,
  audioMuted: false,
  audioPaths: {},
  selectedCharacterId: null,
  coachSkill: null,

  setupPlayer: (p) => set({ player: p }),

  sendMessage: async (text) => {
    const { player, sessionId } = get();
    if (!player || !text.trim() || get().isLoading) return;

    set({ isLoading: true, error: null });
    const input = text.trim();
    try {
      const res = sessionId
        ? await nextTurn(sessionId, input)
        : await startTurn(player, input);

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

      set({
        sessionId: res.session_id,
        entries: [...get().entries, ...newEntries],
        characters: res.turn.characters,
        mission: res.turn.mission,
        coachSkill: res.turn.coach ?? null,
      });
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
