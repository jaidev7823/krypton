"""FastAPI app - one backend for simulation (Piece 3/5) + audio (Piece 6B).

Endpoints:
  POST /api/turn   {session_id?, player_setup?, new_player_input} -> GameTurn JSON
  POST /api/audio  {character_id, dialogue} -> {audio_path, duration}
  GET  /api/session/{id} -> stored session state (debug)
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from pydantic import BaseModel

from . import db, llm_caller
from .audio_service import generate_voice
from .db import create_session, get_session, last_turn_number, save_session_state, update_player_setup
from .merge_turn import merge_turn
from .prompt_builder import (
    build_action_mission_prompt,
    build_coach_prompt,
    build_mission_eval_prompt,
    build_r1_prompt,
    build_r2_prompt,
    build_scene_direction_prompt,
    build_world_tick_prompt,
    stat_readout,
)
from .types import (
    ActionFeasibility,
    CharacterBrainOutput,
    CoachReply,
    CoachRequest,
    GameTurn,
    GameTurnNarration,
    GameTurnScene,
    Mission,
    MissionDebrief,
    MissionObjective,
    PlayerSetup,
    SceneDirectionOutput,
    SceneExitHook,
    SkillBible,
    SkillFeedback,
    TurnRequest,
    TurnResponse,
    WorldBible,
    WorldEffect,
    WorldTickOutput,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("krypton")

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
WORLD_DIR = DATA_DIR / "world"
SKILL_DIR = DATA_DIR / "skills"
AUDIO_DIR = ROOT / "logs" / "audio"

app = FastAPI(title="Krypton Living World Simulator")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

db.init_db()
AUDIO_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/static/audio", StaticFiles(directory=str(AUDIO_DIR)), name="audio")


# ---------------------------------------------------------------------------
# Bible loading (Piece 1 + 2 - data, not generated)
# ---------------------------------------------------------------------------

def _slug(name: str) -> str:
    return name.strip().lower().replace(" ", "_")


def _find_bible(directory: Path, choice: str) -> Path:
    slug = _slug(choice)
    direct = directory / f"{slug}_bible.json"
    if direct.exists():
        return direct
    best, best_score = None, 0
    for c in sorted(directory.glob("*.json")):
        stem = c.stem.replace("_bible", "")
        s_toks, c_toks = slug.split("_"), stem.split("_")
        score = sum(1 for a, b in zip(s_toks, c_toks) if a == b)
        if score > best_score:
            best, best_score = c, score
    if best:
        return best
    raise HTTPException(500, f"No bible matches {choice!r} in {directory}")


def load_world_bible(world_choice: str) -> WorldBible:
    return WorldBible.model_validate(json.loads(_find_bible(WORLD_DIR, world_choice).read_text()))


def load_skill_bible(skill_choice: str) -> SkillBible:
    return SkillBible.model_validate(json.loads(_find_bible(SKILL_DIR, skill_choice).read_text()))


# ---------------------------------------------------------------------------
# Session helpers
# ---------------------------------------------------------------------------

def seed_character_states(world: WorldBible) -> dict:
    """Initialise live character state from the bible for a new session.

    Stats always start at 0 (neutral). The Cast Projection agent (R0-Cast)
    sets each character's stats/goal/problem/solution once the player reveals their plan.

    No character is present until the player's plan is broken into missions;
    presence is derived from the active mission's cast each turn (STATE 3/4).
    """
    states = {}
    for char in world.autonomous_players:
        stats = char.stats.model_dump(mode="json")
        stats["trust_towards_player"] = 0
        stats["familiarity_towards_player"] = 0
        stats["respect_towards_player"] = 0
        stats["suspicion_towards_player"] = 0
        stats["rapport_towards_player"] = 0
        stats["disclosure_level"] = 0
        stats["stress"] = 0
        states[char.id] = {
            "id": char.id,
            "name": char.canon_name or char.id,
            "stats": stats,
            "memory": list(char.memory_about_player),
            "problem_solving_framework": _dump_or_plain(char.problem_solving_framework),
            "current_problem": char.current_problem,
            "solution": char.solution,
            "relationship_dynamics": char.relationship_dynamics,
            "stat_ladders": char.stat_ladders,
            "knowledge": char.knowledge.model_dump(mode="json"),
            "goal": char.goal,
            "dialogue_style": _dump_or_plain(char.dialogue_style),
            "sample_audio_path": char.stats.sample_audio_path,
            "present": False,
        }
    return states


def _dump_or_plain(value) -> Any:
    return value.model_dump(mode="json") if hasattr(value, "model_dump") else value


def scene_context(mission_state: dict, scene: dict) -> dict:
    ctx = {
        "strategic_plan": mission_state.get("strategic_plan", ""),
        "scene_brief": mission_state.get("scene_brief", ""),
        "events": mission_state.get("events") or [],
        "scene": scene,
        "turns_in_scene": int(mission_state.get("turns_elapsed") or 0),
    }
    mission = mission_state.get("current_mission")
    if mission:
        ctx["mission"] = mission
    return ctx


STAT_KEY_MAP = {
    "trust": "trust_towards_player",
    "familiarity": "familiarity_towards_player",
    "respect": "respect_towards_player",
    "suspicion": "suspicion_towards_player",
    "rapport": "rapport_towards_player",
    "disclosure_level": "disclosure_level",
    "stress": "stress",
}


def apply_r2(state: dict, out: CharacterBrainOutput) -> None:
    cid = out.character_id
    if cid not in state:
        return
    char = state[cid]
    stats = char["stats"]
    for short, canonical in STAT_KEY_MAP.items():
        ch = getattr(out.stat_changes, short, None)
        if ch is not None and ch.delta:
            stats[canonical] = max(0, min(10, stats.get(canonical, 0) + ch.delta))
    if out.current_problem.strip():
        char["current_problem"] = out.current_problem
    if out.solution.strip():
        char["solution"] = out.solution
    if out.problem_solving_framework.strip():
        char["problem_solving_framework"] = out.problem_solving_framework
    if out.memory.strip():
        char["memory"] = [out.memory.strip()]


SCENE_STALL_LIMIT = 15


def _commitment_key(c: dict) -> str:
    return f"{c.get('character', '')}|{c.get('target_character', '')}|{c.get('about', '')}"


def apply_commitments(mission_state: dict, r2_outputs: list[CharacterBrainOutput]) -> None:
    ledger = mission_state.setdefault("commitments", [])
    events = mission_state.setdefault("events", [])
    for out in r2_outputs:
        c = out.commitment_made
        if not c or not c.character or not c.about.strip():
            continue
        entry = {
            "character": c.character,
            "target_character": (c.target_character or ""),
            "about": c.about.strip(),
            "status": c.status or "open",
        }
        if any(_commitment_key(x) == _commitment_key(entry) for x in ledger):
            continue
        ledger.append(entry)
        events.append(f"{entry['character']} committed: {entry['about']}.")


def apply_world_effects(character_states: dict, effects) -> None:
    for fx in effects:
        c = character_states.get(fx.character)
        if not c:
            continue
        canonical = STAT_KEY_MAP.get(fx.stat)
        if not canonical:
            continue
        stats = c["stats"]
        stats[canonical] = max(0, min(10, stats.get(canonical, 0) + (fx.delta or 0)))


def _world_tick(
    player: PlayerSetup,
    world: WorldBible,
    mission_state: dict,
    character_states: dict,
    present_ids: list[str],
    on_attempt=None,
) -> None:
    """R7: NPCs not in the current scene do things off-screen."""
    tick_system, tick_user = build_world_tick_prompt(
        player, world, "ongoing", {},
        character_states, mission_state.get("events") or [],
    )
    tick = llm_caller.call_json(
        tick_system, tick_user, WorldTickOutput,
        agent="world_tick",
        on_attempt=on_attempt("world_tick") if on_attempt else None,
    )
    events = mission_state.setdefault("events", [])
    for a in tick.actions:
        cid = a.character
        if not cid or cid in present_ids or cid not in character_states:
            continue
        if a.effects:
            apply_world_effects(character_states, [
                WorldEffect(character=cid, stat=e.stat, delta=e.delta, reason=e.reason)
                for e in a.effects
            ])
        action = a.action.strip()
        if action:
            events.append(f"Meanwhile, {cid} {action}.")


def _run_feasibility_check(
    player: PlayerSetup,
    world: WorldBible,
    character_states: dict,
    action_text: str,
    mission_state: dict,
    conversation: list | None = None,
    on_attempt=None,
) -> ActionFeasibility:
    """Fast referee: can the player realistically do this right now?"""
    from .prompt_builder import build_feasibility_check_prompt
    system, user = build_feasibility_check_prompt(
        player, world, character_states, action_text, mission_state.get("events") or [],
        conversation=conversation or [],
        commitments=mission_state.get("commitments") or [],
    )
    try:
        return llm_caller.call_json(
            system, user, ActionFeasibility,
            agent="feasibility_check",
            on_attempt=on_attempt("feasibility_check") if on_attempt else None,
        )
    except Exception as e:
        logger.warning("Feasibility check failed; allowing action: %s", e)
        return ActionFeasibility(feasible=True, reason="Proceeding.")


def _run_mission_architect(
    player: PlayerSetup,
    world: WorldBible,
    character_states: dict,
    action_text: str,
    mission_state: dict,
    on_attempt=None,
) -> Mission | None:
    """Generate a single mission from the player's declared action."""
    system, user = build_action_mission_prompt(
        player, world, character_states, action_text, mission_state.get("events") or [],
    )
    try:
        return llm_caller.call_json(
            system, user, Mission,
            agent="mission_architect",
            on_attempt=on_attempt("mission_architect") if on_attempt else None,
        )
    except Exception as e:
        logger.warning("Mission architect failed: %s", e)
        return None


