"""State-machine regression test for the 5-state game loop.

Runs ``_run_turn`` end-to-end with a mocked LLM (no API keys) against a temp
SQLite DB. Guards against the hallucination bug: before a plan exists no LLM
may be called, and during a live mission only the mission's cast is in the
room.

Run:  python -m tests.test_states  (from backend/)
"""

import json
import os
import sys
import tempfile
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
os.chdir(BACKEND)

from app import db as db_module  # noqa: E402

_tmp = tempfile.mkdtemp()
db_module.DB_DIR = Path(_tmp)
db_module.DB_PATH = db_module.DB_DIR / "game.db"
from sqlalchemy import create_engine  # noqa: E402
from sqlmodel import SQLModel  # noqa: E402
db_module.engine = create_engine(f"sqlite:///{db_module.DB_PATH}", connect_args={"check_same_thread": False})
SQLModel.metadata.create_all(db_module.engine)

from app import llm_caller, main  # noqa: E402
from app.types import (  # noqa: E402
    CastProjectionOutput, CharacterBrainOutput, CharacterProjection, Mission,
    MissionArchitectOutput, NarratorOutput, SkillFeedback, TurnRequest,
)

CALLS: list[str] = []
LIVE_TURNS = {"count": 0}


def _fake_model(agent):
    if agent == "caster":
        return CastProjectionOutput(characters=[
            CharacterProjection(character_id="MATSUDA", trust=4, suspicion=1,
                                stress=2, goal="Find a reliable witness",
                                plan_objective="Get Jay's help",
                                plan="Ask Jay friendly questions"),
            CharacterProjection(character_id="L", trust=1, suspicion=5, stress=3,
                                goal="Identify Kira",
                                plan_objective="Watch Jay closely",
                                plan="Observe without revealing himself"),
        ])
    if agent == "mission_architect":
        return MissionArchitectOutput(mission_chain=[
            Mission(id=1, title="Matsuda Bridge", description="Get a referral",
                    objective="Raise Matsuda trust", reward="Matsuda's number",
                    location="Cafeteria", characters=["MATSUDA"]),
            Mission(id=2, title="Earn L's attention", description="Get noticed",
                    objective="Lower L suspicion", reward="L's interest",
                    location="Class 3B", characters=["L"]),
        ])
    if agent == "listener":
        return SkillFeedback(did_use_concept=False)
    if agent.startswith("brain:"):
        cid = agent.split(":", 1)[1]
        return CharacterBrainOutput(character_id=cid, dialogue=f"{cid} speaks",
                                    inner_thought=f"{cid} thinks")
    if agent == "narrator":
        won = LIVE_TURNS["count"] >= 1
        return NarratorOutput(narration="The cafeteria hums.",
                              where="Cafeteria",
                              why_here="Mission in progress",
                              mission_status={"current_mission_won": won})
    raise AssertionError(f"unexpected agent {agent}")


def fake_call_json(system, user, response_model, retries=3, agent="default", on_attempt=None):
    CALLS.append(agent)
    model = _fake_model(agent)
    if on_attempt:
        on_attempt(system=system, user_payload=user, raw_response="{}",
                   parsed=model.model_dump(mode="json"), success=True, error="", attempt=1)
    return model


llm_caller.call_json = fake_call_json


def check(cond, msg):
    if not cond:
        raise AssertionError(f"FAIL: {msg}")
    print(f"ok  - {msg}")


def setup_json():
    return {
        "world_choice": "Death Note",
        "character_name": "Jay",
        "goal": "Prove Light is Kira without dying",
        "personality": "Paranoid",
        "background": "Ex-detective assistant",
        "starting_position": "Class 3B",
        "own_plan": "",
        "skill_choice": "Never Split the Difference",
    }


