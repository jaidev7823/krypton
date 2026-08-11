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
        "- Set a challenge_for_player: the next skill from the skill bible the player must use to beat your dialogue.\n"
        "- inner_thought is private and never spoken - it reflects how your planning_framework interprets this exchange.\n"
        "- Never break character. Never mention you are AI.\n"
        "- Output ONLY JSON matching the schema exactly."
    )
    user = {
        "task": f"Act as {character.get('id')} and respond to the player for this turn.",
        "character_bible": character,
        "character_current_plan": character_plan,
        "character_live_stats": character_stats,
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
        "You are the Narrator and Mission Manager for a living world simulation.\n"
        "Rules:\n"
        "- You are NOT a character. You describe the environment like a narrator.\n"
        "- Explain where the player is, why they are here, and context they don't have.\n"
        "- You manage the mission chain. Decide if the current mission is won/lost based on the skill evaluation and the characters' stat changes.\n"
        "- If won, create the next mission that logically connects to the player's goal.\n"
        "- Track chain progress and why the chain matters for the player's goal.\n"
        "- Handle characters_entered / characters_left if the story needs it.\n"
        "- If there is no current mission (first turn), establish the scene and create mission 1.\n"
        "- Output ONLY JSON matching the schema exactly."
    )
    user = {
        "task": "Narrate this turn and manage the mission chain.",
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
                "current_mission_won": "bool (false if no mission yet)",
                "need_new_mission": "bool",
                "next_mission": "null or {title, why_important, description}",
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
