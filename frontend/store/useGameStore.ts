"use client";

import { create } from "zustand";
import { askCoach, enterMission, getAudio, nextTurn, openRevision, revisePlan, startGame } from "@/lib/api";
import type {
  ChatEntry,
  CoachMessage,
  CoachNotice,
  FeasibilityReport,
  GameState,
  GameTurnCharacter,
  GameTurnMission,
  Mission,
  MissionDebrief,
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
  debrief: MissionDebrief | null;
  events: string[];
  shiftNotice: string | null;
  notices: CoachNotice[];
  feasibility: FeasibilityReport | null;
  isLoading: boolean;
  error: string | null;
  audioMuted: boolean;
  audioPaths: Record<string, string>;
  selectedCharacterId: string | null;
  coachSkill: Skill | null;
  coachOpen: boolean;
  coachMessages: CoachMessage[];
  coachLoading: boolean;

  setupPlayer: (p: PlayerSetup) => Promise<void>;
  startMission: () => Promise<void>;
  sendMessage: (text: string) => Promise<void>;
  submitNewPlan: (planText: string) => Promise<void>;
  requestRevision: () => Promise<void>;
  selectCharacter: (id: string | null) => void;
  toggleAudio: () => void;
  openCoach: (skill: Skill | null) => void;
  toggleCoach: () => void;
  askCoach: (text: string) => Promise<void>;
}

let entryId = 0;
let noticeId = 0;

function applyTurn(set: (fn: (s: GameStateStore) => Partial<GameStateStore>) => void, res: TurnResponse) {
  const narration = res.turn.narration;
  // Narration is placed BELOW the player's own message, so the player reads
  // what they just said first, then the world's reaction.
  const playerMsgs: Extract<ChatEntry, { kind: "message" }>[] = [];
  const charMsgs: Extract<ChatEntry, { kind: "message" }>[] = [];
  for (const m of res.turn.messages) {
    const entry: ChatEntry = {
      kind: "message",
      id: `m-${res.turn.turn_id}-${entryId++}`,
      speaker: m.speaker,
      text: m.text,
      inner_thought: m.inner_thought,
      skill_feedback: m.skill_feedback,
      stat_deltas: m.stat_deltas,
    };
    if (m.speaker === "PLAYER") playerMsgs.push(entry);
    else charMsgs.push(entry);
  }
  const narrationEntry: ChatEntry = {
    kind: "narration",
    id: `n-${res.turn.turn_id}`,
    text: narration.text,
    where: narration.where,
    why_here: narration.why_here,
  };
  const newEntries: ChatEntry[] = [...playerMsgs, narrationEntry, ...charMsgs];

  const newNotices: CoachNotice[] = [];
  for (const pm of playerMsgs) {
    if (pm.skill_feedback) {
      newNotices.push({
        id: `coach-${noticeId++}`,
        ok: pm.skill_feedback.did_use_concept,
        concepts: (pm.skill_feedback.concepts_used || []).join(" + ") || "NO SKILL",
        text: pm.skill_feedback.feedback_for_player,
        player: pm.text,
      });
    }
  }

  set((s) => {
    // Drop the optimistic pending player entry - the server echoes the same
    // words back in res.turn.messages.
    const base = s.entries.filter((e) => !(e.kind === "message" && e.pending));
    // Append entries only for turns that carry real game content. Pure lobby /
    // elicitation responses are screens, not chat. A won live turn still
    // returns mission_lobby but carries the debrief exchange -> append it.
    const hasContent =
      res.game_state === "live_mission" ||
      res.game_state === "complete" ||
      res.turn.messages.length > 0;
    let entries = base;
    if (res.game_state === "plan_elicitation") {
      entries = [];
    } else if (hasContent) {
      entries = [...base, ...newEntries];
    }
    return {
      sessionId: res.session_id,
      gameState: res.game_state,
      missionChain: res.mission_chain ?? s.missionChain,
      world: res.world ?? s.world,
      entries,
      characters: res.turn.characters,
      mission: res.turn.mission,
      debrief: res.debrief ?? null,
      events: res.events && res.events.length > 0 ? res.events : s.events,
      shiftNotice: res.reconcile_shift ?? null,
      feasibility: res.feasibility ?? null,
      notices: newNotices.length > 0 ? [...newNotices, ...s.notices].slice(0, 30) : s.notices,
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
  debrief: null,
  events: [],
  shiftNotice: null,
  notices: [],
  feasibility: null,
  isLoading: false,
  error: null,
  audioMuted: false,
  audioPaths: {},
  selectedCharacterId: null,
  coachSkill: null,
  coachOpen: false,
  coachMessages: [],
  coachLoading: false,

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

    // Optimistic: the player's own message shows immediately instead of
    // waiting for the whole world to react. The server echoes it back and the
    // pending copy is dropped in applyTurn.
    if (sessionId) {
      set((s) => ({
        entries: [
          ...s.entries,
          {
            kind: "message",
            id: `pending-${entryId++}`,
            speaker: "PLAYER",
            text: input,
            pending: true,
          } satisfies ChatEntry,
        ],
      }));
    }

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

  submitNewPlan: async (planText) => {
    const { sessionId } = get();
    if (!sessionId || !planText.trim() || get().isLoading) return;
    set({ isLoading: true, error: null });
    try {
      const res = await revisePlan(sessionId, planText.trim());
      applyTurn(set, res);
    } catch (e) {
      set({ error: e instanceof Error ? e.message : String(e) });
    } finally {
      set({ isLoading: false });
    }
  },

  requestRevision: async () => {
    const { sessionId } = get();
    if (!sessionId || get().isLoading) return;
    set({ isLoading: true, error: null });
    try {
      const res = await openRevision(sessionId);
      applyTurn(set, res);
    } catch (e) {
      set({ error: e instanceof Error ? e.message : String(e) });
    } finally {
      set({ isLoading: false });
    }
  },

  selectCharacter: (id) => set({ selectedCharacterId: id }),  toggleAudio: () => set({ audioMuted: !get().audioMuted }),

  openCoach: (skill) => set({ coachSkill: skill }),

  toggleCoach: () => set({ coachOpen: !get().coachOpen }),

  askCoach: async (text) => {
    const { sessionId, coachMessages } = get();
    const input = text.trim();
    if (!sessionId || !input || get().coachLoading) return;
    const history = coachMessages;
    set({
      coachLoading: true,
      coachMessages: [...coachMessages, { role: "player", content: input }],
    });
    try {
      const res = await askCoach(sessionId, input, history);
      set({ coachMessages: [...get().coachMessages, { role: "coach", content: res.reply }] });
    } catch {
      set({
        coachMessages: [
          ...get().coachMessages,
          { role: "coach", content: "The coach is unavailable right now." },
        ],
      });
    } finally {
      set({ coachLoading: false });
    }
  },
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
