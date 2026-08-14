export interface SkillFeedback {
  did_use_concept: boolean;
  concepts_used: string[];
  how_properly_used: string;
  player_intent: string;
  new_plan_proposed_by_player: boolean;
  did_pass_this_turn: boolean;
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
  pfp: string;
  present: boolean;
}

export interface GameTurnMission {
  id: number;
  title: string;
  description: string;
  why_important: string;
  status: string;
  chain_progress: string;
  location: string;
  characters: string[];
  objective: string;
  reward: string;
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
  status: string;
  location: string;
  characters: string[];
  objective: string;
  reward: string;
}

export interface CharacterStats {
  suspicion_towards_player: number;
  trust_towards_player: number;
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
  | "mission_lobby"
  | "live_mission"
  | "complete";

export interface TurnResponse {
  session_id: string;
  turn: GameTurn;
  game_state: GameState;
  mission_chain: Mission[];
  world?: WorldBible | null;
}

export interface AudioResponse {
  character_id: string;
  audio_path: string | null;
  duration: number;
  available: boolean;
}

// Normalized chat entry used by the UI
export type ChatEntry =
  | { kind: "narration"; id: string; text: string; where: string; why_here: string }
  | { kind: "message"; id: string; speaker: string; text: string; inner_thought?: string | null; skill_feedback?: SkillFeedback | null };
