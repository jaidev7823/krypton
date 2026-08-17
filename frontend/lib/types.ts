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
  speaker: string;
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

export interface GameTurnNarration {
  text: string;
  where: string;
  why_here: string;
}

export interface GameTurnScene {
  title: string;
  location?: string;
  characters?: string[];
  strategic_plan?: string;
  scene_hooks?: SceneExitHook[];
}

export interface GameTurn {
  turn_id: number;
  narration: GameTurnNarration;
  messages: GameTurnMessage[];
  characters: GameTurnCharacter[];
  scene?: GameTurnScene;
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
  skill_choice?: string;
}

export interface ActionFeasibility {
  feasible: boolean;
  reason: string;
  suggestions?: string[];
}

export interface SceneExitHook {
  character: string;
  suggestion: string;
  context?: string;
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

export type GameState = "setup" | "world" | "live_scene";

export interface MissionObjective {
  character: string;
  stat: string;
  min?: number;
  max?: number;
}

export interface Mission {
  id: number;
  title: string;
  description: string;
  characters: string[];
  location: string;
  objective: string;
  reward: string;
  win_conditions: MissionObjective[];
  fail_conditions: MissionObjective[];
}

export interface MissionDebrief {
  outcome: "won" | "lost" | "abandoned";
  message: string;
  location: string;
  who_is_around: string[];
}

export interface TurnResponse {
  session_id: string;
  turn: GameTurn;
  game_state: GameState;
  world?: WorldBible | null;
  events?: string[];
  feasibility?: ActionFeasibility | null;
  scene_hooks?: SceneExitHook[];
  strategic_plan?: string;
  mission?: Mission | null;
  debrief?: MissionDebrief | null;
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