def _run_mission_eval(
    player: PlayerSetup,
    world: WorldBible,
    character_states: dict,
    mission: dict,
    conversation: list,
    mission_state: dict,
    on_attempt=None,
) -> MissionDebrief | None:
    """Evaluate whether the mission was won, lost, or abandoned on scene exit."""
    system, user = build_mission_eval_prompt(
        mission, character_states, conversation, mission_state.get("events") or [],
    )
    try:
        return llm_caller.call_json(
            system, user, MissionDebrief,
            agent="mission_eval",
            on_attempt=on_attempt("mission_eval") if on_attempt else None,
        )
    except Exception as e:
        logger.warning("Mission eval failed: %s", e)
        return None


def _determine_present_ids(
    action_text: str,
    world: WorldBible,
    character_states: dict,
) -> list[str]:
    """Figure out who is in the scene based on the player's action + world access metadata."""
    action_lower = action_text.lower()
    present = []
    for char in world.autonomous_players:
        access = char.access
        where_lower = access.where.lower()
        gate_lower = access.gate.lower()
        name_lower = char.canon_name.lower()
        id_lower = char.id.lower()
        if any(k in action_lower for k in [id_lower, name_lower, where_lower]):
            present.append(char.id)
        elif access.meetability == "open" and any(
            k in action_lower for k in where_lower.split()
        ):
            present.append(char.id)
    if not present:
        for char in world.autonomous_players:
            if char.access.meetability == "open":
                present.append(char.id)
    seen = set()
    unique = []
    for cid in present:
        if cid in character_states and cid not in seen:
            unique.append(cid)
            seen.add(cid)
    return unique