def run_checks():
    # STATE 0 -> STATE 1: setup with no plan must NOT call any LLM
    r = main._run_turn(TurnRequest(player_setup=json.loads(json.dumps(setup_json())),
                                   new_player_input="", action="start"))
    sid = r.session_id
    check(r.game_state == "plan_elicitation", "start -> plan_elicitation")
    check(r.world is not None and len(r.world.autonomous_players) == 5, "world bible for gallery")
    check(CALLS == [], f"NO LLM before a plan exists (calls={CALLS})")

    # Live character stats are seeded at 0 before any plan is projected
    world = main.load_world_bible("Death Note")
    seeded = main.seed_character_states(world)
    check(all(seeded[cid]["stats"]["trust_towards_player"] == 0
              and seeded[cid]["stats"]["suspicion_towards_player"] == 0
              and seeded[cid]["stats"]["stress"] == 0
              for cid in ("L", "LIGHT", "MATSUDA", "SOICHIRO", "RYUK")),
          "stats default to 0 before the plan is projected")

    # STATE 1 -> 2: submit a plan -> caster THEN R0 runs ONCE, mission lobby
    r = main._run_turn(TurnRequest(session_id=sid, action="submit_plan",
                                   plan_text="Get close to Matsuda, then earn L's attention"))
    check(r.game_state == "mission_lobby", "submit_plan -> mission_lobby")
    check(CALLS == ["caster", "mission_architect"],
          f"caster ran BEFORE mission_architect, once (calls={CALLS})")
    check(len(r.mission_chain) == 2, "mission chain of 2 built")
    check(r.turn.mission.title == "Matsuda Bridge" and r.turn.mission.status == "lobby",
          "current mission is M1 in lobby")

    # Cast projection persisted: stats/goal/plan updated for projected chars
    row = db_module.get_session(sid)
    mat = row.character_states["MATSUDA"]
    check(mat["stats"]["trust_towards_player"] == 4, "MATSUDA trust projected to 4")
    check(mat["stats"]["suspicion_towards_player"] == 1, "MATSUDA suspicion projected to 1")
    check(mat["goal"] == "Find a reliable witness", "MATSUDA goal rewritten by caster")
    check(mat["plan"]["plan"].startswith("Ask Jay"), "MATSUDA plan rewritten by caster")
    check(row.character_states["L"]["stats"]["suspicion_towards_player"] == 5,
          "L suspicion projected to 5")

    # STATE 3 -> 4: enter mission -> no LLM, live
    r = main._run_turn(TurnRequest(session_id=sid, action="enter_mission", new_player_input=""))
    check(r.game_state == "live_mission", "enter_mission -> live_mission")
    check(CALLS == ["caster", "mission_architect"], "enter_mission still no LLM")

    # STATE 4: live turn -> R1+R2(cast only)+R3, presence synced
    r = main._run_turn(TurnRequest(session_id=sid, new_player_input="Hello Matsuda"))
    LIVE_TURNS["count"] += 1
    check(r.game_state == "live_mission", "live turn stays live")
    brains = [c for c in CALLS if c.startswith("brain:")]
    check(brains == ["brain:MATSUDA"], f"R2 ran ONLY for mission cast (got {brains})")
    row = db_module.get_session(sid)
    present = [cid for cid, s in row.character_states.items() if s.get("present")]
    check(present == ["MATSUDA"], f"presence synced to mission cast only (got {present})")
    check(all(not row.character_states[cid]["present"] for cid in ("L", "LIGHT", "RYUK")),
          "L/LIGHT/RYUK NOT in the room during Matsuda mission")

    # STATE 4 -> 5: second live turn, R3 rules won -> advance to M2 lobby
    CALLS.clear()
    r = main._run_turn(TurnRequest(session_id=sid, new_player_input="A perfect accusation audit"))
    LIVE_TURNS["count"] += 1
    check(r.game_state == "mission_lobby", "won mission -> lobby for M2")
    check(r.turn.mission.title == "Earn L's attention" and r.turn.mission.status == "lobby",
          "advanced to M2 in lobby")
    check(r.turn.mission.chain_progress == "1/2", "chain progress 1/2")

    # enter M2 -> live -> win M2 -> complete
    r = main._run_turn(TurnRequest(session_id=sid, action="enter_mission", new_player_input=""))
    check(r.game_state == "live_mission", "M2 entered")
    r = main._run_turn(TurnRequest(session_id=sid, new_player_input="win it"))
    LIVE_TURNS["count"] += 1
    check(r.game_state == "complete", "final mission won -> complete")

    # defensive: calling turn with no plan and no action returns elicitation
    r = main._run_turn(TurnRequest(player_setup=json.loads(json.dumps(setup_json())),
                                   new_player_input="hi"))
    check(r.game_state == "plan_elicitation", "no-plan turn stays in elicitation")

    print("\nALL STATE CHECKS PASSED")


if __name__ == "__main__":
    run_checks()
