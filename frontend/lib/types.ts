export interface SkillFeedback {
  did_use_concept: boolean;
  concepts_used: string[];
  how_properly_used: string;
  player_intent: string;
  feedback_for_player: string;
}

export interface StatChange {
  delta: number;
  reason: string;
}

export interface GameTurnMessage {
  speaker: string; // character id or "PLAYER"
  text: string;
  audio_path?: string | null;
  inner_thought?: string | null;
  skill_feedback?: SkillFeedback | null;
  stat_deltas?: Record<string, number>;
}

export interface GameTurnCharacter {
  id: string;
  name: string;
  stats: Record<string, number>;
  stat_deltas: Record<string, number>;
  memory: string[];
  current_problem: string;
  solution: string;
  problem_solving_framework: string;
  relationship_state: string;
  pfp: string;
  present: boolean;
}

export interface WinCondition {
  character: string;
  stat: string;
  min?: number;
  max?: number;
}

export interface GameTurnMission {
  id: number;
  title: string;
  description: string;
  why_important: string;
  reason?: string;
  status: string;
  chain_progress: string;
  location: string;
  characters: string[];
  objective: string;
  reward: string;
  win_conditions: WinCondition[];
}

export interface GameTurnNarration {
  text: string;
  where: string;
  why_here: string;
}

export interface GameTurn {
  turn_id: number;
  narration: GameTurnNarration;
  messages: GameTurnMessage[];
  characters: GameTurnCharacter[];
  mission: GameTurnMission;
  scene_update: { characters_entered: string[]; characters_left: string[] };
  coach?: Skill | null;
}

export interface Skill {
  id: string;
  name: string;
  definition: string;
  psychology?: string;
  example_good: string[];
  example_bad: string[];
  feedback_template?: string;
}

export interface PlayerSetup {
  world_choice: string;
  character_name: string;
  goal: string;
  personality: string;
  background: string;
  starting_position: string;
  own_plan: string;
}

export interface Mission {
  id: number;
  title: string;
  description: string;
  why_important: string;
  reason?: string;
  status: string;
  location: string;
  characters: string[];
  objective: string;
  reward: string;
}

export interface CharacterStats {
  suspicion_towards_player: number;
  trust_towards_player: number;
  familiarity_towards_player: number;
  respect_towards_player: number;
  rapport_towards_player: number;
  disclosure_level: number;
  stress: number;
}

export interface BibleCharacter {
  id: string;
  canon_name: string;
  role: string;
  goal: string;
  stats: CharacterStats;
}

export interface WorldBible {
  world: { name: string; starting_location: string; atmosphere: string };
  autonomous_players: BibleCharacter[];
}

export type GameState =
  | "plan_elicitation"
  | "plan_revision"
  | "mission_lobby"
  | "live_mission"
  | "complete";

export interface MissionDebrief {
  message: string;
  location: string;
  who_is_around: string[];
}

export interface FeasibilityBlocker {
  step: string;
  why_blocked: string;
  how_to_unlock: string;
}

export interface FeasibleStep {
  step: string;
  target_character: string;
  objective: string;
  reason: string;
}

export interface FeasibilityReport {
  feasible: boolean;
  verdict: string;
  blockers: FeasibilityBlocker[];
  path: FeasibleStep[];
  reframe: string;
}

export interface TurnResponse {
  session_id: string;
  turn: GameTurn;
  game_state: GameState;
  mission_chain: Mission[];
  world?: WorldBible | null;
  debrief?: MissionDebrief | null;
  events?: string[];
  reconcile_shift?: string | null;
  feasibility?: FeasibilityReport | null;
}

export interface AudioResponse {
  character_id: string;
  audio_path: string | null;
  duration: number;
  available: boolean;
}

export interface CoachMessage {
  role: "player" | "coach";
  content: string;
}

// Normalized chat entry used by the UI
export type ChatEntry =
  | { kind: "narration"; id: string; text: string; where: string; why_here: string }
  | {
      kind: "message";
      id: string;
      speaker: string;
      text: string;
      inner_thought?: string | null;
      skill_feedback?: SkillFeedback | null;
      stat_deltas?: Record<string, number>;
      pending?: boolean;
    };

export interface CoachNotice {
  id: string;
  ok: boolean;
  concepts: string;
  text: string;
  player: string;
}