def _world_response(
    session_id: str,
    mission_state: dict,
    player: PlayerSetup,
    world: WorldBible,
    feasibility: ActionFeasibility | None = None,
    scene_hooks: list[SceneExitHook] | None = None,
) -> TurnResponse:
    narration = "What is your next action?"
    if mission_state.get("scene_hooks"):
        hooks = [h if isinstance(h, SceneExitHook) else SceneExitHook(**h)
                 for h in mission_state["scene_hooks"]]
        suggestions = "; ".join(f"{h.character}: {h.suggestion}" for h in hooks[:3])
        narration += f"\n\nIdeas from the last scene: {suggestions}"
    stored_hooks = [h if isinstance(h, SceneExitHook) else SceneExitHook(**h)
                    for h in mission_state.get("scene_hooks", [])]
    turn = GameTurn(
        turn_id=0,
        narration=GameTurnNarration(text=narration),
        scene=GameTurnScene(
            title="The World",
            strategic_plan=mission_state.get("strategic_plan", ""),
            scene_hooks=stored_hooks,
        ),
    )
    return TurnResponse(
        session_id=session_id,
        turn=turn,
        game_state="world",
        world=world,
        events=mission_state.get("events") or [],
        feasibility=feasibility,
        scene_hooks=scene_hooks or stored_hooks,
        strategic_plan=mission_state.get("strategic_plan", ""),
    )


