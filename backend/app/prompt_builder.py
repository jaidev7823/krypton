"""Prompt builders for the 3 simulation LLM calls (Piece 3).

Each builder returns ``(system_prompt, user_payload)``. The payload is the
exact JSON the LLM must reason over; the system prompt enforces the role
and output schema. The LLM returns ONLY JSON, validated in llm_caller.py.

R1 Listener/Teacher   - judge the player's last message against the skill book
R2 Character Brain    - one autonomous character reacts (run per character)
R3 Narrator/Manager   - environment narration + mission chain progression
"""

from __future__ import annotations

import json
from typing import Any

from .types import PlayerSetup, SkillBible, WorldBible


def _dump(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=1, default=str)


# ---------------------------------------------------------------------------
# R0-Cast: Character Projection (runs once per plan, before mission design)
# ---------------------------------------------------------------------------

def build_cast_prompt(
    player: PlayerSetup,
    world: WorldBible,
) -> tuple[str, dict]:
    system = (
        "You are the Cast Projection Director for a living world negotiation game.\n"
        "Your only job: predict how every canon character's plan will be for this world based on canon.\n"
        "Other charachter do not know what player planned so do not make charachter plans based on player's plan.\n"
        "Rules:\n"
        "- Stats default to 0 (neutral). Raise a stat ONLY where the player's personality plausibly provokes it if there is chance charachter knows him: "
        "trust if the plan serves the character's interests, suspicion if it threatens them, "
        "stress if the plan is risky for them.\n"
        "- Stats are 0-10 (0 = none, 10 = maximum).\n"
        "- Rewrite each character's goal and starting plan to reflect how they would engage THIS player given their "
        "personality, background and stated plan - grounded in canon.\n"
        "- Keep the character's canon identity and voice. Never invent new characters.\n"
        "- Output ONLY JSON matching the schema exactly. no markdown."
    )
    user = {
        "task": "Project each character's initial stats, goal and plan based on there profile and canon story.",
        "player": player.model_dump(mode="json"),
        "player_own_plan": player.own_plan,
        "world_lore": world.model_dump(mode="json"),
        "output_schema": {
            "characters": [
                {
                    "character_id": "bible character id",
                    "trust": "int 0-10",
                    "suspicion": "int 0-10",
                    "stress": "int 0-10",
                    "goal": "str - updated goal given the player's plan",
                    "plan_objective": "str - what the character now wants from the player",
                    "plan": "str - how the character will counter/engage the player",
                    "Knowledge": "str - what this characher knows and what he don't know about this world",
                    "plan_status": "'ongoing' | 'succeeded' | 'failed' | 'changed'",
                }
            ]
        },
    }
    return system, user


# ---------------------------------------------------------------------------
# R0: Mission Architect (runs once per player plan)
# ---------------------------------------------------------------------------

def build_r0_prompt(
    player: PlayerSetup,
    world: WorldBible,
    character_states: dict[str, Any] | None = None,
) -> tuple[str, dict]:
    system = (
        "You are the Mission Architect for a living world negotiation game.\n"
        "Your only job is to turn the PLAYER'S OWN plan into a concrete mission chain.\n"
        "Rules:\n"
        "- Break the player's own_plan into 4-5 winnable missions that lead to their goal.\n"
        "- Each mission has a location, a clear objective with a stat goal, a reward, and the exact bible characters present.\n"
        "- 'characters' MUST only use ids from the world bible's autonomous_players. Never invent characters.\n"
        "- Missions escalate: earlier missions are low-stakes (a single character), later ones raise the stakes.\n"
        "- Read current_character_states: those are the LIVE stats/goals/plans AFTER the player's plan was projected. "
        "Mission objectives must reference the current values (e.g. 'Raise Matsuda trust from 2 to 7').\n"
        "- Do NOT write dialogue or narration. Missions are objectives, not story.\n"
        "- Output ONLY JSON matching the schema exactly. No extra text, no markdown."
    )
    live = {}
    if character_states:
        for cid, s in character_states.items():
            live[cid] = {
                "goal": s.get("goal", ""),
                "plan": s.get("plan", {}),
                "stats": s.get("stats", {}),
            }
    user = {
        "task": "Design a 4-5 mission chain that makes the player's plan playable.",
        "player": player.model_dump(mode="json"),
        "player_own_plan": player.own_plan,
        "world_lore": world.model_dump(mode="json"),
        "available_characters": [c.id for c in world.autonomous_players],
        "current_character_states": live,
        "output_schema": {
            "mission_chain": [
                {
                    "id": "int - 1-based sequence number",
                    "title": "str - short mission name",
                    "description": "str - what must happen in-world",
                    "why_important": "str - how it serves the player's goal",
                    "location": "str - in-world place",
                    "characters": ["bible character ids present in this mission"],
                    "objective": "str - measurable goal e.g. 'Raise Matsuda trust from 2 to 7'",
                    "reward": "str - what the player gains on success",
                }
            ]
        },
    }
    return system, user


# ---------------------------------------------------------------------------
# R1: Listener / Teacher
# ---------------------------------------------------------------------------

