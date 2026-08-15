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
    CastProjectionOutput, CharacterBrainOutput, CharacterProjection, CharacterReasoning,
    CoachReply, CoachRequest, Commitment, Mission, MissionArchitectOutput, MissionDebrief,
    MissionEndOutput, NarratorOutput, NextMissionAdjustment, NpcAction, NpcEffect,
    ReconcileOutput, SkillFeedback, StatChange, StatChanges, TurnRequest, WorldEffect,
    WorldTickOutput,
)

CALLS: list[str] = []
BRAIN_MODE = {"fail": False, "commit": False}
END_MODE = {"severity": "mild"}
NARRATOR_LEAVE_ALL = {"on": False}


def _fake_model(agent):
    if agent == "caster":
        return CastProjectionOutput(characters=[
            CharacterProjection(character_id="MATSUDA", trust=4, familiarity=2,
                                respect=3, suspicion=1, rapport=4, disclosure_level=3,
                                stress=2, goal="Find a reliable witness",
                                current_problem="No witness to Kira's methods",
                                solution="Ask Jay friendly questions"),
            CharacterProjection(character_id="L", trust=1, familiarity=0,
                                respect=5, suspicion=5, rapport=0, disclosure_level=1,
                                stress=3, goal="Identify Kira",
                                current_problem="Kira acts without a trace",
                                solution="Observe without revealing himself"),
        ])
    if agent == "mission_architect":
        return MissionArchitectOutput(mission_chain=[
            Mission(id=1, title="Matsuda Bridge", description="Get a referral",
                    objective="Raise Matsuda trust to 6", reward="Matsuda's number",
                    location="Cafeteria", characters=["MATSUDA"],
                    win_conditions=[{"character": "MATSUDA", "stat": "trust", "min": 6}],
                    fail_conditions=[{"character": "MATSUDA", "stat": "trust", "max": 1}]),
            Mission(id=2, title="Earn L's attention", detail_level="outline",
                    description="Lower L's suspicion and earn his interest.",
                    location="Class 3B", characters=["L"]),
        ])
    if agent == "mission_flesher":
        return MissionArchitectOutput(mission_chain=[
            Mission(id=2, title="Earn L's attention", description="Get noticed",
                    objective="Lower L suspicion to 3", reward="L's interest",
                    location="Class 3B", characters=["L"],
                    win_conditions=[{"character": "L", "stat": "suspicion", "max": 3}],
                    fail_conditions=[{"character": "L", "stat": "suspicion", "min": 7}]),
        ])
    if agent == "scenario_director":
        return ReconcileOutput(
            revised_next=NextMissionAdjustment(
                title="Chief Soichiro's ear", description="Matsuda promised to ask Chief Soichiro about you.",
                location="NPA Headquarters", characters=["SOICHIRO"]),
            commitments=[Commitment(character="MATSUDA", target_character="SOICHIRO",
                                    about="ask Chief Soichiro about the player", status="fulfilled")],
            material_shift=True,
            shift_summary="Matsuda told you he will ask Chief Soichiro about you - your next step centers on him.",
        )
    if agent == "world_tick":
        return WorldTickOutput(actions=[
            NpcAction(character="RYUK",
                      action="floated overhead, quietly amused by the mortal's scheming",
                      effects=[NpcEffect(stat="stress", delta=1, reason="Amused by watching")]),
            NpcAction(character="LIGHT",
                      action="studied the player's background file in private",
                      effects=[NpcEffect(stat="stress", delta=1, reason="Light is uneasy about the new arrival")]),
        ])
    if agent == "coach":
        return CoachReply(reply="Matsuda trust is still 4/6. Stop pushing questions - "
                                 "label his fear first (LABELING), then use a CALIBRATED_QUESTION "
                                 "to get him to open up about the case.")
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
                memory=f"{cid} left because the player alienated me and I no longer trust them.",
                inner_thought=f"{cid} thinks this is hopeless",
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
                relationship_state=f"{cid} trusts the player moderately and is willing to open up.",
                current_interaction="The player spoke to me directly.",
            ),
            dialogue=f"{cid} speaks",
            memory=f"A stranger came up to me and said hello - I answered, we are still talking.",
            inner_thought=f"{cid} thinks",
            commitment_made=(Commitment(character=cid, target_character="SOICHIRO",
                                        about="ask Chief Soichiro about the player", status="open")
                             if BRAIN_MODE["commit"] and cid == "MATSUDA" else None),
            stat_changes=StatChanges(
                trust=StatChange(delta=1, reason="Player was friendly"),
                familiarity=StatChange(delta=1, reason="Player shared background"),
                respect=StatChange(delta=1, reason="Player showed competence"),
                suspicion=StatChange(delta=-1, reason="Player seemed genuine"),
                rapport=StatChange(delta=1, reason="Easy rapport"),
                disclosure_level=StatChange(delta=1, reason="Player opened up"),
                stress=StatChange(delta=-1, reason="Reassured"),
            ),
        )
    if agent == "narrator":
        scene_update = {"characters_left": ["MATSUDA"]} if NARRATOR_LEAVE_ALL["on"] else {}
        return NarratorOutput(narration="The cafeteria hums.",
                              where="Cafeteria",
                              why_here="Mission in progress",
                              mission_status={"current_mission_won": True},
                              scene_update=scene_update)
    raise AssertionError(f"unexpected agent {agent}")


