"use client";

import { create } from "zustand";
import { askCoach, declareAction, getAudio, sendSceneMessage, startGame } from "@/lib/api";
import type {
  ActionFeasibility,
  ChatEntry,
  CoachMessage,
  CoachNotice,
  GameState,
  GameTurnCharacter,
  Mission,
  MissionDebrief,
  PlayerSetup,
  SceneExitHook,
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
  world: WorldBible | null;
  events: string[];
  notices: CoachNotice[];
  feasibility: ActionFeasibility | null;
  sceneHooks: SceneExitHook[];
  strategicPlan: string;
  mission: Mission | null;
  debrief: MissionDebrief | null;
  isLoading: boolean;
  error: string | null;
  audioMuted: boolean;
  audioPaths: Record<string, string>;
  selectedCharacterId: string | null;
  coachSkill: Skill | null;
  coachOpen: boolean;
  coachMessages: CoachMessage[];
  coachLoading: boolean;

  setupPlayer: (p: PlayerSetup, planText: string) => Promise<void>;
  declareAction: (actionText: string) => Promise<void>;
  sendMessage: (text: string) => Promise<void>;
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
  const newEntries: ChatEntry[] = [...playerMsgs, ...charMsgs];
  if (narrationEntry.text) {
    newEntries.splice(playerMsgs.length, 0, narrationEntry);
  }

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
    const base = s.entries.filter((e) => !(e.kind === "message" && e.pending));
    let entries = base;
    if (res.game_state === "setup") {
      entries = [];
    } else if (res.game_state === "world") {
      // World state: keep live scene chat history, no narration (WorldScreen handles it)
      entries = base;
    } else if (res.game_state === "live_scene" && res.turn.messages.length > 0) {
      entries = [...base, ...newEntries];
    }
    return {
      sessionId: res.session_id,
      gameState: res.game_state,
      world: res.world ?? s.world,
      entries,
      characters: res.turn.characters,
      events: res.events && res.events.length > 0 ? res.events : s.events,
      feasibility: res.feasibility ?? null,
      sceneHooks: res.scene_hooks ?? [],
      strategicPlan: res.strategic_plan ?? s.strategicPlan,
      mission: res.mission ?? s.mission,
      debrief: res.debrief ?? (res.game_state === "world" ? null : s.debrief),
      notices: newNotices.length > 0 ? [...newNotices, ...s.notices].slice(0, 30) : s.notices,
      coachSkill: res.turn.coach ?? null,
      isLoading: false,
    };
  });
}

export const useGameStore = create<GameStateStore>((set, get) => ({
  player: null,
  sessionId: null,
  gameState: "setup",
  entries: [],
  characters: [],
  world: null,
  events: [],
  notices: [],
  feasibility: null,
  sceneHooks: [],
  strategicPlan: "",
  mission: null,
  debrief: null,
  isLoading: false,
  error: null,
  audioMuted: false,
  audioPaths: {},
  selectedCharacterId: null,
  coachSkill: null,
  coachOpen: false,
  coachMessages: [],
  coachLoading: false,

  setupPlayer: async (p, planText) => {
    set({ isLoading: true, error: null, player: p, strategicPlan: planText });
    try {
      const res = await startGame(p, planText);
      applyTurn(set, res);
    } catch (e) {
      set({ error: e instanceof Error ? e.message : String(e) });
    } finally {
      set({ isLoading: false });
    }
  },

  declareAction: async (actionText) => {
    const { sessionId } = get();
    if (!sessionId || !actionText.trim() || get().isLoading) return;
    set({ isLoading: true, error: null });
    try {
      const res = await declareAction(sessionId, actionText.trim());
      applyTurn(set, res);
    } catch (e) {
      set({ error: e instanceof Error ? e.message : String(e) });
    } finally {
      set({ isLoading: false });
    }
  },

  sendMessage: async (text) => {
    const { sessionId } = get();
    if (!sessionId || !text.trim() || get().isLoading) return;
    set({ isLoading: true, error: null });
    const input = text.trim();

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

    try {
      const res = await sendSceneMessage(sessionId, input);
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