def _live_response(
    session_id: str,
    mission_state: dict,
    player: PlayerSetup,
    world: WorldBible,
    present_ids: list[str],
    feasibility: ActionFeasibility | None = None,
    mission: Mission | None = None,
) -> TurnResponse:
    location = world.world.starting_location
    title = f"Scene with {', '.join(present_ids)}"
    turn = GameTurn(
        turn_id=0,
        narration=GameTurnNarration(text=f"You step into the scene. {', '.join(present_ids)} are present."),
        scene=GameTurnScene(
            title=title,
            location=location,
            characters=present_ids,
            strategic_plan=mission_state.get("strategic_plan", ""),
        ),
    )
    return TurnResponse(
        session_id=session_id,
        turn=turn,
        game_state="live_scene",
        events=mission_state.get("events") or [],
        feasibility=feasibility,
        mission=mission,
    )



def _make_agent_logger(session_id: str, turn_number: int):
    """Build the on_attempt factory that audits every LLM call to agent_calls.

    Shared by ALL agents (caster, mission_architect, listener, brain, narrator)
    so every LLM round-trip is logged - not just the per-turn calls.
    """
    def log_agent_attempt(
        system: str,
        user_payload: dict,
        raw_response: str,
        parsed,
        success: bool,
        error: str,
        attempt: int,
        agent: str,
    ) -> None:
        db.log_agent_call(
            session_id=session_id,
            turn_number=turn_number,
            agent=agent,
            attempt=attempt,
            provider=llm_caller.available_provider(),
            model=llm_caller._current_model(),
            system_prompt=system,
            user_payload=user_payload,
            raw_response=raw_response,
            parsed_output=parsed,
            success=success,
            error=error,
        )

    def on_attempt(agent: str):
        def _cb(**kwargs):
            log_agent_attempt(**kwargs, agent=agent)
        return _cb

    return on_attempt


# ---------------------------------------------------------------------------
# Turn endpoint
# ---------------------------------------------------------------------------