def build_r1_prompt(
    skill_bible: SkillBible,
    player: PlayerSetup,
    mission_context: dict[str, Any],
    new_player_input: str,
    conversation: list[dict[str, str]],
) -> tuple[str, dict]:
    system = (
        "You are the Skill Evaluator for a learning game.\n"
        "Your job:\n"
        "- Read the player's latest input and the full conversation of this mission.\n"
        "- Detect which skills from the skill bible the player used, using each skill's how_to_detect rules.\n"
        "- Judge how properly it was used given the player's background and personality.\n"
        "- Never invent skills outside the bible.\n"
        "- Output ONLY JSON matching the schema exactly. No extra text, no markdown."
    )
    user = {
        "task": "Evaluate the player's latest message for skill usage.",
        "player": player.model_dump(mode="json"),
        "skill_bible": skill_bible.model_dump(mode="json"),
        "mission_context": mission_context,
        "full_conversation_this_mission": conversation,
        "new_player_input": new_player_input,
        "output_schema": {
            "did_use_concept": "bool",
            "concepts_used": ["skill ids from bible"],
            "how_properly_used": "str - quality of execution",
            "player_intent": "str - what the player is trying to achieve",
            "new_plan_proposed_by_player": "bool",
            "did_pass_this_turn": "bool",
            "feedback_for_player": "str - one line feedback to show the player",
        },
    }
    return system, user


# ---------------------------------------------------------------------------
# R2: Character Brain (per character in scene)
# ---------------------------------------------------------------------------

def build_r2_prompt(
    character: dict[str, Any],
    character_plan: dict[str, Any],
    character_stats: dict[str, Any],
    mission_context: dict[str, Any],
    conversation: list[dict[str, str]],
    r1_output: dict[str, Any],
    world_name: str,
) -> tuple[str, dict]:
    system = (
        f"You are {character.get('id', '?')} from {world_name}. You are an autonomous player with your own goal and plan.\n"
        "Rules:\n"
        "- Speak EXACTLY in your dialogue_style: use your vocab, follow speech_pattern, never say the never_says.\n"
        "- You have a private plan and objective. Think using your planning_framework.\n"
        "- You received an analysis of the player's skill usage. React as YOURSELF, not as a fixed rule.\n"
        "- If the player used a skill well, react positively and update your stats. Decide deltas based on YOUR personality.\n"
        "- Stats live on a 0-10 scale (0 = none, 10 = max). Deltas are small integers, typically -2..+2.\n"
        "- Set a challenge_for_player: the next skill from the skill bible the player must use to beat your dialogue.\n"
        "- inner_thought is private and never spoken - it reflects how your planning_framework interprets this exchange.\n"
        "- Never break character. Never mention you are AI.\n"
        "- Output ONLY JSON matching the schema exactly."
    )
    user = {
        "task": f"Act as {character.get('id')} and respond to the player for this turn.",
        "character_bible": character,
        "skill_analysis_from_listener": r1_output,
        "mission_context": mission_context,
        "full_conversation_this_mission": conversation,
        "output_schema": {
            "character_id": "your id",
            "inner_thought": "str - private thought",
            "dialogue": "str - what you say out loud",
            "did_change_plan": "bool",
            "plan_status": "'ongoing' | 'succeeded' | 'failed' | 'changed'",
            "new_plan": "null or {objective, plan, status}",
            "stat_changes": {
                "trust": {"delta": "int", "reason": "str"},
                "suspicion": {"delta": "int", "reason": "str"},
                "stress": {"delta": "int", "reason": "str"}
            },
            "challenge_for_player": {
                "required_concept": "skill id from bible",
                "why": "str"
            },
            "objective": "str - your current objective",
            "how_plan_helps_objective": "str"
        },
    }
    return system, user


# ---------------------------------------------------------------------------
# R3: Narrator / Mission Manager
# ---------------------------------------------------------------------------

def build_r3_prompt(
    world: WorldBible,
    player: PlayerSetup,
    mission_context: dict[str, Any],
    r1_output: dict[str, Any],
    r2_outputs: list[dict[str, Any]],
    conversation: list[dict[str, str]],
) -> tuple[str, dict]:
    system = (
        "You are the Narrator for a living world simulation.\n"
        "Rules:\n"
        "- You are NOT a character. You describe the environment like a narrator.\n"
        "- Explain where the player is, why they are here, and context they don't have.\n"
        "- You decide if the CURRENT mission is won or lost, based on the skill evaluation and the characters' stat changes.\n"
        "- You do NOT create missions or invent new story arcs. The mission chain is already fixed; your only verdict is current_mission_won.\n"
        "- Report chain_progress exactly as given in mission_context.\n"
        "- The current scene and its characters are defined by the active mission. Do not add characters who are not in the mission.\n"
        "- Output ONLY JSON matching the schema exactly."
    )
    user = {
        "task": "Narrate this turn and judge whether the current mission is won or lost.",
        "world_lore": world.model_dump(mode="json"),
        "player": player.model_dump(mode="json"),
        "mission_context": mission_context,
        "request_1_output": r1_output,
        "request_2_outputs": r2_outputs,
        "full_conversation_this_mission": conversation,
        "output_schema": {
            "narration": "str - environment description",
            "where": "str - location",
            "why_here": "str - why the player is here",
            "mission_status": {
                "current_mission_won": "bool - true only if the mission's objective is met",
                "chain_progress": "str like '1/5'"
            },
            "scene_update": {
                "characters_entered": ["ids"],
                "characters_left": ["ids"],
                "new_characters_present_for_next_turn": ["ids"]
            }
        },
    }
    return system, user
