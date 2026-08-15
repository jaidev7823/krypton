"""Pydantic models for every contract in the living world simulator.

Piece 1 (WorldBible), Piece 2 (SkillBible + PlayerSetup) are loaded/sent as
data. Piece 3 contracts (R1/R2/R3) are what the LLM produces each turn.
Piece 5 (GameTurn) is the single merged JSON the frontend consumes.

All models are permissive (extra="allow") so new worlds / skill books never
break the contract.
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


class PermissiveModel(BaseModel):
    """Base model that tolerates unknown fields from LLM output."""
    model_config = ConfigDict(extra="allow")


# ---------------------------------------------------------------------------
# Piece 1: World & Character bible
# ---------------------------------------------------------------------------

class StructuredDialogueStyle(PermissiveModel):
    vocab: list[str] = Field(default_factory=list)
    speech_pattern: str = ""
    never_says: list[str] = Field(default_factory=list)
    emotional_range: str = ""


class StructuredProblemSolvingFramework(PermissiveModel):
    type: str = ""
    how_he_plans: str = ""
    weakness: str = ""


class Knowledge(PermissiveModel):
    knows: list[str] = Field(default_factory=list)
    does_not_know: list[str] = Field(default_factory=list)
    suspects: list[str] = Field(default_factory=list)


class CharacterStats(PermissiveModel):
    trust_towards_player: int = 0
    familiarity_towards_player: int = 0
    respect_towards_player: int = 0
    suspicion_towards_player: int = 0
    rapport_towards_player: int = 0
    disclosure_level: int = 0
    stress: int = 0
    voice_id: str = ""
    sample_audio_path: str = ""


class AutonomousPlayer(PermissiveModel):
    id: str
    type: str = "autonomous_player"
    canon_name: str = ""
    role: str = ""
    dialogue_style: str | StructuredDialogueStyle = ""
    problem_solving_framework: str | StructuredProblemSolvingFramework = ""
    knowledge: Knowledge = Field(default_factory=Knowledge)
    goal: str = ""
    motivation: str = ""
    current_problem: str = ""
    solution: str = ""
    relationship_dynamics: str = ""
    stat_ladders: dict[str, Any] = Field(default_factory=dict)
    memory_about_player: list[str] = Field(default_factory=list)
    stats: CharacterStats = Field(default_factory=CharacterStats)


class WorldInfo(PermissiveModel):
    name: str
    canon_summary: str = ""
    timeline: str = ""
    starting_location: str = ""
    atmosphere: str = ""
    rules: list[str] = Field(default_factory=list)


class WorldBible(PermissiveModel):
    world: WorldInfo
    autonomous_players: list[AutonomousPlayer] = Field(default_factory=list)
    developer_context: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Piece 2: Skill book + Player setup
# ---------------------------------------------------------------------------

class SkillDetect(PermissiveModel):
    rule: str = ""
    required_prefix: list[str] = Field(default_factory=list)
    emotion_list: list[str] = Field(default_factory=list)
    keywords_check: str = ""
    forbidden_prefix: list[str] = Field(default_factory=list)


class SkillEffect(PermissiveModel):
    if_correct: dict[str, Any] = Field(default_factory=dict)
    if_wrong: dict[str, Any] = Field(default_factory=dict)
    feedback_template: str = ""


class Skill(PermissiveModel):
    id: str
    name: str = ""
    definition: str = ""
    psychology: str = ""
    example_good: list[str] | list[dict[str, str]] = Field(default_factory=list)
    example_bad: list[str] = Field(default_factory=list)
    how_to_detect: SkillDetect = Field(default_factory=SkillDetect)
    game_effect: SkillEffect = Field(default_factory=SkillEffect)


class SkillBible(PermissiveModel):
    book: str = ""
    meta: dict[str, Any] = Field(default_factory=dict)
    skills: list[Skill] = Field(default_factory=list)
    scoring: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def _wrap_bare_list(cls, data):
        """Tolerate a bare JSON array of skills (see never_split_bible.json)."""
        if isinstance(data, list):
            return {"book": "", "skills": data}
        return data


class PlayerSetup(PermissiveModel):
    world_choice: str = ""
    character_name: str = ""
    goal: str = ""
    personality: str = ""
    background: str = ""
    starting_position: str = ""
    own_plan: str = ""
    skill_choice: str = "Never Split the Difference"
    timestamp: str = ""


# ---------------------------------------------------------------------------
# Piece 3: R1 / R2 / R3 contracts
# ---------------------------------------------------------------------------

class SkillFeedback(PermissiveModel):
    """R1 output - a pure skill coach. It only detects concept usage and
    coaches the player; it has NO influence on stats or mission outcome."""
    did_use_concept: bool = False
    concepts_used: list[str] = Field(default_factory=list)
    how_properly_used: str = ""
    player_intent: str = ""
    feedback_for_player: str = ""


class StatChange(PermissiveModel):
    delta: int = 0
    reason: str = ""


class StatChanges(PermissiveModel):
    trust: StatChange = Field(default_factory=StatChange)
    familiarity: StatChange = Field(default_factory=StatChange)
    respect: StatChange = Field(default_factory=StatChange)
    suspicion: StatChange = Field(default_factory=StatChange)
    rapport: StatChange = Field(default_factory=StatChange)
    disclosure_level: StatChange = Field(default_factory=StatChange)
    stress: StatChange = Field(default_factory=StatChange)


class CharacterReasoning(PermissiveModel):
    """The chain R2 must derive from before producing dialogue, so stats bind
    the character's behavior instead of being treated as inert metadata."""
    personality: str = ""
    current_goal: str = ""
    current_problem: str = ""
    current_strategy: str = ""
    relationship_state: str = ""
    current_interaction: str = ""