def _run_turn(body: TurnRequest) -> TurnResponse:
    # Resolve session
    if body.session_id:
        row = get_session(body.session_id)
        if row is None:
            raise HTTPException(404, f"Session {body.session_id} not found")
        player = PlayerSetup.model_validate(row.player_setup)
    else:
        if body.player_setup is None:
            raise HTTPException(400, "player_setup required on first turn")
        player = body.player_setup
        if not player.world_choice:
            raise HTTPException(400, "world_choice required in player_setup")
        row = create_session(
            player.model_dump(mode="json"),
            player.world_choice,
            player.skill_choice,
        )

    world = load_world_bible(row.world_choice)
    skill = load_skill_bible(row.skill_choice)

    if not row.character_states:
        row.character_states = seed_character_states(world)
    character_states = row.character_states
    mission_state = row.mission_state or {
        "strategic_plan": "",
        "scene_hooks": [],
        "events": [],
        "commitments": [],
        "present_ids": [],
        "turns_elapsed": 0,
    }
    conversation = row.conversation

    action = body.action or "scene"
    strategic_plan = mission_state.get("strategic_plan", "").strip()
    on_attempt = _make_agent_logger(row.id, 0)

    # ------------------------------------------------------------------
    # STATE 0: Setup — player submits character + strategic plan.
    # ------------------------------------------------------------------
    if action == "setup":
        plan = (body.plan_text or body.new_player_input or "").strip()
        if not plan:
            raise HTTPException(400, "strategic plan required")
        mission_state["strategic_plan"] = plan
        mission_state["present_ids"] = []
        mission_state["turns_elapsed"] = 0
        save_session_state(row.id, mission_state, character_states, conversation)
        return _world_response(row.id, mission_state, player, world)

    # ------------------------------------------------------------------
    # STATE 1: World / Action Declaration — player declares what they do next.
    # ------------------------------------------------------------------
    if action == "declare_action":
        action_text = body.new_player_input.strip()
        if not action_text:
            raise HTTPException(400, "action required")

        feasibility = _run_feasibility_check(
            player, world, character_states, action_text, mission_state,
            conversation=conversation, on_attempt=on_attempt,
        )
        if not feasibility.feasible:
            _world_tick(player, world, mission_state, character_states,
                        mission_state.get("present_ids") or [], on_attempt=on_attempt)
            save_session_state(row.id, mission_state, character_states, conversation)
            return _world_response(
                row.id, mission_state, player, world, feasibility=feasibility,
            )

        mission = _run_mission_architect(
            player, world, character_states, action_text, mission_state,
            on_attempt=on_attempt,
        )

        if mission and mission.characters:
            present_ids = [cid for cid in mission.characters if cid in character_states]
        else:
            present_ids = _determine_present_ids(action_text, world, character_states)
        if not present_ids:
            present_ids = [c.id for c in world.autonomous_players[:1]]

        mission_state["present_ids"] = present_ids
        mission_state["turns_elapsed"] = 0
        mission_state["scene_brief"] = action_text
        if mission:
            mission_state["current_mission"] = mission.model_dump(mode="json")
        _sync_presence(character_states, present_ids)
        save_session_state(row.id, mission_state, character_states, conversation)
        return _live_response(row.id, mission_state, player, world, present_ids,
                              feasibility=feasibility, mission=mission)

    # ------------------------------------------------------------------
    # STATE 2: Live Scene — R1 + Scene Director + R2 loop.
    # ------------------------------------------------------------------
    return _run_live_turn(
        body, row, player, world, skill, mission_state, character_states, conversation,
    )


def _mission_cast(current_ids: list[str], character_states: dict) -> list[str]:
    return [cid for cid in current_ids if cid in character_states]


def _sync_presence(character_states: dict, present_ids: list[str]) -> None:
    for cid, s in character_states.items():
        s["present"] = cid in present_ids


