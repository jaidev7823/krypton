"""FastAPI app - one backend for simulation (Piece 3/5) + audio (Piece 6B).

Endpoints:
  POST /api/turn   {session_id?, player_setup?, new_player_input} -> GameTurn JSON
  POST /api/audio  {character_id, dialogue} -> {audio_path, duration}
  GET  /api/session/{id} -> stored session state (debug)
"""

from __future__ import annotations

import json
import logging
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from pydantic import BaseModel

from . import db, llm_caller
from .audio_service import generate_voice
from .db import create_session, get_session, last_turn_number, save_session_state
from .merge_turn import merge_turn
from .prompt_builder import (
    build_r1_prompt,
    build_r2_prompt,
    build_r3_prompt,
)
from .types import (
    CharacterBrainOutput,
    NarratorOutput,
    PlayerSetup,
    SkillBible,
    SkillFeedback,
    TurnRequest,
    TurnResponse,
    WorldBible,
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
    """Initialise live character state from the bible for a new session."""
    states = {}
    for char in world.autonomous_players:
        states[char.id] = {
            "id": char.id,
            "name": char.canon_name or char.id,
            "stats": char.stats.model_dump(mode="json"),
            "memory": list(char.memory_about_player),
            "plan": char.starting_plan.model_dump(mode="json"),
            "knowledge": char.knowledge.model_dump(mode="json"),
            "goal": char.goal,
            "dialogue_style": char.dialogue_style.model_dump(mode="json"),
            "planning_framework": char.planning_framework.model_dump(mode="json"),
            "sample_audio_path": char.stats.sample_audio_path,
            "present": char.id in ("L", "LIGHT"),  # Ryuk is an invisible observer
        }
    return states


def mission_context(mission_state: dict, scene: dict) -> dict:
    return {
        "current_mission": mission_state.get("current"),
        "old_missions_summary": mission_state.get("history", []),
        "scene": scene,
    }


def characters_present(character_states: dict) -> list[str]:
    return [cid for cid, s in character_states.items() if s.get("present", True)]


STAT_KEY_MAP = {
    "trust": "trust_towards_player",
    "suspicion": "suspicion_towards_player",
    "stress": "stress",
}


def normalize_concept(concept: str, skill_bible: SkillBible) -> str:
    """Map a (possibly sloppy) LLM concept id onto a real skill id."""
    if not concept:
        return ""
    concept_l = concept.strip().upper().rstrip("S")
    for skill in skill_bible.skills:
        if skill.id.upper() == concept_l:
            return skill.id
    for skill in skill_bible.skills:
        if skill.id.upper() in concept_l or concept_l in skill.id.upper():
            return skill.id
    return concept


def apply_r2(state: dict, out: CharacterBrainOutput, skill_bible: SkillBible) -> None:
    """Apply one character's R2 output to the live state."""
    cid = out.character_id
    if cid not in state:
        return
    char = state[cid]
    stats = char["stats"]
    for short, canonical in STAT_KEY_MAP.items():
        ch = getattr(out.stat_changes, short, None)
        if ch is not None and ch.delta:
            stats[canonical] = max(0, min(100, stats.get(canonical, 0) + ch.delta))
    if out.did_change_plan and out.new_plan:
        char["plan"] = {**out.new_plan, "status": out.plan_status}
    else:
        char["plan"]["status"] = out.plan_status
    if out.dialogue.strip():
        char["memory"].append(f"{out.dialogue[:90]}")
    if out.challenge_for_player and out.challenge_for_player.required_concept:
        out.challenge_for_player.required_concept = normalize_concept(
            out.challenge_for_player.required_concept, skill_bible
        )


def apply_scene_update(character_states: dict, entered: list, left: list, next_present: list) -> None:
    for cid in entered:
        if cid in character_states:
            character_states[cid]["present"] = True
    for cid in left:
        if cid in character_states:
            character_states[cid]["present"] = False
    if next_present:
        for cid, s in character_states.items():
            s["present"] = cid in next_present


def apply_mission_state(mission_state: dict, r3: NarratorOutput) -> None:
    ms = r3.mission_status
    current = mission_state.get("current")
    if current:
        current["status"] = "won" if ms.current_mission_won else current.get("status", "ongoing")
        if ms.current_mission_won:
            mission_state.setdefault("history", []).append(
                f"M{current.get('id', '?')} {current.get('title', '')} - won"
            )
    if ms.need_new_mission and ms.next_mission:
        nxt = ms.next_mission
        mission_state["current"] = {
            "id": (current or {}).get("id", 0) + 1,
            "title": nxt.title,
            "description": getattr(nxt, "description", "") or "",
            "why_important": nxt.why_important,
            "status": "ongoing",
        }
    elif current is None:
        # first turn, no mission yet - leave current as None, R3 created the scene
        pass


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
    mission_state = row.mission_state or {"current": None, "history": []}
    conversation = row.conversation

    scene = {
        "location": (mission_state.get("current") or {}).get("location") or world.world.starting_location,
        "characters_present": characters_present(character_states),
    }
    mctx = mission_context(mission_state, scene)

    # R1 - Listener / Teacher
    r1_system, r1_user = build_r1_prompt(skill, player, mctx, body.new_player_input, conversation)
    r1 = llm_caller.call_json(r1_system, r1_user, SkillFeedback)

    # R2 - Character Brain, one per character in scene (parallel)
    def _char_call(cid: str):
        char = character_states[cid]
        r2_system, r2_user = build_r2_prompt(
            character=char,
            character_plan=char.get("plan", {}),
            character_stats=char.get("stats", {}),
            mission_context=mctx,
            conversation=conversation,
            r1_output=r1.model_dump(mode="json"),
            world_name=world.world.name,
        )
        return llm_caller.call_json(r2_system, r2_user, CharacterBrainOutput)

    present = characters_present(character_states)
    r2_outputs: list[CharacterBrainOutput] = []
    if present:
        with ThreadPoolExecutor(max_workers=min(len(present), 4)) as ex:
            r2_outputs = list(ex.map(_char_call, present))

    # R3 - Narrator / Mission Manager
    r3_system, r3_user = build_r3_prompt(
        world,
        player,
        mctx,
        r1.model_dump(mode="json"),
        [o.model_dump(mode="json") for o in r2_outputs],
        conversation,
    )
    r3 = llm_caller.call_json(r3_system, r3_user, NarratorOutput)

    # Apply state changes
    for out in r2_outputs:
        apply_r2(character_states, out, skill)
    apply_scene_update(
        character_states,
        r3.scene_update.characters_entered,
        r3.scene_update.characters_left,
        r3.scene_update.new_characters_present_for_next_turn,
    )
    apply_mission_state(mission_state, r3)

    for msg in [{"speaker": "PLAYER", "text": body.new_player_input}]:
        conversation.append(msg)
    for out in r2_outputs:
        if out.dialogue.strip():
            conversation.append({"speaker": out.character_id, "text": out.dialogue})

    turn_number = last_turn_number(row.id) + 1
    game_turn = merge_turn(
        turn_id=turn_number,
        r1_output=r1,
        r2_outputs=r2_outputs,
        r3_output=r3,
        player_input=body.new_player_input,
        player_name=player.character_name,
        characters_state=list(character_states.values()),
        mission_state=mission_state.get("current"),
    )

    save_session_state(row.id, mission_state, character_states, conversation)
    db.log_turn(
        session_id=row.id,
        turn_number=turn_number,
        player_input=body.new_player_input,
        r1_output=r1.model_dump(mode="json"),
        r2_outputs=[o.model_dump(mode="json") for o in r2_outputs],
        r3_output=r3.model_dump(mode="json"),
        game_turn=game_turn.model_dump(mode="json"),
        model=llm_caller._current_model(),
        provider=llm_caller.available_provider(),
    )

    return TurnResponse(session_id=row.id, turn=game_turn)


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