class Commitment(PermissiveModel):
    """An explicit promise a character made to the player in dialogue.

    Hooks the emergent world to the plan: the next scenario should consume
    open commitments (e.g. Matsuda promised to ask Chief Soichiro) instead of
    blindly following a pre-fixed chain.
    """
    character: str = ""
    target_character: str = ""
    about: str = ""
    status: str = "open"  # open | fulfilled | broken


class CharacterBrainOutput(PermissiveModel):
    character_id: str
    reasoning: CharacterReasoning = Field(default_factory=CharacterReasoning)
    inner_thought: str = ""
    dialogue: str = ""
    memory: str = ""
    stat_changes: StatChanges = Field(default_factory=StatChanges)
    commitment_made: Optional[Commitment] = None
    current_problem: str = ""
    solution: str = ""
    problem_solving_framework: str = ""


class NextMission(PermissiveModel):
    title: str = ""
    why_important: str = ""


class MissionStatus(PermissiveModel):
    current_mission_won: bool = False
    need_new_mission: bool = False
    next_mission: Optional[NextMission] = None
    chain_progress: str = ""


class SceneUpdate(PermissiveModel):
    characters_entered: list[str] = Field(default_factory=list)
    characters_left: list[str] = Field(default_factory=list)
    new_characters_present_for_next_turn: list[str] = Field(default_factory=list)


class NarratorOutput(PermissiveModel):
    narration: str = ""
    where: str = ""
    why_here: str = ""
    mission_status: MissionStatus = Field(default_factory=MissionStatus)
    scene_update: SceneUpdate = Field(default_factory=SceneUpdate)


class WorldEffect(PermissiveModel):
    character: str
    stat: str = "trust"
    delta: int = 0
    reason: str = ""


class MissionDebrief(PermissiveModel):
    message: str = ""
    location: str = ""
    who_is_around: list[str] = Field(default_factory=list)


class MissionEndOutput(PermissiveModel):
    """R4 - what a won/failed mission MEANS for the world (consequences)."""
    severity: str = "mild"
    action: str = ""
    character: str = ""
    world_effects: list[WorldEffect] = Field(default_factory=list)
    debrief: MissionDebrief = Field(default_factory=MissionDebrief)
    memory: str = ""
    event_log: str = ""


class NextMissionAdjustment(PermissiveModel):
    """R6 - how the next outline mission should be rewritten to consume hooks."""
    title: str = ""
    description: str = ""
    location: str = ""
    characters: list[str] = Field(default_factory=list)