def _mission_end_model(user):
    outcome = user.get("computed_outcome", "ongoing")
    if outcome == "won":
        return MissionEndOutput(
            severity="mild",
            action="MATSUDA hands over the referral info he promised",
            character="MATSUDA",
            world_effects=[WorldEffect(character="MATSUDA", stat="disclosure_level", delta=1,
                                       reason="Shared the referral after being won over")],
            debrief=MissionDebrief(message="Matsuda handed over the referral. Your plan moves forward.",
                                   location="Cafeteria", who_is_around=["MATSUDA"]),
            memory="A stranger kept pressing me for the referral - tonight he won me over and I shared it. I'm a little warmer to them now.",
            event_log="M1 won - MATSUDA gave up the referral.",
        )
    if END_MODE["severity"] == "harsh":
        return MissionEndOutput(
            severity="harsh",
            action="MATSUDA reports the player to L",
            character="MATSUDA",
            world_effects=[WorldEffect(character="L", stat="suspicion", delta=2,
                                       reason="Matsuda reported the player to L")],
            debrief=MissionDebrief(
                message="You failed the mission. Matsuda left in disgust and told L about you. "
                        "The rest of the chain no longer makes sense - what will you do now?",
                location="Police lobby", who_is_around=["LIGHT", "RYUK"]),
            memory="This player pushed too hard and I don't trust them - I told L about him and I won't hear him out again.",
            event_log="M1 lost - MATSUDA reported the player to L.",
        )
    return MissionEndOutput(
        severity="mild",
        action="MATSUDA leaves politely",
        character="MATSUDA",
        debrief=MissionDebrief(
            message="You failed the mission. Matsuda said 'ok, no problem' and left. "
                    "The rest of the chain no longer makes sense - what will you do now?",
            location="Police lobby", who_is_around=["LIGHT", "RYUK"]),
        memory="I said 'no problem, no hard feelings' and left - it just didn't work out between us, and I'd rather not reopen it.",
        event_log="M1 lost - MATSUDA left politely.",
    )


