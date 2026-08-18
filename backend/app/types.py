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


class CharacterAccess(PermissiveModel):
    """How reachable this character is - the world's control over who the
    player can realistically meet. The Feasibility Gate must respect these."""
    meetability: str = ""  # "open" | "guarded" | "secluded"
    gate: str = ""         # what unlocks a meeting (e.g. "introduction from a Task Force member")
    where: str = ""        # where/when the character can actually be found
    grants: list[str] = Field(default_factory=list)  # introductions, information, access


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
    access: CharacterAccess = Field(default_factory=CharacterAccess)


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


class PlayerProfile(PermissiveModel):
    """Living document tracking who the player IS, what they HAVE,
    what they KNOW, and what they've LEARNED. Updated every turn."""

    status: str = ""              # "Student", "NPA Intern", "Wanted"
    cash: int = 0
    resources: list[str] = Field(default_factory=list)
    knowledge: list[str] = Field(default_factory=list)
    reputation: str = "unknown student"
    concepts_used: dict[str, dict] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Piece 3: R1 / R2 contracts
# ---------------------------------------------------------------------------

class SkillFeedback(PermissiveModel):
    """R1 output - a pure skill coach. It only detects concept usage and
    coaches the player; it has NO influence on stats or mission outcome."""
    did_use_concept: bool = False
    concepts_used: list[str] = Field(default_factory=list)
    how_properly_used: str = ""
    player_intent: str = ""
    feedback_for_player: str = ""
    missed_concepts: list[str] = Field(default_factory=list)
    missed_context: str = ""


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


class SceneExitHook(PermissiveModel):
    """An NPC suggestion extracted from scene exit dialogue."""
    character: str = ""
    suggestion: str = ""
    context: str = ""


class ObserverMemory(PermissiveModel):
    """One line a present-but-silent character takes in while others speak."""
    character: str = ""
    note: str = ""


class CharacterBrainOutput(PermissiveModel):
    character_id: str
    reasoning: CharacterReasoning = Field(default_factory=CharacterReasoning)
    inner_thought: str = ""
    dialogue: str = ""
    memory: str = ""
    stat_changes: StatChanges = Field(default_factory=StatChanges)
    commitment_made: Optional[Commitment] = None
    tool_calls: list[str] = Field(default_factory=list)
    current_problem: str = ""
    solution: str = ""
    problem_solving_framework: str = ""
    silent_observations: list[ObserverMemory] = Field(default_factory=list)
    scene_suggestion: Optional[SceneExitHook] = None
    profile_updates: dict[str, Any] = Field(default_factory=dict)


class SceneDirectionOutput(PermissiveModel):
    """Scene Director output - who the player aimed at, who reacts and in what
    order, and who is present but stays silent this turn.

    Mechanical rules in main.py force `addressed_to` first and guarantee at
    least one speaker, so a bad model answer can never freeze the scene."""
    addressed_to: Optional[str] = None
    speaker_order: list[str] = Field(default_factory=list)
    stay_silent: list[str] = Field(default_factory=list)


class ActionFeasibility(PermissiveModel):
    """Can the player realistically do this action right now?"""
    feasible: bool = True
    reason: str = ""
    suggestions: list[str] = Field(default_factory=list)


class MissionObjective(PermissiveModel):
    """A single win or fail condition on a stat."""
    character: str = ""
    stat: str = ""
    min: int = 0
    max: int = 10


class Mission(PermissiveModel):
    """A single mission generated from the player's declared action."""
    id: int = 1
    title: str = ""
    description: str = ""
    characters: list[str] = Field(default_factory=list)
    location: str = ""
    objective: str = ""
    reward: str = ""
    win_conditions: list[MissionObjective] = Field(default_factory=list)
    fail_conditions: list[MissionObjective] = Field(default_factory=list)


class MissionDebrief(PermissiveModel):
    """What happened when the mission ended."""
    outcome: str = ""  # "won" | "lost" | "abandoned"
    message: str = ""
    location: str = ""
    who_is_around: list[str] = Field(default_factory=list)


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
    conversation_over: bool = False
    ending: str = ""


class WorldEffect(PermissiveModel):
    character: str
    stat: str = "trust"
    delta: int = 0
    reason: str = ""


class SceneExitSummary(PermissiveModel):
    """What happened when the scene closed."""
    hooks: list[SceneExitHook] = Field(default_factory=list)
    narration: str = ""
    characters_left: list[str] = Field(default_factory=list)


class NpcEffect(PermissiveModel):
    """A permanent stat drift caused by an NPC's off-screen agenda."""
    stat: str = "stress"
    delta: int = 0
    reason: str = ""


class NpcAction(PermissiveModel):
    """R7 - one background action a non-cast NPC took while the player was busy."""
    character: str
    action: str = ""
    effects: list[NpcEffect] = Field(default_factory=list)


class WorldTickOutput(PermissiveModel):
    """R7 (World Tick) - what NPCs did on their own between missions, so the
    world visibly changes even when the player is focused on one thread."""
    actions: list[NpcAction] = Field(default_factory=list)


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


class GameTurnScene(PermissiveModel):
    """Current scene context (replaces the old rigid mission card)."""
    title: str = ""
    location: str = ""
    characters: list[str] = Field(default_factory=list)
    reason: str = ""
    strategic_plan: str = ""
    scene_hooks: list[SceneExitHook] = Field(default_factory=list)


class GameTurn(PermissiveModel):
    turn_id: int = 0
    narration: GameTurnNarration = Field(default_factory=GameTurnNarration)
    messages: list[GameTurnMessage] = Field(default_factory=list)
    characters: list[GameTurnCharacter] = Field(default_factory=list)
    scene: GameTurnScene = Field(default_factory=GameTurnScene)
    scene_update: SceneUpdate = Field(default_factory=SceneUpdate)
    coach: Optional[Skill] = None


class TurnRequest(PermissiveModel):
    session_id: Optional[str] = None
    player_setup: Optional[PlayerSetup] = None
    new_player_input: str = ""
    action: str = ""  # "setup" | "declare_action" | "scene"
    plan_text: str = ""  # used for strategic plan edits


class CoachMessage(PermissiveModel):
    role: str = "player"  # "player" | "coach"
    content: str = ""


class CoachRequest(PermissiveModel):
    session_id: str = ""
    message: str = ""
    history: list[CoachMessage] = Field(default_factory=list)


class CoachReply(PermissiveModel):
    """The Coach's answer - free-text guidance grounded in the live game state."""
    reply: str = ""


class TurnResponse(PermissiveModel):
    session_id: str
    turn: GameTurn
    game_state: str = ""  # "setup" | "world" | "live_scene" | "complete"
    world: Optional[WorldBible] = None
    events: list[str] = Field(default_factory=list)
    feasibility: Optional[ActionFeasibility] = None
    scene_hooks: list[SceneExitHook] = Field(default_factory=list)
    strategic_plan: str = ""
    mission: Optional[Mission] = None
    debrief: Optional[MissionDebrief] = None
    player_profile: Optional[PlayerProfile] = None
