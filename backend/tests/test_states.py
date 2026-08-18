"""State-machine regression test for the 3-state game loop (no rigid missions).

Setup -> World (declare action) -> Live Scene -> World (declare action) -> ...

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
    ActionFeasibility,
    CharacterBrainOutput,
    CharacterReasoning,
    CoachReply,
    CoachRequest,
    Commitment,
    Mission,
    MissionDebrief,
    PlayerProfile,
    SceneDirectionOutput,
    SkillFeedback,
    StatChange,
    StatChanges,
    TurnRequest,
    WorldTickOutput,
)
from app.types import NpcAction, NpcEffect  # noqa: E402

CALLS: list[str] = []
last_r2_user: dict = {}
BRAIN_MODE = {"fail": False, "commit": False, "stall": False}
FEASIBILITY_MODE = {"blocked": False}
SCENE_EXIT_TOOL = {"on": False}
DIRECT_MODE = {
    "addressed_to": "MATSUDA",
    "speaker_order": ["MATSUDA", "SOICHIRO"],
    "stay_silent": [],
}


def _fake_model(agent, user=None):
    if agent == "feasibility_check":
        if FEASIBILITY_MODE["blocked"]:
            return ActionFeasibility(
                feasible=False,
                reason="Chief Yagami is extremely selective about who he meets - "
                       "you have no introduction and don't know when he is free.",
                suggestions=[
                    "Talk to Matsuda in the NPA cafeteria - he sees the Chief daily",
                    "Approach Soichiro's office with an introduction from a trusted colleague",
                ],
            )
        return ActionFeasibility(feasible=True, reason="This is within your reach.")
    if agent == "mission_architect":
        action_lower = (user.get("Player_action") or user.get("player_action") or "").lower()
        chars = []
        if "matsuda" in action_lower:
            chars.append("MATSUDA")
        if "soichiro" in action_lower:
            chars.append("SOICHIRO")
        if not chars:
            chars = ["MATSUDA"]
        return Mission(
            id=1,
            title="Gain Trust",
            description="Talk to the characters and build rapport.",
            characters=chars,
            location="NPA Cafeteria",
            objective="Build trust with the target characters.",
            reward="They agree to help you.",
            win_conditions=[{"character": chars[0], "stat": "trust", "min": 5}],
            fail_conditions=[{"character": chars[0], "stat": "suspicion", "max": 8}],
        )
    if agent == "mission_eval":
        return MissionDebrief(
            outcome="won",
            message="Matsuda trusts you now and offered to introduce you to Chief Yagami.",
            location="NPA Cafeteria",
            who_is_around=["MATSUDA"],
        )
    if agent == "scene_director":
        return SceneDirectionOutput(
            addressed_to=DIRECT_MODE["addressed_to"],
            speaker_order=DIRECT_MODE["speaker_order"],
            stay_silent=DIRECT_MODE["stay_silent"],
        )
    if agent == "world_tick":
        return WorldTickOutput(actions=[
            NpcAction(character="RYUK",
                      action="floated overhead, quietly amused",
                      effects=[NpcEffect(stat="stress", delta=1, reason="Amused by watching")]),
            NpcAction(character="LIGHT",
                      action="studied the player's background file",
                      effects=[NpcEffect(stat="stress", delta=1, reason="Uneasy about new arrival")]),
        ])
    if agent == "coach":
        return CoachReply(reply="Trust is building. Use LABELING to name his fear, "
                                 "then a CALIBRATED_QUESTION to open him up.")
    if agent == "listener":
        return SkillFeedback(did_use_concept=False)
    if agent.startswith("brain:"):
        cid = agent.split(":", 1)[1]
        if BRAIN_MODE["fail"] and cid == "MATSUDA":
            return CharacterBrainOutput(
                character_id=cid,
                reasoning=CharacterReasoning(
                    personality="Warm and eager",
                    current_goal="Win the player over",
                    current_problem="Prove myself",
                    current_strategy="Be friendly",
                    relationship_state=f"{cid} has lost faith and wants out.",
                    current_interaction="The player alienated me.",
                ),
                dialogue=f"{cid} gets frustrated and leaves",
                memory=f"{cid} left because the player alienated me.",
                inner_thought=f"{cid} thinks this is hopeless",
                tool_calls=["end_conversation"] if SCENE_EXIT_TOOL["on"] else [],
                stat_changes=StatChanges(
                    trust=StatChange(delta=-4, reason="Player was off-putting"),
                    suspicion=StatChange(delta=2, reason="Now distrustful"),
                    stress=StatChange(delta=3, reason="Frustrated"),
                ),
            )
        return CharacterBrainOutput(
            character_id=cid,
            reasoning=CharacterReasoning(
                personality="Warm and eager",
                current_goal="Win the player over",
                current_problem="Prove myself",
                current_strategy="Be friendly",
                relationship_state=f"{cid} trusts the player moderately.",
                current_interaction="The player spoke to me directly.",
            ),
            dialogue=f"{cid} speaks",
            memory=f"A stranger came up to me and said hello.",
            inner_thought=f"{cid} thinks",
            tool_calls=["end_conversation"] if SCENE_EXIT_TOOL["on"] else [],
            commitment_made=(Commitment(character=cid, target_character="SOICHIRO",
                                        about="ask Chief Soichiro about the player", status="open")
                             if BRAIN_MODE["commit"] and cid == "MATSUDA" else None),
            stat_changes=StatChanges(
                trust=StatChange(delta=0 if BRAIN_MODE["stall"] else 1, reason="Player was friendly"),
                familiarity=StatChange(delta=0 if BRAIN_MODE["stall"] else 1, reason="Player shared background"),
                respect=StatChange(delta=0 if BRAIN_MODE["stall"] else 1, reason="Player showed competence"),
                suspicion=StatChange(delta=0 if BRAIN_MODE["stall"] else -1, reason="Player seemed genuine"),
                rapport=StatChange(delta=0 if BRAIN_MODE["stall"] else 1, reason="Easy rapport"),
                disclosure_level=StatChange(delta=0 if BRAIN_MODE["stall"] else 1, reason="Player opened up"),
                stress=StatChange(delta=0 if BRAIN_MODE["stall"] else -1, reason="Reassured"),
            ),
        )
    raise AssertionError(f"unexpected agent {agent}")


def fake_call_json(system, user, response_model, retries=3, agent="default", on_attempt=None):
    CALLS.append(agent)
    if agent.startswith("brain:"):
        last_r2_user["payload"] = user
    model = _fake_model(agent, user)
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
    # ---- SETUP: player submits character + strategic plan ----
    r = main._run_turn(TurnRequest(player_setup=json.loads(json.dumps(setup_json())),
                                   new_player_input="", action="setup",
                                   plan_text="Infiltrate the Task Force and find Kira"))
    sid = r.session_id
    check(r.game_state == "world", "setup -> world")
    check(r.world is not None and len(r.world.autonomous_players) == 5, "world bible loaded")
    check(CALLS == [], f"NO LLM on setup (calls={CALLS})")
    check(r.strategic_plan == "Infiltrate the Task Force and find Kira",
          "strategic plan persisted")

    # Stats seeded at 0
    world = main.load_world_bible("Death Note")
    seeded = main.seed_character_states(world)
    check(all(seeded[cid]["stats"]["trust_towards_player"] == 0
              for cid in ("L", "LIGHT", "MATSUDA", "SOICHIRO", "RYUK")),
          "all stats default to 0")

    # ---- DECLARE ACTION: feasibility check -> live scene ----
    r = main._run_turn(TurnRequest(session_id=sid, action="declare_action",
                                   new_player_input="I want to talk to Matsuda in the cafeteria"))
    check(r.game_state == "live_scene", "declare_action (feasible) -> live_scene")
    check("feasibility_check" in CALLS, "feasibility check ran")
    check(r.feasibility is not None and r.feasibility.feasible, "action is feasible")
    row = db_module.get_session(sid)
    present = [cid for cid, s in row.character_states.items() if s.get("present")]
    check("MATSUDA" in present, "MATSUDA is present after declaring action")

    # ---- LIVE SCENE: R1 + Scene Director + R2 + R3 ----
    CALLS.clear()
    r = main._run_turn(TurnRequest(session_id=sid, new_player_input="Hello Matsuda"))
    check(r.game_state == "live_scene", "scene turn stays live")
    check("listener" in CALLS, "R1 listener ran")
    brains = [c for c in CALLS if c.startswith("brain:")]
    check(len(brains) >= 1, f"R2 brain(s) ran (got {brains})")
    # check("narrator" in CALLS, "R3 narrator ran")  # R3 temporarily disabled

    # R2 payload contains player's latest message
    brain_call = next(c for c in db_module.get_agent_calls(sid) if c.agent.startswith("brain:"))
    payload = brain_call.user_payload
    check(payload.get("new_player_input") == "Hello Matsuda",
          "R2 payload carries player's latest message")
    conv = payload.get("full_conversation_this_scene") or payload.get("full_conversation_this_mission") or []
    check(conv and conv[-1].get("text") == "Hello Matsuda",
          "R2 conversation ends with player's latest message")

    # Stats updated
    row = db_module.get_session(sid)
    mat = row.character_states["MATSUDA"]
    check(mat["stats"]["trust_towards_player"] >= 1, "MATSUDA trust increased after friendly turn")

    # Conversation persisted
    check(any(m.get("speaker") == "PLAYER" and "Hello Matsuda" in m.get("text", "")
              for m in row.conversation),
          "player message persisted in conversation")

    # ---- DECLARE ACTION (blocked): feasibility check rejects ----
    FEASIBILITY_MODE["blocked"] = True
    r = main._run_turn(TurnRequest(session_id=sid, action="declare_action",
                                   new_player_input="Meet Chief Yagami directly"))
    FEASIBILITY_MODE["blocked"] = False
    check(r.game_state == "world", "blocked action stays in world")
    check(r.feasibility is not None and not r.feasibility.feasible, "action blocked")
    check(len(r.feasibility.suggestions) >= 1, "suggestions provided when blocked")

    # ---- WORLD TICK: runs between scenes ----
    check(any(e.startswith("Meanwhile,") for e in r.events),
          "world tick logged Meanwhile events")
    row = db_module.get_session(sid)
    check(row.character_states["RYUK"]["stats"]["stress"] >= 1,
          "world tick persisted stat drift on non-scene NPC")

    # ---- COMMITMENT PATH: dialogue promise captured ----
    r = main._run_turn(TurnRequest(player_setup=json.loads(json.dumps(setup_json())),
                                   new_player_input="", action="setup",
                                   plan_text="Get close to Matsuda"))
    c_sid = r.session_id
    main._run_turn(TurnRequest(session_id=c_sid, action="declare_action",
                               new_player_input="Talk to Matsuda"))
    BRAIN_MODE["commit"] = True
    main._run_turn(TurnRequest(session_id=c_sid, new_player_input="I promise to help"))
    BRAIN_MODE["commit"] = False
    row = db_module.get_session(c_sid)
    check(any(c["about"] == "ask Chief Soichiro about the player"
              for c in row.mission_state.get("commitments", [])),
          "dialogue promise captured into commitments ledger")
    check(any("committed" in e for e in row.mission_state.get("events", [])),
          "commitment logged as world event")

    # ---- COACH: player can ask the Coach anything ----
    coach_resp = main.api_coach(CoachRequest(
        session_id=sid,
        message="What should I do?",
        history=[],
    ))
    check(coach_resp["reply"] and "LABELING" in coach_resp["reply"],
          "coach answers with a concrete skill")

    # ---- EMPTY ROOM: everyone leaves -> back to world ----
    r = main._run_turn(TurnRequest(player_setup=json.loads(json.dumps(setup_json())),
                                   new_player_input="", action="setup",
                                   plan_text="Get close to Matsuda"))
    empty_sid = r.session_id
    main._run_turn(TurnRequest(session_id=empty_sid, action="declare_action",
                                new_player_input="Talk to Matsuda"))
    SCENE_EXIT_TOOL["on"] = True
    r = main._run_turn(TurnRequest(session_id=empty_sid, new_player_input="Hello"))
    SCENE_EXIT_TOOL["on"] = False
    check(r.game_state == "world", "all left -> back to world")
    row = db_module.get_session(empty_sid)
    present = [cid for cid, s in row.character_states.items() if s.get("present")]
    check("MATSUDA" not in present, "MATSUDA no longer present after leaving")

    # ---- TURN-CAP: stalled scene wraps up ----
    r = main._run_turn(TurnRequest(player_setup=json.loads(json.dumps(setup_json())),
                                   new_player_input="", action="setup",
                                   plan_text="Get close to Matsuda"))
    cap_sid = r.session_id
    main._run_turn(TurnRequest(session_id=cap_sid, action="declare_action",
                               new_player_input="Talk to Matsuda"))
    BRAIN_MODE["stall"] = True
    last_state = "live_scene"
    for i in range(16):
        r = main._run_turn(TurnRequest(session_id=cap_sid, new_player_input="small talk"))
        if r.game_state != "live_scene":
            last_state = r.game_state
            break
    BRAIN_MODE["stall"] = False
    check(last_state == "world",
          f"stalled scene ends via turn cap, no softlock (ended as {last_state})")

    # ---- SCENE DIRECTOR: 2-char room, addressed first ----
    r = main._run_turn(TurnRequest(player_setup=json.loads(json.dumps(setup_json())),
                                   new_player_input="", action="setup",
                                   plan_text="Get close to Matsuda and Soichiro"))
    scene_sid = r.session_id
    main._run_turn(TurnRequest(session_id=scene_sid, action="declare_action",
                               new_player_input="Talk to Matsuda and Soichiro"))
    DIRECT_MODE["addressed_to"] = "MATSUDA"
    DIRECT_MODE["speaker_order"] = ["SOICHIRO", "MATSUDA"]
    DIRECT_MODE["stay_silent"] = []
    CALLS.clear()
    r = main._run_turn(TurnRequest(session_id=scene_sid,
                                   new_player_input="Matsuda, what do you think?"))
    check("scene_director" in CALLS, "Scene Director ran for 2-char room")
    brains = [c for c in CALLS if c.startswith("brain:")]
    check(brains == ["brain:MATSUDA", "brain:SOICHIRO"],
          f"addressed MATSUDA speaks FIRST despite director order (got {brains})")
    check(last_r2_user.get("payload", {}).get("directed_to_you") is False,
          "SOICHIRO knows the player spoke to MATSUDA, not him")
    before = last_r2_user.get("payload", {}).get("this_turn_before_you") or []
    check(any("MATSUDA" in (m.get("speaker") or "") for m in before),
          "second speaker SEES what the first said")

    # ---- SCENE DIRECTOR: silencing ----
    DIRECT_MODE["speaker_order"] = ["MATSUDA"]
    DIRECT_MODE["stay_silent"] = ["SOICHIRO"]
    BRAIN_MODE["stall"] = True
    CALLS.clear()
    soichiro_before = dict(db_module.get_session(scene_sid)
                           .character_states["SOICHIRO"]["stats"])
    r = main._run_turn(TurnRequest(session_id=scene_sid, new_player_input="Only you, Matsuda"))
    BRAIN_MODE["stall"] = False
    brains = [c for c in CALLS if c.startswith("brain:")]
    check(brains == ["brain:MATSUDA"],
          f"silenced SOICHIRO gets NO brain call (got {brains})")
    row = db_module.get_session(scene_sid)
    check(row.character_states["SOICHIRO"]["stats"] == soichiro_before,
          "silenced character's stats frozen")
    # mem = row.character_states["SOICHIRO"]["memory"]
    # check(any("stayed quiet" in m for m in mem),
    #       "narrator wrote observer memory for silent character")  # R3 disabled

    # ---- HARSH FAIL: character walks out, scene ends ----
    r = main._run_turn(TurnRequest(player_setup=json.loads(json.dumps(setup_json())),
                                   new_player_input="", action="setup",
                                   plan_text="Get close to Matsuda"))
    harsh_sid = r.session_id
    main._run_turn(TurnRequest(session_id=harsh_sid, action="declare_action",
                                new_player_input="Talk to Matsuda"))
    BRAIN_MODE["fail"] = True
    SCENE_EXIT_TOOL["on"] = True
    r = main._run_turn(TurnRequest(session_id=harsh_sid, new_player_input="Rude outburst"))
    BRAIN_MODE["fail"] = False
    SCENE_EXIT_TOOL["on"] = False
    check(r.game_state == "world", "harsh fail -> back to world")
    row = db_module.get_session(harsh_sid)
    check(row.character_states["MATSUDA"]["stats"]["trust_towards_player"] == 0,
          "trust cratered after harsh fail")
    mem = row.character_states["MATSUDA"]["memory"]
    check(any("left" in m.lower() or "frustrated" in m.lower() for m in mem),
          "MATSUDA memory records the fallout")

    print("\nALL STATE CHECKS PASSED")


# ── Player Profile Tests ────────────────────────────────────────────

def test_profile_init():
    """Setup creates a player_profile with initial values."""
    r = main._run_turn(TurnRequest(player_setup=json.loads(json.dumps(setup_json())),
                                   new_player_input="", action="setup",
                                   plan_text="Infiltrate NPA"))
    sid = r.session_id
    row = db_module.get_session(sid)
    p = row.mission_state.get("player_profile", {})
    check(isinstance(p, dict), "profile is a dict")
    check(p.get("status") == "Student", "initial status is Student")
    check(p.get("cash") == 50000, "initial cash is 50000")
    check(p.get("resources") == [], "initial resources empty")
    check(p.get("knowledge") == [], "initial knowledge empty")


def test_profile_in_turn_response():
    """TurnResponse includes player_profile."""
    r = main._run_turn(TurnRequest(player_setup=json.loads(json.dumps(setup_json())),
                                   new_player_input="", action="setup",
                                   plan_text="Infiltrate NPA"))
    check(r.player_profile is not None, "turn response has player_profile")
    check(r.player_profile.status == "Student", "profile status in response")


def test_profile_update_on_turn():
    """After a turn, profile should still be present (apply_profile_updates ran)."""
    r = main._run_turn(TurnRequest(player_setup=json.loads(json.dumps(setup_json())),
                                   new_player_input="", action="setup",
                                   plan_text="Infiltrate NPA"))
    sid = r.session_id
    main._run_turn(TurnRequest(session_id=sid, action="declare_action",
                               new_player_input="Talk to Matsuda"))
    r2 = main._run_turn(TurnRequest(session_id=sid, new_player_input="Hello there"))
    check(r2.player_profile is not None, "profile still present after live turn")
    check(r2.player_profile.status == "Student", "profile status preserved")


def test_profile_updates():
    """If R2 outputs profile_updates, the profile gets updated."""
    original_call_json = llm_caller.call_json

    def _fake_with_updates(system, user, schema, agent="", on_attempt=None):
        if agent == "listener":
            return SkillFeedback(did_use_concept=False)
        if agent.startswith("brain:"):
            cid = agent.split(":", 1)[1]
            return CharacterBrainOutput(
                character_id=cid,
                reasoning=CharacterReasoning(
                    personality="Warm", current_goal="Help", current_problem="None",
                    current_strategy="Be friendly", relationship_state="OK",
                    current_interaction="Talking",
                ),
                dialogue=f"{cid} says something",
                memory="talked",
                inner_thought="thinking",
                tool_calls=[],
                stat_changes=StatChanges(),
                profile_updates={"resources": ["NPA badge"], "knowledge": ["L is in Tokyo"]},
            )
        if agent == "feasibility_check":
            return ActionFeasibility(feasible=True, reason="action ok")
        if agent == "scene_director":
            return SceneDirectionOutput(speakers=[cid] if cid else [], silenced=[], reason="good")
        if agent == "world_tick":
            from app.types import WorldTickOutput
            return WorldTickOutput(tick=[], meanwhile_events=[], scene_hooks=[])
        if agent == "mission_architect":
            return None
        raise AssertionError(f"unexpected agent {agent}")

    llm_caller.call_json = _fake_with_updates
    try:
        r = main._run_turn(TurnRequest(player_setup=json.loads(json.dumps(setup_json())),
                                       new_player_input="", action="setup",
                                       plan_text="Infiltrate NPA"))
        sid = r.session_id
        main._run_turn(TurnRequest(session_id=sid, action="declare_action",
                                   new_player_input="Talk to Matsuda"))
        r2 = main._run_turn(TurnRequest(session_id=sid, new_player_input="Hello"))
        row = db_module.get_session(sid)
        p = row.mission_state.get("player_profile", {})
        check("NPA badge" in (p.get("resources") or []),
              "profile resources includes NPA badge from R2")
        check("L is in Tokyo" in (p.get("knowledge") or []),
              "profile knowledge includes fact from R2")
    finally:
        llm_caller.call_json = original_call_json


if __name__ == "__main__":
    run_checks()
    test_profile_init()
    test_profile_in_turn_response()
    test_profile_update_on_turn()
    test_profile_updates()
    print("\nALL PROFILE CHECKS PASSED")