def fake_call_json(system, user, response_model, retries=3, agent="default", on_attempt=None):
    CALLS.append(agent)
    model = _mission_end_model(user) if agent == "mission_end" else _fake_model(agent)
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
              and seeded[cid]["stats"]["familiarity_towards_player"] == 0
              and seeded[cid]["stats"]["respect_towards_player"] == 0
              and seeded[cid]["stats"]["suspicion_towards_player"] == 0
              and seeded[cid]["stats"]["rapport_towards_player"] == 0
              and seeded[cid]["stats"]["disclosure_level"] == 0
              and seeded[cid]["stats"]["stress"] == 0
              for cid in ("L", "LIGHT", "MATSUDA", "SOICHIRO", "RYUK")),
          "all 7 stats default to 0 before the plan is projected")
    check(all(bool(seeded[cid]["relationship_dynamics"]) for cid in ("L", "LIGHT", "MATSUDA", "SOICHIRO", "RYUK")),
          "each character carries relationship_dynamics for the R2 brain")

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
    check(mat["stats"]["familiarity_towards_player"] == 2, "MATSUDA familiarity projected to 2")
    check(mat["stats"]["respect_towards_player"] == 3, "MATSUDA respect projected to 3")
    check(mat["stats"]["rapport_towards_player"] == 4, "MATSUDA rapport projected to 4")
    check(mat["stats"]["disclosure_level"] == 3, "MATSUDA disclosure projected to 3")
    check(mat["goal"] == "Find a reliable witness", "MATSUDA goal rewritten by caster")
    check(mat["solution"].startswith("Ask Jay"), "MATSUDA solution rewritten by caster")
    check(row.character_states["L"]["stats"]["suspicion_towards_player"] == 5,
          "L suspicion projected to 5")
    check(row.character_states["L"]["stats"]["disclosure_level"] == 1,
          "L disclosure projected to 1 (guarded even when engaged)")

    # Every LLM call is audited to agent_calls - including caster + mission_architect
    calls = db_module.get_agent_calls(sid)
    agents = [c.agent for c in calls]
    check("caster" in agents, f"caster logged to agent_calls (got {agents})")
    check("mission_architect" in agents, f"mission_architect logged to agent_calls (got {agents})")
    check(all(c.turn_number == 0 for c in calls), "plan-time agents logged under turn 0")
    ma_call = next(c for c in calls if c.agent == "mission_architect")
    check(bool(ma_call.system_prompt) and bool(ma_call.raw_response),
          "mission_architect audit stores prompt + raw response")

    # STATE 3 -> 4: enter mission -> no LLM, live
    r = main._run_turn(TurnRequest(session_id=sid, action="enter_mission", new_player_input=""))
    check(r.game_state == "live_mission", "enter_mission -> live_mission")
    check(CALLS == ["caster", "mission_architect"], "enter_mission still no LLM")

    # STATE 4: live turn -> R1+R2(cast only)+R3, presence synced.
    # The narrator FAKE always claims current_mission_won=True - but the real
    # verdict is deterministic (Matsuda trust needs 6). Turn 1 only reaches 5,
    # so the mission MUST stay live even though R3 said "won".
    r = main._run_turn(TurnRequest(session_id=sid, new_player_input="Hello Matsuda"))
    check(r.game_state == "live_mission", "mission stays live until the stat goal is met (R3's verdict ignored)")
    brains = [c for c in CALLS if c.startswith("brain:")]
    check(brains == ["brain:MATSUDA"], f"R2 ran ONLY for mission cast (got {brains})")

    # Context check: the brain MUST receive the player's latest message. The
    # persisted conversation is appended only after R2, so the turn payload must
    # carry new_player_input + a conversation ending with the player's words.
    brain_call = next(c for c in db_module.get_agent_calls(sid) if c.agent == "brain:MATSUDA")
    payload = brain_call.user_payload
    conv = payload.get("full_conversation_this_mission") or payload.get("conversation") or []
    check(payload.get("new_player_input") == "Hello Matsuda",
          "R2 payload carries the player's latest message (new_player_input)")
    check(conv and conv[-1].get("speaker") == "PLAYER" and conv[-1].get("text") == "Hello Matsuda",
          "R2 conversation ends with the player's latest message")
    row = db_module.get_session(sid)
    present = [cid for cid, s in row.character_states.items() if s.get("present")]
    check(present == ["MATSUDA"], f"presence synced to mission cast only (got {present})")
    check(all(not row.character_states[cid]["present"] for cid in ("L", "LIGHT", "RYUK")),
          "L/LIGHT/RYUK NOT in the room during Matsuda mission")
    mat = row.character_states["MATSUDA"]
    check(mat["stats"]["trust_towards_player"] == 5 and mat["stats"]["stress"] == 1,
          "R2 applied all 7 stat deltas (trust+1, stress-1)")
    # memory is a narrative diary line from the brain - never a raw dialogue transcript
    check(any("still talking" in m for m in mat["memory"]),
          "memory stored as narrative diary entry (not hardcoded dialogue)")
    check(not any("speaks" in m for m in mat["memory"]),
          "memory never stores raw dialogue")
    check(mat["stats"]["familiarity_towards_player"] == 3
          and mat["stats"]["respect_towards_player"] == 4
          and mat["stats"]["suspicion_towards_player"] == 0
          and mat["stats"]["rapport_towards_player"] == 5
          and mat["stats"]["disclosure_level"] == 4,
          "R2 applied familiarity/respect/rapport/disclosure deltas")

    # R2 reasoning is threaded onto the turn character for the inspector drawer
    mchar = next(c for c in r.turn.characters if c.id == "MATSUDA")
    check(bool(mchar.relationship_state and mchar.relationship_state.startswith("MATSUDA")),
          "turn character carries R2 reasoning.relationship_state")

    # STATE 4 -> 5: trust reaches 6 -> won -> advance to M2 lobby
    CALLS.clear()
    r = main._run_turn(TurnRequest(session_id=sid, new_player_input="A perfect accusation audit"))
    check(r.game_state == "mission_lobby", "stat goal reached -> mission won, lobby for M2")
    check(r.turn.mission.title == "Earn L's attention" and r.turn.mission.status == "lobby",
          "advanced to M2 in lobby")
    check(r.turn.mission.chain_progress == "1/2", "chain progress 1/2")
    check("mission_end" in CALLS, "R4 ran on mission win (payoff decided)")
    row = db_module.get_session(sid)
    check(any("M1 won" in e for e in row.mission_state.get("events", [])),
          "win payoff logged as a world event")
    check(row.character_states["MATSUDA"]["stats"]["disclosure_level"] >= 5,
          "win payoff applied (reward info delivered on top of turn deltas)")
    mem = row.character_states["MATSUDA"]["memory"]
    check(len(mem) == 1 and "referral" in mem[0],
          "R4 rewrites MATSUDA memory into one merged summary (win payoff folded in)")
    check(row.mission_state["current"]["detail_level"] == "outline",
          "M2 kept as a rough OUTLINE after M1 won (fleshed later, not pre-written)")
    check(row.mission_state.get("reconcile_shift") is None,
          "no world shift without open commitments (no scenario_director call)")

    # R7 world tick: non-cast NPCs kept living their lives during the mission
    check("world_tick" in CALLS, "R7 ran on mission win (NPCs did things off-screen)")
    check(any(e.startswith("Meanwhile,") for e in row.mission_state.get("events", [])),
          "off-screen NPC actions logged as 'Meanwhile' world events")
    check(row.character_states["RYUK"]["stats"]["stress"] >= 1,
          "world tick persisted a stat drift on a non-cast NPC (Ryuk)")
    check(row.character_states["L"]["stats"]["suspicion_towards_player"] == 5,
          "world tick never touched L (next mission's stats stay fair)")

    # Coach chat: player can ask the Coach anything; it reads the live state
    coach_resp = main.api_coach(CoachRequest(
        session_id=sid,
        message="What concept should I use to win?",
        history=[{"role": "player", "content": "Hi"},
                 {"role": "coach", "content": "Ask me anything about the state."}],
    ))
    check(coach_resp["reply"] and "LABELING" in coach_resp["reply"],
          "coach answers with a concrete skill from the bible")
    calls = db_module.get_agent_calls(sid)
    check(any(c.agent == "coach" for c in calls), "coach Q&A audited to agent_calls")

    # enter M2 -> the OUTLINE is fleshed out at entry time (mission_flesher)
    CALLS.clear()
    r = main._run_turn(TurnRequest(session_id=sid, action="enter_mission", new_player_input=""))
    check(r.game_state == "live_mission", "M2 entered")
    check("mission_flesher" in CALLS, "outline mission fleshed on entry (mission_flesher ran)")
    row = db_module.get_session(sid)
    check(row.mission_state["current"]["detail_level"] == "detailed"
          and row.mission_state["current"]["win_conditions"],
          "M2 now fully detailed with stat conditions after fleshing")
    r = main._run_turn(TurnRequest(session_id=sid, new_player_input="engage L"))
    check(r.game_state == "live_mission", "M2 turn 1 stays live (suspicion 4 > 3)")
    r = main._run_turn(TurnRequest(session_id=sid, new_player_input="disarm L"))
    check(r.game_state == "complete", "M2 suspicion hits 3 -> complete")

    # ---- COMMITMENT PATH: a dialogue promise reshapes the next mission ----
    r = main._run_turn(TurnRequest(player_setup=json.loads(json.dumps(setup_json())),
                                   new_player_input="", action="start"))
    c_sid = r.session_id
    main._run_turn(TurnRequest(session_id=c_sid, action="submit_plan",
                               plan_text="Get close to Matsuda"))
    main._run_turn(TurnRequest(session_id=c_sid, action="enter_mission", new_player_input=""))
    BRAIN_MODE["commit"] = True
    main._run_turn(TurnRequest(session_id=c_sid, new_player_input="Promise Matsuda help"))
    row = db_module.get_session(c_sid)
    check(any(c["about"] == "ask Chief Soichiro about the player" for c in row.mission_state.get("commitments", [])),
          "dialogue promise captured into the commitments ledger")
    check(any("committed" in e for e in row.mission_state.get("events", [])),
          "new commitment logged as a world event")
    # WIN with an open commitment -> R6 Scenario Director revises M2.
    # (The same promise fires again on this turn but is deduped, so the ledger
    # still holds exactly one open entry.)
    CALLS.clear()
    main._run_turn(TurnRequest(session_id=c_sid, new_player_input="A perfect accusation audit"))
    check("scenario_director" in CALLS, "R6 ran on win because an open commitment exists")
    check("mission_end" in CALLS, "R4 still ran on mission win")
    row = db_module.get_session(c_sid)
    check(len([c for c in row.mission_state.get("commitments", []) if c["about"] == "ask Chief Soichiro about the player"]) == 1,
          "commitment deduped by who+what (no duplicate ledger rows)")
    nxt = [m for m in row.mission_state["chain"] if m["id"] == 2][0]
    check(nxt["title"] == "Chief Soichiro's ear", "R6 rewrote M2 title to follow the promise")
    check(nxt["characters"] == ["SOICHIRO"], "R6 re-cast M2 around the promised target")
    check(row.mission_state["current"]["detail_level"] == "outline",
          "revised M2 still an outline until entered")
    check(any("WORLD SHIFT" in e for e in row.mission_state.get("events", [])),
          "material shift broadcast as a world event")
    # lobby response surfaces the shift for the player to see
    r = main._run_turn(TurnRequest(session_id=c_sid, new_player_input=""))
    check(r.reconcile_shift is not None and "Chief Soichiro" in r.reconcile_shift,
          "lobby surfaces the world shift (reconcile_shift)")
    # commitments survive a voluntary re-plan
    main._run_turn(TurnRequest(session_id=c_sid, action="revise_plan", new_player_input=""))
    row = db_module.get_session(c_sid)
    check(row.mission_state.get("plan_flopped") is True and row.mission_state.get("chain") == [],
          "revise_plan voids the chain like a flop")
    check(len(row.mission_state.get("commitments", [])) == 1,
          "commitments persist across a plan revision (loose coupling)")
    check(row.mission_state.get("reconcile_shift") is None,
          "revise_plan clears the stale shift banner")
    BRAIN_MODE["commit"] = False

    # defensive: calling turn with no plan and no action returns elicitation
    r = main._run_turn(TurnRequest(player_setup=json.loads(json.dumps(setup_json())),
                                   new_player_input="hi"))
    check(r.game_state == "plan_elicitation", "no-plan turn stays in elicitation")

    # ---- FAIL PATH (HARSH): the character reports the player -> plan flops ----
    r = main._run_turn(TurnRequest(player_setup=json.loads(json.dumps(setup_json())),
                                   new_player_input="", action="start"))
    harsh_sid = r.session_id
    main._run_turn(TurnRequest(session_id=harsh_sid, action="submit_plan",
                               plan_text="Get close to Matsuda"))
    main._run_turn(TurnRequest(session_id=harsh_sid, action="enter_mission", new_player_input=""))
    CALLS.clear()
    BRAIN_MODE["fail"] = True
    END_MODE["severity"] = "harsh"
    r = main._run_turn(TurnRequest(session_id=harsh_sid, new_player_input="Rude outburst"))
    BRAIN_MODE["fail"] = False
    check(r.game_state == "plan_revision", "failed mission -> plan_revision (not a retry lobby)")
    check(r.debrief is not None and "what will you do now" in r.debrief.message,
          "failure debrief asks the player for a new plan")
    check("mission_end" in CALLS, "R4 ran on mission failure")
    check("world_tick" in CALLS, "R7 ran on mission failure too (world keeps moving)")
    row = db_module.get_session(harsh_sid)
    check(row.mission_state.get("plan_flopped") is True,
          "plan marked as flopped (chain voided)")
    check(row.mission_state.get("current") is None and row.mission_state.get("chain") == [],
          "failed chain cleared - remaining missions no longer apply")
    check(any("reported" in e for e in row.mission_state.get("events", [])),
          "harsh consequence logged as a world event")
    check(row.character_states["L"]["stats"]["suspicion_towards_player"] == 7,
          "harsh consequence: L suspicion raised by 2 (Matsuda reported you)")
    check(row.character_states["MATSUDA"]["stats"]["trust_towards_player"] == 0,
          "trust cratered (4 - 4) - the damage persists")
    mem = row.character_states["MATSUDA"]["memory"]
    check(len(mem) == 1 and "I told L" in mem[0],
          "R4 rewrites Matsuda memory into ONE merged summary (reported you)")
    present = [cid for cid, s in row.character_states.items() if s.get("present")]
    check(present == ["LIGHT", "RYUK"] and not row.character_states["MATSUDA"]["present"],
          "presence synced to debrief: Matsuda left, others around")

    # PLAN REVISION: a new plan rebuilds the chain WITHOUT resetting the cast
    CALLS.clear()
    r = main._run_turn(TurnRequest(session_id=harsh_sid, action="submit_plan",
                                   plan_text="Repair Matsuda's trust before touching L"))
    check(r.game_state == "mission_lobby", "revised plan -> mission lobby")
    check(CALLS == ["mission_architect"],
          f"revision skips cast re-projection - stats/memory survive (calls={CALLS})")
    check(len(r.mission_chain) == 2, "revised plan built a fresh mission chain")
    row = db_module.get_session(harsh_sid)
    check(row.mission_state.get("plan_flopped") is False, "plan_flopped cleared after revision")
    check(row.character_states["MATSUDA"]["stats"]["trust_towards_player"] == 0,
          "Matsuda STILL distrusts the player after revision (no reset)")
    mem = row.character_states["MATSUDA"]["memory"]
    check(len(mem) == 1 and "I told L" in mem[0],
          "Matsuda's rewritten memory survives into the new plan")
    r = main._run_turn(TurnRequest(session_id=harsh_sid, action="enter_mission", new_player_input=""))
    check(r.game_state == "live_mission", "revised plan -> new mission entered")

    # ---- FAIL PATH (MILD): polite leave, no permanent world damage ----
    r = main._run_turn(TurnRequest(player_setup=json.loads(json.dumps(setup_json())),
                                   new_player_input="", action="start"))
    mild_sid = r.session_id
    main._run_turn(TurnRequest(session_id=mild_sid, action="submit_plan",
                               plan_text="Get close to Matsuda"))
    main._run_turn(TurnRequest(session_id=mild_sid, action="enter_mission", new_player_input=""))
    END_MODE["severity"] = "mild"
    BRAIN_MODE["fail"] = True
    r = main._run_turn(TurnRequest(session_id=mild_sid, new_player_input="Rude outburst"))
    BRAIN_MODE["fail"] = False
    row = db_module.get_session(mild_sid)
    check(r.game_state == "plan_revision", "mild failure also -> plan_revision")
    check(row.character_states["L"]["stats"]["suspicion_towards_player"] == 5,
          "mild consequence: L suspicion unchanged (no report to L)")
    check(any("no problem" in m for m in row.character_states["MATSUDA"]["memory"]),
          "mild consequence: character leaves politely (memory records it)")

    # ---- EMPTY ROOM: everyone in the cast left -> mission ends as a failure ----
    # The narrator reports the sole cast member leaving. Even though the stats
    # say the mission is still winnable, no one is there to talk to.
    r = main._run_turn(TurnRequest(player_setup=json.loads(json.dumps(setup_json())),
                                   new_player_input="", action="start"))
    empty_sid = r.session_id
    main._run_turn(TurnRequest(session_id=empty_sid, action="submit_plan",
                               plan_text="Get close to Matsuda"))
    main._run_turn(TurnRequest(session_id=empty_sid, action="enter_mission", new_player_input=""))
    NARRATOR_LEAVE_ALL["on"] = True
    r = main._run_turn(TurnRequest(session_id=empty_sid, new_player_input="Hello"))
    NARRATOR_LEAVE_ALL["on"] = False
    check(r.game_state == "plan_revision",
          "all cast left -> empty room forces the mission to fail")
    check("mission_end" in CALLS, "R4 resolves the empty-room failure")
    row = db_module.get_session(empty_sid)
    check(row.mission_state.get("plan_flopped") is True,
          "empty-room failure flops the plan like any other failure")
    present = [cid for cid, s in row.character_states.items() if s.get("present")]
    check(present == ["LIGHT", "RYUK"],
          "presence synced after empty room (Matsuda gone, others around)")

    print("\nALL STATE CHECKS PASSED")


if __name__ == "__main__":
    run_checks()