class ReconcileOutput(PermissiveModel):
    """R6 (Scenario Director) - re-align the rough outline with what actually
    happened in dialogue, so promises made now shape what happens next."""
    revised_next: Optional[NextMissionAdjustment] = None
    commitments: list[Commitment] = Field(default_factory=list)
    material_shift: bool = False
    shift_summary: str = ""


# ---------------------------------------------------------------------------
# Piece 4: Mission state persisted per session
# ---------------------------------------------------------------------------

class Mission(PermissiveModel):
    id: int = 0
    title: str = ""
    description: str = ""
    why_important: str = ""
    status: str = "lobby"
    detail_level: str = "detailed"  # detailed (playable) | outline (name+purpose+cast, fleshed on entry)
    location: str = ""
    characters: list[str] = Field(default_factory=list)
    objective: str = ""
    reward: str = ""
    win_conditions: list[dict[str, Any]] = Field(default_factory=list)
    fail_conditions: list[dict[str, Any]] = Field(default_factory=list)


class MissionArchitectOutput(PermissiveModel):
    """R0 output - the fixed mission chain derived from the player's own plan."""
    mission_chain: list[Mission] = Field(default_factory=list)


class CharacterProjection(PermissiveModel):
    """One character's projected starting stance for this world/player."""
    character_id: str
    trust: int = 0
    familiarity: int = 0
    respect: int = 0
    suspicion: int = 0
    rapport: int = 0
    disclosure_level: int = 0
    stress: int = 0
    goal: str = ""
    problem_solving_framework: str = ""
    current_problem: str = ""
    solution: str = ""


class CastProjectionOutput(PermissiveModel):
    """R0-Cast output - how every canon character's stats/goal/problem/solution shift for THIS player."""
    characters: list[CharacterProjection] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Piece 5: Game Turn JSON (what the frontend consumes)
# ---------------------------------------------------------------------------

class GameTurnNarration(PermissiveModel):
    text: str = ""
    where: str = ""
    why_here: str = ""


class GameTurnMessage(PermissiveModel):
    speaker: str  # character id or "PLAYER"
    text: str = ""
    audio_path: Optional[str] = None
    inner_thought: Optional[str] = None
    skill_feedback: Optional[SkillFeedback] = None
    stat_deltas: dict[str, int] = Field(default_factory=dict)


class GameTurnCharacter(PermissiveModel):
    id: str
    name: str = ""
    stats: dict[str, Any] = Field(default_factory=dict)
    stat_deltas: dict[str, int] = Field(default_factory=dict)
    memory: list[str] = Field(default_factory=list)
    current_problem: str = ""
    solution: str = ""
    problem_solving_framework: str = ""
    relationship_state: str = ""
    pfp: str = ""
    present: bool = True


class GameTurnMission(PermissiveModel):
    id: int = 0
    title: str = ""
    description: str = ""
    why_important: str = ""
    status: str = "ongoing"
    chain_progress: str = ""
    location: str = ""
    characters: list[str] = Field(default_factory=list)
    objective: str = ""
    reward: str = ""
    win_conditions: list[dict[str, Any]] = Field(default_factory=list)


class GameTurn(PermissiveModel):
    turn_id: int = 0
    narration: GameTurnNarration = Field(default_factory=GameTurnNarration)
    messages: list[GameTurnMessage] = Field(default_factory=list)
    characters: list[GameTurnCharacter] = Field(default_factory=list)
    mission: GameTurnMission = Field(default_factory=GameTurnMission)
    scene_update: SceneUpdate = Field(default_factory=SceneUpdate)
    coach: Optional[Skill] = None


class TurnRequest(PermissiveModel):
    session_id: Optional[str] = None
    player_setup: Optional[PlayerSetup] = None
    new_player_input: str = ""
    action: str = ""  # "start" | "submit_plan" | "enter_mission" | "turn"
    plan_text: str = ""


class TurnResponse(PermissiveModel):
    session_id: str
    turn: GameTurn
    game_state: str = ""  # plan_elicitation | plan_revision | mission_lobby | live_mission | complete
    mission_chain: list[Mission] = Field(default_factory=list)
    world: Optional[WorldBible] = None
    debrief: Optional[MissionDebrief] = None
    events: list[str] = Field(default_factory=list)
    reconcile_shift: Optional[str] = None
