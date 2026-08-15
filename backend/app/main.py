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
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from pydantic import BaseModel

from . import db, llm_caller
from .audio_service import generate_voice
from .db import create_session, get_session, last_turn_number, save_session_state, update_player_setup
from .merge_turn import merge_turn
from .prompt_builder import (
    build_cast_prompt,
    build_coach_prompt,
    build_flesh_prompt,
    build_r0_prompt,
    build_r1_prompt,
    build_r2_prompt,
    build_r3_prompt,
    build_r4_prompt,
    build_reconcile_prompt,
    build_world_tick_prompt,
)
from .types import (
    CastProjectionOutput,
    CharacterBrainOutput,
    CoachReply,
    CoachRequest,
    GameTurn,
    GameTurnMission,
    GameTurnNarration,
    Mission,
    MissionArchitectOutput,
    MissionDebrief,
    MissionEndOutput,
    NarratorOutput,
    PlayerSetup,
    ReconcileOutput,
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


def mission_context(mission_state: dict, scene: dict) -> dict:
    return {
        "current_mission": mission_state.get("current"),
        "old_missions_summary": mission_state.get("history", []),
        "events": mission_state.get("events") or [],
        "scene": scene,
    }


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
    """Apply one character's R2 output to the live state."""
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


def chain_progress(mission_state: dict) -> str:
    chain = mission_state.get("chain") or []
    return f"{len(mission_state.get('history') or [])}/{len(chain)}"


def _condition_met(cond: dict, character_states: dict) -> bool:
    """A single win/fail condition: does the character's live stat satisfy it?"""
    cid = cond.get("character")
    short = cond.get("stat", "trust")
    canonical = STAT_KEY_MAP.get(short)
    if not cid or not canonical:
        return False
    value = character_states.get(cid, {}).get("stats", {}).get(canonical, 0)
    if "min" in cond and value < cond["min"]:
        return False
    if "max" in cond and value > cond["max"]:
        return False
    return True


def mission_outcome(mission: dict, character_states: dict, r3_won: bool) -> str:
    """Deterministic verdict from the mission's stat thresholds.

    Returns 'won', 'failed', or 'ongoing'. R3's word is used only as a
    fallback for legacy missions that have no structured conditions.
    """
    wins = mission.get("win_conditions") or []
    fails = mission.get("fail_conditions") or []
    if fails and any(_condition_met(c, character_states) for c in fails):
        return "failed"
    if wins:
        return "won" if all(_condition_met(c, character_states) for c in wins) else "ongoing"
    return "won" if r3_won else "ongoing"


def _outcome_culprits(mission: dict, character_states: dict) -> list[str]:
    """Which characters tripped a fail condition (i.e. are the reason the mission failed)."""
    culprits = []
    for cond in mission.get("fail_conditions") or []:
        cid = cond.get("character")
        if cid and _condition_met(cond, character_states) and cid not in culprits:
            culprits.append(cid)
    return culprits


def apply_world_effects(character_states: dict, effects) -> None:
    """Persist R4's permanent stat changes into the world (outlive the mission)."""
    for fx in effects:
        c = character_states.get(fx.character)
        if not c:
            continue
        canonical = STAT_KEY_MAP.get(fx.stat)
        if not canonical:
            continue
        stats = c["stats"]
        stats[canonical] = max(0, min(10, stats.get(canonical, 0) + (fx.delta or 0)))
    return None


def _commitment_key(c: dict) -> str:
    return f"{c.get('character', '')}|{c.get('target_character', '')}|{c.get('about', '')}"


def apply_commitments(mission_state: dict, r2_outputs: list[CharacterBrainOutput]) -> None:
    """Collect explicit commitments characters made this turn into the ledger.

    A commitment only enters the ledger once (dedup by who/what). Each new one
    is logged as a world event so it reads as an undeniable fact.
    """
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


def apply_mission_state(mission_state: dict, r3: NarratorOutput) -> bool:
    """Advance the fixed mission chain. The caller has already decided the
    mission was won via the deterministic stat thresholds (mission_outcome);
    R3's own verdict is never consulted.

    Never creates missions - the chain was built by R0 from the player's plan.
    Returns True if the current mission was won (game_state should move on).
    """
    current = mission_state.get("current")
    if not current:
        return False
    current["status"] = "won"
    mission_state.setdefault("history", []).append(
        f"M{current.get('id', '?')} {current.get('title', '')} - won"
    )
    chain = mission_state.get("chain") or []
    idx = next((i for i, m in enumerate(chain) if m.get("id") == current.get("id")), -1)
    nxt = chain[idx + 1] if idx >= 0 and idx + 1 < len(chain) else None
    if nxt:
        nxt["status"] = "lobby"
        mission_state["current"] = nxt
    else:
        mission_state["current"] = None
    return True


def _flesh_mission(
    player: PlayerSetup,
    world: WorldBible,
    mission_state: dict,
    character_states: dict,
    on_attempt=None,
) -> None:
    """Flesh out the current OUTLINE mission into a playable one, at entry time.

    Uses the CURRENT live stats + commitments + events so the objective can
    follow through on promises made in earlier dialogue.
    """
    current = mission_state.get("current")
    if not current or current.get("detail_level") != "outline":
        return
    commit = mission_state.get("commitments") or []
    events = mission_state.get("events") or []
    flesh_system, flesh_user = build_flesh_prompt(
        player, world, current, character_states, commit, events
    )
    flesh = llm_caller.call_json(
        flesh_system, flesh_user, MissionArchitectOutput,
        agent="mission_flesher",
        on_attempt=on_attempt("mission_flesher") if on_attempt else None,
    )
    chain = mission_state.get("chain") or []
    for m in flesh.mission_chain:
        if m.id == current.get("id"):
            m.status = current.get("status", "lobby")
            m.detail_level = "detailed"
            idx = next((i for i, x in enumerate(chain) if x.get("id") == m.id), None)
            chain[idx] = m.model_dump(mode="json")
            mission_state["current"] = chain[idx]
            return
    # Flesher produced nothing usable -> keep the outline playable (fallback
    # verdict path) rather than hard-failing the game.
    current["detail_level"] = "detailed"


def _reconcile_next(
    player: PlayerSetup,
    world: WorldBible,
    mission_state: dict,
    character_states: dict,
    outcome: str,
    conversation: list[dict[str, str]],
    on_attempt=None,
) -> None:
    """R6 (Scenario Director): after a mission ends, re-align the rough outline
    with what actually happened, so dialogue promises shape the next scenario.

    Only runs when there are open commitments worth honoring. Never changes the
    win/lose math - it only rewrites WHICH scene comes next.
    """
    commitments = mission_state.get("commitments") or []
    open_commitments = [c for c in commitments if c.get("status") == "open"]
    if not open_commitments:
        return
    chain = mission_state.get("chain") or []
    current_id = (mission_state.get("current") or {}).get("id")
    idx = next((i for i, m in enumerate(chain) if m.get("id") == current_id), -1)
    nxt = chain[idx + 1] if idx >= 0 and idx + 1 < len(chain) else None
    remaining = [m for m in chain[idx + 1:] if m.get("detail_level") == "outline"]
    if not remaining:
        return
    rec_system, rec_user = build_reconcile_prompt(
        player, world, outcome, conversation, commitments, remaining,
        mission_state.get("events") or [],
    )
    rec = llm_caller.call_json(
        rec_system, rec_user, ReconcileOutput,
        agent="scenario_director",
        on_attempt=on_attempt("scenario_director") if on_attempt else None,
    )
    if rec.commitments:
        cleaned = [c.model_dump(mode="json") for c in rec.commitments if c.character]
        mission_state["commitments"] = cleaned
    if rec.revised_next and nxt is not None:
        nxt["title"] = rec.revised_next.title or nxt.get("title", "")
        nxt["description"] = rec.revised_next.description or nxt.get("description", "")
        nxt["location"] = rec.revised_next.location or nxt.get("location", "")
        nxt["characters"] = rec.revised_next.characters or nxt.get("characters", [])
    if rec.material_shift and rec.shift_summary.strip():
        mission_state["reconcile_shift"] = rec.shift_summary.strip()
        mission_state.setdefault("events", []).append(f"WORLD SHIFT: {rec.shift_summary.strip()}")


def _world_tick(
    player: PlayerSetup,
    world: WorldBible,
    mission_state: dict,
    character_states: dict,
    outcome: str,
    on_attempt=None,
) -> None:
    """R7: the NPCs NOT in the player's mission were busy off-screen.

    Persist their stat drift + log 'Meanwhile...' events so the world visibly
    keeps moving even when the player is focused on one thread.
    """
    current = mission_state.get("current") or {}
    tick_system, tick_user = build_world_tick_prompt(
        player, world, outcome, current, character_states,
        mission_state.get("events") or [],
    )
    tick = llm_caller.call_json(
        tick_system, tick_user, WorldTickOutput,
        agent="world_tick",
        on_attempt=on_attempt("world_tick") if on_attempt else None,
    )
    cast = [c for c in (current.get("characters") or [])]
    events = mission_state.setdefault("events", [])
    for a in tick.actions:
        cid = a.character
        if not cid or cid in cast or cid not in character_states:
            continue
        if a.effects:
            apply_world_effects(character_states, [
                WorldEffect(character=cid, stat=e.stat, delta=e.delta, reason=e.reason)
                for e in a.effects
            ])
        action = a.action.strip()
        if action:
            events.append(f"Meanwhile, {cid} {action}.")



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
    mission_state = row.mission_state or {"chain": [], "current": None, "history": []}
    conversation = row.conversation

    action = body.action or "turn"
    own_plan = (player.own_plan or "").strip()

    # Every LLM call is audited - plan-time agents log under turn 0 since no
    # mission turn has happened yet.
    on_attempt = _make_agent_logger(row.id, 0)

    # ------------------------------------------------------------------
    # STATE 0: previous plan FLOOPED -> the player must propose a new one.
    # The cast is NOT re-projected - stats and memories survive the flop.
    # ------------------------------------------------------------------
    if mission_state.get("plan_flopped") and not mission_state.get("chain"):
        if action == "submit_plan":
            plan = (body.plan_text or "").strip()
            if not plan:
                raise HTTPException(400, "plan_text required for submit_plan")
            player.own_plan = plan
            update_player_setup(row.id, player.model_dump(mode="json"))
            mission_state["plan_flopped"] = False
            mission_state["events"] = mission_state.get("events") or []
            mission_state = _build_mission_chain(
                player, world, mission_state, character_states,
                on_attempt=on_attempt, reproject=False,
            )
            save_session_state(row.id, mission_state, character_states, conversation)
            return _lobby_response(row.id, mission_state, player, world)
        return _plan_revision_response(row.id, mission_state, player, world)

    # ------------------------------------------------------------------
    # STATE 1: no plan yet -> elicit it. NO LLM.
    # ------------------------------------------------------------------
    if not own_plan:
        if action == "submit_plan":
            plan = (body.plan_text or "").strip()
            if not plan:
                raise HTTPException(400, "plan_text required for submit_plan")
            player.own_plan = plan
            update_player_setup(row.id, player.model_dump(mode="json"))
            mission_state = _build_mission_chain(player, world, mission_state, character_states, on_attempt=on_attempt)
            save_session_state(row.id, mission_state, character_states, conversation)
            return _lobby_response(row.id, mission_state, player, world)
        return _plan_response(row.id, player, world)

    # ------------------------------------------------------------------
    # STATE 2 recovery: plan exists but chain was never built.
    # ------------------------------------------------------------------
    if not mission_state.get("chain"):
        mission_state = _build_mission_chain(player, world, mission_state, character_states, on_attempt=on_attempt)
        save_session_state(row.id, mission_state, character_states, conversation)

    current = mission_state.get("current")

    # All missions done.
    if current is None:
        return _complete_response(row.id, mission_state, player)

    # ------------------------------------------------------------------
    # STATE 3: mission lobby (or retry after a failure). NO LLM until Enter Mission.
    # ------------------------------------------------------------------
    if current.get("status") in ("lobby", "failed"):
        if action == "enter_mission":
            # Outline missions are fleshed out NOW so the playable detail can
            # use the latest stats + any promises made in earlier dialogue.
            _flesh_mission(player, world, mission_state, character_states, on_attempt=on_attempt)
            current = mission_state["current"]
            current["status"] = "active"
            save_session_state(row.id, mission_state, character_states, conversation)
            return _live_response(row.id, mission_state, player)
        if action == "revise_plan":
            # Voluntary re-plan: same semantics as a plan flop - the chain is
            # voided but stats/memories/commitments survive.
            mission_state["plan_flopped"] = True
            mission_state["chain"] = []
            mission_state["current"] = None
            mission_state["reconcile_shift"] = None
            save_session_state(row.id, mission_state, character_states, conversation)
            return _plan_revision_response(row.id, mission_state, player, world)
        return _lobby_response(row.id, mission_state, player, world)

    # ------------------------------------------------------------------
    # STATE 4: LIVE MISSION - R1 + R2 + R3, cast locked to the mission.
    # ------------------------------------------------------------------
    return _run_live_turn(
        body, row, player, world, skill, mission_state, character_states, conversation, action
    )


def _mission_cast(current: dict, character_states: dict) -> list[str]:
    """Characters allowed in the room this turn = the active mission's cast."""
    cast = current.get("characters") or []
    return [cid for cid in cast if cid in character_states]


def _sync_presence(character_states: dict, present_ids: list[str]) -> None:
    for cid, s in character_states.items():
        s["present"] = cid in present_ids


def _run_cast_projection(
    player: PlayerSetup,
    world: WorldBible,
    character_states: dict,
    on_attempt=None,
) -> None:
    """R0-Cast: reset each character's stance from zero and let the LLM project
    new stats, goal, current problem and solution from the player's profile + canon."""
    system, user = build_cast_prompt(player, world)
    out = llm_caller.call_json(
        system, user, CastProjectionOutput,
        agent="caster", on_attempt=on_attempt("caster") if on_attempt else None,
    )
    for p in out.characters:
        c = character_states.get(p.character_id)
        if not c:
            continue
        stats = c["stats"]
        stats["trust_towards_player"] = max(0, min(10, p.trust))
        stats["familiarity_towards_player"] = max(0, min(10, p.familiarity))
        stats["respect_towards_player"] = max(0, min(10, p.respect))
        stats["suspicion_towards_player"] = max(0, min(10, p.suspicion))
        stats["rapport_towards_player"] = max(0, min(10, p.rapport))
        stats["disclosure_level"] = max(0, min(10, p.disclosure_level))
        stats["stress"] = max(0, min(10, p.stress))
        if p.goal:
            c["goal"] = p.goal
        if p.current_problem or p.solution:
            c["current_problem"] = p.current_problem or c.get("current_problem", "")
            c["solution"] = p.solution or c.get("solution", "")
        if p.problem_solving_framework:
            c["problem_solving_framework"] = p.problem_solving_framework


def _build_mission_chain(
    player: PlayerSetup,
    world: WorldBible,
    mission_state: dict,
    character_states: dict,
    on_attempt=None,
    reproject: bool = True,
) -> dict:
    """STATE 2 - project the cast (R0-Cast), then run the Mission Architect (R0).

    reproject=False is used when the player revises a failed plan: the cast is
    NOT reset - live stats and memories survive so characters remember the
    player and the world keeps its damage.
    """
    if reproject:
        _run_cast_projection(player, world, character_states, on_attempt=on_attempt)
    r0_system, r0_user = build_r0_prompt(player, world, character_states)
    r0 = llm_caller.call_json(
        r0_system, r0_user, MissionArchitectOutput,
        agent="mission_architect",
        on_attempt=on_attempt("mission_architect") if on_attempt else None,
    )
    chain = [m.model_dump(mode="json") for m in r0.mission_chain]
    if not chain:
        raise HTTPException(500, "Mission Architect returned an empty mission chain")
    chain[0]["status"] = "lobby"
    chain[0]["detail_level"] = "detailed"
    for m in chain[1:]:
        m["detail_level"] = "outline"
        m.setdefault("objective", "")
        m.setdefault("reward", "")
        m.setdefault("win_conditions", [])
        m.setdefault("fail_conditions", [])
    mission_state["chain"] = chain
    mission_state["current"] = chain[0]
    mission_state["history"] = mission_state.get("history") or []
    mission_state.setdefault("commitments", [])
    mission_state["reconcile_shift"] = None
    return mission_state

def _mission_turn(turn_id: int, mission_state: dict, narration: str) -> GameTurn:
    current = mission_state.get("current") or {}
    return GameTurn(
        turn_id=turn_id,
        narration=GameTurnNarration(text=narration),
        mission=GameTurnMission(
            id=current.get("id", 0),
            title=current.get("title", ""),
            description=current.get("description", ""),
            why_important=current.get("why_important", ""),
            status=current.get("status", "lobby"),
            chain_progress=chain_progress(mission_state),
            location=current.get("location", ""),
            characters=current.get("characters", []),
            objective=current.get("objective", ""),
            reward=current.get("reward", ""),
        ),
    )


def _plan_response(session_id: str, player: PlayerSetup, world: WorldBible) -> TurnResponse:
    turn = _mission_turn(0, {"chain": [], "current": None, "history": []},
                         "Define your plan. The world will wait.")
    return TurnResponse(session_id=session_id, turn=turn,
                        game_state="plan_elicitation", mission_chain=[], world=world,
                        events=[])


def _lobby_response(session_id: str, mission_state: dict, player: PlayerSetup, world: WorldBible) -> TurnResponse:
    current = mission_state.get("current") or {}
    if current.get("status") == "failed":
        narration = (
            f"Mission M{current.get('id', '?')} failed. The conversation broke down and "
            f"{', '.join(current.get('characters') or [])} left. You'll have to try again."
        )
    else:
        narration = (
            f"Mission M{current.get('id', '?')}: {current.get('title', '')}. "
            f"{current.get('objective', '')}"
        )
    turn = _mission_turn(0, mission_state, narration)
    chain = mission_state.get("chain") or []
    return TurnResponse(session_id=session_id, turn=turn, game_state="mission_lobby",
                        mission_chain=[Mission.model_validate(m) for m in chain], world=world,
                        events=mission_state.get("events") or [],
                        reconcile_shift=mission_state.get("reconcile_shift"))


def _plan_revision_response(
    session_id: str, mission_state: dict, player: PlayerSetup, world: WorldBible
) -> TurnResponse:
    """STATE: the previous plan flopped - the player must propose a new one.

    Nothing is reset: live stats, memories and the failure debrief all survive.
    """
    debrief = mission_state.get("plan_flop_debrief") or {}
    message = (
        debrief.get("message")
        or "Your plan fell apart. Where do you go from here? What is your new plan?"
    )
    where = debrief.get("location") or ""
    around = debrief.get("who_is_around") or []
    location = (f" You're at {where}." if where else "") or " You're back where the plan broke down."
    around_txt = f" Nearby: {', '.join(around)}." if around else ""
    events = mission_state.get("events") or []
    if events:
        around_txt += f"\nWhat happened: {' '.join(events[-2:])}"
    narration = message + location + around_txt
    turn = _mission_turn(
        0, {"chain": [], "current": None, "history": mission_state.get("history") or []},
        narration,
    )
    return TurnResponse(
        session_id=session_id,
        turn=turn,
        game_state="plan_revision",
        mission_chain=[],
        world=world,
        debrief=MissionDebrief(message=message, location=where, who_is_around=around),
        events=mission_state.get("events") or [],
    )


def _live_response(session_id: str, mission_state: dict, player: PlayerSetup) -> TurnResponse:
    current = mission_state.get("current") or {}
    narration = (
        f"You step into {current.get('location', 'the scene')} for "
        f"'{current.get('title', '')}'. {current.get('objective', '')}"
    )
    turn = _mission_turn(0, mission_state, narration)
    return TurnResponse(session_id=session_id, turn=turn, game_state="live_mission",
                        mission_chain=mission_state.get("chain") or [],
                        events=mission_state.get("events") or [])


def _complete_response(session_id: str, mission_state: dict, player: PlayerSetup) -> TurnResponse:
    turn = _mission_turn(
        0, mission_state,
        "All missions complete. Your plan is fulfilled - the world remembers what you did.",
    )
    return TurnResponse(session_id=session_id, turn=turn, game_state="complete",
                        mission_chain=mission_state.get("chain") or [],
                        events=mission_state.get("events") or [])


def _run_live_turn(
    body: TurnRequest,
    row,
    player: PlayerSetup,
    world: WorldBible,
    skill: SkillBible,
    mission_state: dict,
    character_states: dict,
    conversation: list,
    action: str,
) -> TurnResponse:
    """STATE 4 - the original R1 + R2 + R3 loop, run per active mission turn."""
    turn_number = last_turn_number(row.id) + 1
    current = mission_state["current"]

    on_attempt = _make_agent_logger(row.id, turn_number)

    # The room contains ONLY the active mission's cast - never the full bible.
    present_ids = _mission_cast(current, character_states)
    _sync_presence(character_states, present_ids)

    scene = {
        "location": current.get("location") or world.world.starting_location,
        "characters_present": present_ids,
    }
    mctx = mission_context(mission_state, scene)

    # R1 - Listener / Teacher
    r1_system, r1_user = build_r1_prompt(skill, player, mctx, body.new_player_input, conversation)
    r1 = llm_caller.call_json(
        r1_system, r1_user, SkillFeedback, agent="listener", on_attempt=on_attempt("listener")
    )

    # The brain must see the player's LATEST message. The persisted `conversation`
    # only contains prior turns - the new input is appended AFTER R2 runs. So build
    # a per-turn copy that ends with the player's newest words.
    turn_conversation = list(conversation) + [{"speaker": "PLAYER", "text": body.new_player_input}]

    # R2 - Character Brain, one per character in the mission cast (parallel).
    # The brain judges ONLY the player's words - the R1 skill analysis is
    # intentionally NOT passed to it.
    def _char_call(cid: str):
        char = character_states[cid]
        r2_system, r2_user = build_r2_prompt(
            character=char,
            mission_context=mctx,
            conversation=turn_conversation,
            new_player_input=body.new_player_input,
            world_name=world.world.name,
        )
        return llm_caller.call_json(
            r2_system, r2_user, CharacterBrainOutput,
            agent=f"brain:{cid}", on_attempt=on_attempt(f"brain:{cid}"),
        )

    r2_outputs: list[CharacterBrainOutput] = []
    if present_ids:
        with ThreadPoolExecutor(max_workers=min(len(present_ids), 4)) as ex:
            r2_outputs = list(ex.map(_char_call, present_ids))

    # Apply state changes FIRST so the mission verdict reads the post-turn stats.
    for out in r2_outputs:
        apply_r2(character_states, out)
    # Hooks ledger: explicit promises made this turn (deduped + logged as events).
    apply_commitments(mission_state, r2_outputs)
    # Presence is ALWAYS the mission cast - ignore R3's scene_update so the
    # model can never drag in characters that are not part of the mission.
    _sync_presence(character_states, present_ids)

    # Deterministic mission verdict from the stat thresholds set by R0.
    outcome = mission_outcome(current, character_states, False)

    # R3 - Narrator (verdict already decided; it only narrates it)
    r3_mctx = {**mctx, "computed_mission_outcome": outcome}
    r3_system, r3_user = build_r3_prompt(
        world,
        player,
        r3_mctx,
        r1.model_dump(mode="json"),
        [o.model_dump(mode="json") for o in r2_outputs],
        turn_conversation,
    )
    r3 = llm_caller.call_json(
        r3_system, r3_user, NarratorOutput, agent="narrator", on_attempt=on_attempt("narrator")
    )

    # If EVERYONE in the mission cast left, the room is empty and no further
    # conversation can happen - the mission is over, regardless of stats.
    # R3 only reports who left; the emptiness itself is a mechanical verdict.
    if outcome != "won" and present_ids:
        left = set(r3.scene_update.characters_left or [])
        if all(cid in left for cid in present_ids):
            outcome = "failed"

    # R4 - Mission End Director: what the end MEANS for the world.
    # Runs only when the mission is definitively won or failed.
    r4: MissionEndOutput | None = None
    if outcome in ("won", "failed"):
        culprits = _outcome_culprits(current, character_states) if outcome == "failed" else []
        culprit_states = {cid: character_states.get(cid) for cid in culprits}
        r4_system, r4_user = build_r4_prompt(
            outcome=outcome,
            mission_context=mctx,
            culprit_states=culprit_states,
            r2_outputs=[o.model_dump(mode="json") for o in r2_outputs],
            player=player,
            world=world,
            conversation=turn_conversation,
        )
        r4 = llm_caller.call_json(
            r4_system, r4_user, MissionEndOutput,
            agent="mission_end", on_attempt=on_attempt("mission_end"),
        )
        apply_world_effects(character_states, r4.world_effects)
        if r4.character in character_states and r4.memory.strip():
            character_states[r4.character]["memory"] = [r4.memory.strip()]
        if r4.event_log.strip():
            mission_state.setdefault("events", []).append(r4.event_log.strip())

        # R7 - World Tick: everyone else in the world kept moving while the
        # player was locked into this mission. Runs on BOTH win and fail.
        _world_tick(player, world, mission_state, character_states, outcome,
                    on_attempt=on_attempt)

    if outcome == "won":
        # R6 - Scenario Director FIRST (while `current` is still the finished
        # mission): re-align the next rough outline with commitments made in
        # dialogue, then let apply_mission_state advance onto the revised entry.
        _reconcile_next(
            player, world, mission_state, character_states, outcome,
            turn_conversation, on_attempt=on_attempt,
        )
        apply_mission_state(mission_state, r3)
    elif outcome == "failed":
        # PLAN FLOP: the whole chain is void - the world keeps the damage and
        # the player must propose a new plan. Memory + stats survive.
        mission_state["plan_flopped"] = True
        mission_state["plan_flop_debrief"] = r4.debrief.model_dump(mode="json")
        around = [c for c in (r4.debrief.who_is_around or []) if c in character_states]
        _sync_presence(character_states, around)
        mission_state["chain"] = []
        mission_state["current"] = None

    for msg in [{"speaker": "PLAYER", "text": body.new_player_input}]:
        conversation.append(msg)
    for out in r2_outputs:
        if out.dialogue.strip():
            conversation.append({"speaker": out.character_id, "text": out.dialogue})

    game_turn = merge_turn(
        turn_id=turn_number,
        r1_output=r1,
        r2_outputs=r2_outputs,
        r3_output=r3,
        player_input=body.new_player_input,
        player_name=player.character_name,
        characters_state=list(character_states.values()),
        mission_state=mission_state.get("current"),
        chain_progress=chain_progress(mission_state),
    )
    if r4 and r4.debrief.message.strip():
        game_turn.narration.text = (
            f"{game_turn.narration.text}\n\n{r4.debrief.message.strip()}"
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

    if outcome == "won":
        game_state = "complete" if mission_state.get("current") is None else "mission_lobby"
        debrief = r4.debrief if r4 else None
    elif outcome == "failed":
        game_state = "plan_revision"
        debrief = r4.debrief if r4 else None
    else:
        game_state = "live_mission"
        debrief = None

    return TurnResponse(session_id=row.id, turn=game_turn, game_state=game_state,
                        mission_chain=mission_state.get("chain") or [], debrief=debrief,
                        events=mission_state.get("events") or [])


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