def _run_live_turn(
    body: TurnRequest,
    row,
    player: PlayerSetup,
    world: WorldBible,
    skill: SkillBible,
    mission_state: dict,
    character_states: dict,
    conversation: list,
) -> TurnResponse:
    turn_number = last_turn_number(row.id) + 1
    present_ids = mission_state.get("present_ids") or []

    on_attempt = _make_agent_logger(row.id, turn_number)

    _sync_presence(character_states, present_ids)

    scene = {
        "location": world.world.starting_location,
        "characters_present": present_ids,
    }
    sctx = scene_context(mission_state, scene)

    r1_system, r1_user = build_r1_prompt(skill, player, sctx, body.new_player_input, conversation)
    r1 = llm_caller.call_json(
        r1_system, r1_user, SkillFeedback, agent="listener", on_attempt=on_attempt("listener")
    )

    turn_conversation = list(conversation) + [{"speaker": "PLAYER", "text": body.new_player_input}]

    speakers: list[str] = present_ids
    silent: list[str] = []
    addressed_to: Optional[str] = None

    if len(present_ids) > 1:
        try:
            summaries = {
                cid: {
                    "goal": s.get("goal", ""),
                    "current_problem": s.get("current_problem", ""),
                    "solution": s.get("solution", ""),
                    "relationship_state": s.get("relationship_dynamics", ""),
                    "stats": s.get("stats", {}),
                }
                for cid, s in character_states.items()
                if cid in present_ids
            }
            dir_system, dir_user = build_scene_direction_prompt(
                body.new_player_input, sctx, present_ids, summaries
            )
            direction = llm_caller.call_json(
                dir_system, dir_user, SceneDirectionOutput,
                agent="scene_director", on_attempt=on_attempt("scene_director"),
            )
            addressed_to = direction.addressed_to if direction.addressed_to in present_ids else None
            ordered = [c for c in direction.speaker_order if c in present_ids]
            silent = [c for c in direction.stay_silent if c in present_ids and c not in ordered]
            speakers = ordered or present_ids
        except Exception:
            logger.warning("Scene Director failed; falling back to cast order")
            speakers, silent, addressed_to = present_ids, [], None

        if addressed_to:
            speakers = [addressed_to] + [c for c in speakers if c != addressed_to]
        speakers = speakers or present_ids
        silent = [c for c in present_ids if c not in speakers]

    r2_outputs: list[CharacterBrainOutput] = []
    in_turn_before: list[dict[str, str]] = []
    for cid in speakers:
        char = character_states[cid]
        r2_system, r2_user = build_r2_prompt(
            character=char,
            mission_context=sctx,
            conversation=turn_conversation,
            new_player_input=body.new_player_input,
            world_name=world.world.name,
            addressed_to=addressed_to,
            this_turn_before_you=in_turn_before,
        )
        out = llm_caller.call_json(
            r2_system, r2_user, CharacterBrainOutput,
            agent=f"brain:{cid}", on_attempt=on_attempt(f"brain:{cid}"),
        )
        r2_outputs.append(out)
        if out.dialogue.strip():
            in_turn_before.append({"speaker": out.character_id, "text": out.dialogue})

    for out in r2_outputs:
        apply_r2(character_states, out)
    apply_commitments(mission_state, r2_outputs)
    _sync_presence(character_states, present_ids)

    mission_state["turns_elapsed"] = int(mission_state.get("turns_elapsed") or 0) + 1

    # --- Scene exit via NPC tool calls ---
    chars_leaving = []
    for out in r2_outputs:
        for tc in (out.tool_calls or []):
            if tc == "end_conversation":
                chars_leaving.append(out.character_id)

    if chars_leaving:
        for cid in chars_leaving:
            if cid in character_states:
                character_states[cid]["present"] = False
        present_ids = [cid for cid in present_ids if cid not in chars_leaving]
        mission_state["present_ids"] = present_ids
        _sync_presence(character_states, present_ids)

    turns_elapsed = int(mission_state.get("turns_elapsed") or 0)
    closed = len(present_ids) == 0 or turns_elapsed >= 15

    # Collect observer memories and scene hooks from R2 outputs
    observer_memories = []
    hooks: list[SceneExitHook] = []
    for out in r2_outputs:
        if out.silent_observations:
            observer_memories.extend(out.silent_observations)
        if out.scene_suggestion and out.scene_suggestion.character and out.scene_suggestion.suggestion.strip():
            hooks.append(out.scene_suggestion)

    _world_tick(player, world, mission_state, character_states, present_ids,
                on_attempt=on_attempt)

    for msg in [{"speaker": "PLAYER", "text": body.new_player_input}]:
        conversation.append(msg)
    for out in r2_outputs:
        if out.dialogue.strip():
            conversation.append({"speaker": out.character_id, "text": out.dialogue})

    game_turn = merge_turn(
        turn_id=turn_number,
        r1_output=r1,
        r2_outputs=r2_outputs,
        player_input=body.new_player_input,
        player_name=player.character_name,
        characters_state=list(character_states.values()),
        scene_state=mission_state,
    )

    save_session_state(row.id, mission_state, character_states, conversation)
    db.log_turn(
        session_id=row.id,
        turn_number=turn_number,
        player_input=body.new_player_input,
        r1_output=r1.model_dump(mode="json"),
        r2_outputs=[o.model_dump(mode="json") for o in r2_outputs],
        game_turn=game_turn.model_dump(mode="json"),
        model=llm_caller._current_model(),
        provider=llm_caller.available_provider(),
    )

    if closed:
        debrief = None
        current_mission = mission_state.get("current_mission")
        if current_mission:
            debrief = _run_mission_eval(
                player, world, character_states, current_mission, conversation, mission_state,
                on_attempt=on_attempt,
            )
            if debrief:
                mission_state["debrief"] = debrief.model_dump(mode="json")
                events_log = mission_state.setdefault("events", [])
                events_log.append(f"Mission '{current_mission.get('title', '')}' {debrief.outcome}.")
            mission_state.pop("current_mission", None)

        _world_tick(player, world, mission_state, character_states, present_ids,
                    on_attempt=on_attempt)
        mission_state["present_ids"] = []
        mission_state["turns_elapsed"] = 0
        _sync_presence(character_states, [])
        save_session_state(row.id, mission_state, character_states, conversation)
        return TurnResponse(
            session_id=row.id,
            turn=game_turn,
            game_state="world",
            events=mission_state.get("events") or [],
            scene_hooks=hooks,
            strategic_plan=mission_state.get("strategic_plan", ""),
            debrief=debrief,
        )

    return TurnResponse(
        session_id=row.id,
        turn=game_turn,
        game_state="live_scene",
        events=mission_state.get("events") or [],
    )


@app.post("/api/turn", response_model=TurnResponse)
def api_turn(body: TurnRequest) -> TurnResponse:
    logger.info("api/turn session=%s input=%r", body.session_id, body.new_player_input[:60])
    return _run_turn(body)


class AudioRequest(BaseModel):
    character_id: str
    dialogue: str


@app.post("/api/audio")
def api_audio(body: AudioRequest) -> dict:
    if not body.dialogue.strip():
        raise HTTPException(400, "dialogue required")
    return generate_voice(body.character_id, body.dialogue)


@app.get("/api/session/{session_id}/calls")
def api_session_calls(session_id: str) -> dict:
    """Full LLM audit trail for a session: every prompt + raw response."""
    rows = db.get_agent_calls(session_id)
    return {
        "session_id": session_id,
        "calls": [r.model_dump(mode="json") for r in rows],
    }


@app.get("/api/session/{session_id}")
def api_session(session_id: str) -> dict:
    row = get_session(session_id)
    if row is None:
        raise HTTPException(404, "not found")
    return {
        "id": row.id,
        "world_choice": row.world_choice,
        "player_setup": row.player_setup,
        "mission_state": row.mission_state,
        "character_states": row.character_states,
        "conversation": row.conversation,
    }


@app.get("/api/skill/{concept}")
def api_skill(concept: str) -> dict:
    """Return a skill definition from the active skill book (for the Coach)."""
    book = load_skill_bible("Never Split the Difference")
    for skill in book.skills:
        if skill.id.upper() == concept.strip().upper():
            return skill.model_dump(mode="json")
    raise HTTPException(404, f"skill {concept} not found in {book.book}")


@app.post("/api/coach")
def api_coach(body: CoachRequest) -> dict:
    """The Coach chat: answer the player's question with full game transparency.

    The Coach sees the live stats, the mission chain (incl. win/fail
    conditions), events, commitments and recent dialogue, and coaches the
    player toward the skill bible so they can win through technique.
    """
    row = get_session(body.session_id)
    if row is None:
        raise HTTPException(404, f"Session {body.session_id} not found")
    if not (body.message or "").strip():
        raise HTTPException(400, "message required")
    player = PlayerSetup.model_validate(row.player_setup)
    world = load_world_bible(row.world_choice)
    skill = load_skill_bible(row.skill_choice)
    mission_state = row.mission_state or {"chain": [], "current": None, "history": []}
    character_states = row.character_states or {}
    on_attempt = _make_agent_logger(row.id, 0)
    sys_prompt, user_payload = build_coach_prompt(
        player, world, skill, mission_state, character_states,
        row.conversation, body.message,
        [h.model_dump(mode="json") for h in body.history],
    )
    try:
        reply = llm_caller.call_json(
            sys_prompt, user_payload, CoachReply,
            agent="coach", on_attempt=on_attempt("coach"),
        )
    except RuntimeError as e:
        raise HTTPException(502, f"Coach unavailable: {e}")
    return {"reply": reply.reply.strip()}
