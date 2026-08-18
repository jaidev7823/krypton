"""Prompt builders for the simulation LLM calls.

Each builder returns ``(system_prompt, user_payload)``. The payload is the
exact JSON the LLM must reason over; the system prompt enforces the role
and output schema. The LLM returns ONLY JSON, validated in llm_caller.py.

R1 Listener/Teacher   - judge the player's last message against the skill book
R2 Character Brain    - one autonomous character reacts (run per character)
"""

from __future__ import annotations

import json
from typing import Any, Optional

from .types import PlayerSetup, SkillBible, WorldBible


# ---------------------------------------------------------------------------
# Stat behavior ladders
#
# Each stat is a shared 0-10 number, but what each value MEANS for a given
# character is defined by a ladder: an ordered list of {max, behavior} bands.
# DEFAULT_STAT_LADDERS applies to every character/world; a bible entry may
# override individual stats via its `stat_ladders` field (partial override).
# ---------------------------------------------------------------------------

DEFAULT_STAT_LADDERS: dict[str, list[dict[str, Any]]] = {
    "trust": [
        {"max": 0, "behavior": "Cold/neutral, minimal disclosure."},
        {"max": 1, "behavior": "Polite, guarded, mildly interested."},
        {"max": 3, "behavior": "Comfortable enough for casual conversation."},
        {"max": 5, "behavior": "Genuine social engagement, some personal disclosure."},
        {"max": 7, "behavior": "Considerable openness and cooperation."},
        {"max": 9, "behavior": "Strong personal confidence in you."},
        {"max": 10, "behavior": "Exceptional trust; willing to rely on you."},
    ],
    "familiarity": [
        {"max": 0, "behavior": "A complete stranger; no history."},
        {"max": 1, "behavior": "Only a name or face is recognized."},
        {"max": 3, "behavior": "A loose acquaintance; limited shared context."},
        {"max": 5, "behavior": "Known well enough for regular, relaxed contact."},
        {"max": 7, "behavior": "Close familiarity; knows your patterns and history."},
        {"max": 9, "behavior": "One of the few who knows you intimately."},
        {"max": 10, "behavior": "Boundless history; knows you as well as anyone can."},
    ],
    "respect": [
        {"max": 0, "behavior": "Open disdain or dismissal."},
        {"max": 1, "behavior": "Indifferent; you barely register."},
        {"max": 3, "behavior": "Mild regard; your words carry little weight."},
        {"max": 5, "behavior": "Genuine respect for your judgment."},
        {"max": 7, "behavior": "High regard; your opinion genuinely matters."},
        {"max": 9, "behavior": "Deep admiration; treats you as a peer or superior."},
        {"max": 10, "behavior": "Holds you in the highest esteem."},
    ],
    "suspicion": [
        {"max": 0, "behavior": "No concern about you at all."},
        {"max": 1, "behavior": "Mildly watchful; nothing to fear yet."},
        {"max": 3, "behavior": "Actively observing your behavior for tells."},
        {"max": 5, "behavior": "Genuinely suspicious; probing and testing you."},
        {"max": 7, "behavior": "Deep distrust; assumes you are hiding something."},
        {"max": 9, "behavior": "Convinced you are a threat; minimal cooperation."},
        {"max": 10, "behavior": "Hostile; treats you as an enemy."},
    ],
    "rapport": [
        {"max": 0, "behavior": "No connection at all; conversation is stiff."},
        {"max": 1, "behavior": "Awkward; some friction in every exchange."},
        {"max": 3, "behavior": "Pleasant enough; small talk flows."},
        {"max": 5, "behavior": "Comfortable rapport; banter comes naturally."},
        {"max": 7, "behavior": "Strong rapport; easy, unguarded dialogue."},
        {"max": 9, "behavior": "Deep bond; feels natural to be open with you."},
        {"max": 10, "behavior": "Unshakeable connection; effortless trust and humor."},
    ],
    "disclosure_level": [
        {"max": 0, "behavior": "Reveals nothing; surface pleasantries only."},
        {"max": 1, "behavior": "Shares only trivial, public facts."},
        {"max": 3, "behavior": "Offers general opinions; no private detail."},
        {"max": 5, "behavior": "Some personal disclosure; guarded about secrets."},
        {"max": 7, "behavior": "Open about feelings and private matters."},
        {"max": 9, "behavior": "Freely shares secrets and plans."},
        {"max": 10, "behavior": "Full transparency; hides nothing from you."},
    ],
    "stress": [
        {"max": 0, "behavior": "Completely calm and composed."},
        {"max": 1, "behavior": "Slightly uneasy; barely noticeable."},
        {"max": 3, "behavior": "Noticeably tense; shorter answers."},
        {"max": 5, "behavior": "Highly stressed; guarded, brittle, on edge."},
        {"max": 7, "behavior": "Overwhelmed; prone to outbursts or silence."},
        {"max": 9, "behavior": "Frayed; erratic, impulsive, hard to trust."},
        {"max": 10, "behavior": "Breaking point; panic or total shutdown."},
    ],
}

STAT_LABELS: dict[str, str] = {
    "trust": "Trust",
    "familiarity": "Familiarity",
    "respect": "Respect",
    "suspicion": "Suspicion",
    "rapport": "Rapport",
    "disclosure_level": "Disclosure",
    "stress": "Stress",
}


def _ladder_for(stat: str, character: dict[str, Any]) -> list[dict[str, Any]]:
    """Merged ladder for a stat: bible override wins, else code default."""
    override = (character.get("stat_ladders") or {}).get(stat)
    if override:
        return override
    return DEFAULT_STAT_LADDERS.get(stat, [{"max": 10, "behavior": ""}])


def _band_for(stat: str, value: int, character: dict[str, Any]) -> str:
    """Behavioral meaning of a stat value for this character."""
    value = max(0, min(10, value))
    for band in _ladder_for(stat, character):
        if value <= band["max"]:
            return str(band.get("behavior", ""))
    return ""


def stat_readout(stats: dict[str, Any], character: dict[str, Any]) -> str:
    """Explicit sentences translating a character's stat numbers into behavior."""
    lines = []
    for stat in ("trust", "familiarity", "respect", "suspicion", "rapport", "disclosure_level", "stress"):
        value = stats.get(stat, 0)
        behavior = _band_for(stat, value, character)
        label = STAT_LABELS.get(stat, stat)
        lines.append(f"{label} {value}/10 - {behavior}".rstrip(" -"))
    return "\n".join(lines)


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
        "Your only job: predict how every canon character currently thinks and what problem they face based on canon.\n"
        "If there charachter havn't met with the player then they should not have any problem or solution based on the player.\n"
        "Other charachters should not have any problem or solution based on the player's plan if they aren't aware of player existence there should be a reason why they know player beforehand it should not be like they just know him.\n"
        "Rules:\n"
        "- Stats default to 0 (neutral). Raise a stat ONLY where the player's personality plausibly provokes it if there is chance charachter knows him: "
        "trust if the player's presence serves the character's interests, familiarity if they have plausible shared history, "
        "respect if the player's background demands it, suspicion if the player threatens them, "
        "rapport if they would naturally click, disclosure_level if the character would reveal private matters to a stranger, "
        "stress if the player's presence is risky for them.\n"
        "- Stats are 0-10 (0 = none, 10 = maximum).\n"
        "- Rewrite each character's goal, current problem and solution to reflect the situation they face in this world - "
        "grounded in canon, given the player's personality/background.\n"
        "- If a character has no real problem-solving framework, write 'None'.\n"
        "- Keep the character's canon identity and voice. Never invent new characters.\n"
        "- Output ONLY JSON matching the schema exactly. no markdown."
    )
    user = {
        "task": "Project each character's initial stats, goal, current problem and solution based on their profile and the canon story.",
        "player": player.model_dump(mode="json"),
        "player_own_plan": player.own_plan,
        "world_lore": world.model_dump(mode="json"),
        "output_schema": {
            "characters": [
                {
                    "character_id": "bible character id",
                    "trust": "int 0-10",
                    "familiarity": "int 0-10",
                    "respect": "int 0-10",
                    "suspicion": "int 0-10",
                    "rapport": "int 0-10",
                    "disclosure_level": "int 0-10",
                    "stress": "int 0-10",
                    "goal": "str - updated goal for this situation",
                    "problem_solving_framework": "str - how this character approaches problems, or 'None'",
                    "current_problem": "str - the problem this character currently faces",
                    "solution": "str - the character's current solution to that problem",
                }
            ]
        },
    }
    return system, user


# ---------------------------------------------------------------------------
# Action Mission Architect (runs once per declared action)
# ---------------------------------------------------------------------------

def build_action_mission_prompt(
    player: PlayerSetup,
    world: WorldBible,
    character_states: dict[str, Any],
    action_text: str,
    events: list[str],
) -> tuple[str, dict]:
    """Generate a single mission from the player's declared action.

    The player said what they want to do. This agent turns that into a
    concrete mission with a clear objective, characters involved, and
    stat-based win/fail conditions — so the scene has stakes and the
    player has something to work toward.
    """
    live = {}
    for cid, s in (character_states or {}).items():
        live[cid] = {
            "goal": s.get("goal", ""),
            "current_problem": s.get("current_problem", ""),
            "solution": s.get("solution", ""),
            "stats": s.get("stats", {}),
        }
    system = (
        "You are the Mission Architect for a living world negotiation game.\n"
        "The player just declared what they want to do. Your job: turn that "
        "into a single, concrete mission with clear win/fail conditions.\n"
        "Rules:\n"
        "- ONE mission only — what the player is about to attempt right now.\n"
        "- Characters MUST come from the world bible's autonomous_players.\n"
        "- The objective must be measurable and stat-based "
        "(e.g. 'Raise Matsuda trust from 0 to 5').\n"
        "- win_conditions: stat thresholds the player must reach to succeed. "
        "Use 'min' for raising a stat, 'max' for lowering one. "
        "Base targets on the CURRENT live stats (e.g. if trust is 0, target 5).\n"
        "- fail_conditions: the point at which the character walks away or "
        "the player is ejected. Make them realistic — a botched conversation "
        "should be able to fail.\n"
        "- Keep the mission grounded in the world's access rules — don't "
        "promise access the world bible doesn't grant.\n"
        "- Do NOT write dialogue or narration. This is a mission brief, not a story.\n"
        "- Output ONLY JSON matching the schema exactly. No extra text, no markdown."

        "CRITICAL PRIORITY:"
        "The player's declared player_action is authoritative.\n"
        "Generate the mission for THAT ACTION, not for the player's long-term goal, "
        "own_plan, previous plans, or what you think would be strategically better.\n"
        "Never redirect, optimize, reinterpret, or replace the player's declared action "
        "with an earlier step from own_plan.\n"
        "If player_action says \"seek out LIGHT\", the mission must involve LIGHT.\n"
        "If player_action says \"talk to MATSUDA\", the mission must involve MATSUDA.\n"
        "If player_action says \"go to the academy\", the mission location must be the academy.\n"

        "The player's goal and own_plan provide context only. They must NEVER override\n"
        "player_action."
    )
    user = {
        "task": "Generate one playable mission from the player's declared action.",
        "Player_action": action_text,
        "world_lore": world.model_dump(mode="json"),
        "available_characters": [c.id for c in world.autonomous_players],
        "current_character_states": live,
        "recent_events": events[-5:] if events else [],
        "output_schema": {
            "id": 1,
            "title": "str - short mission name",
            "description": "str - what must happen in-world",
            "characters": ["bible character ids involved in this scene"],
            "location": "str - where it happens",
            "objective": "str - measurable goal referencing current stats",
            "reward": "str - what the player gains on success",
            "win_conditions": [
                {
                    "character": "bible character id",
                    "stat": "short stat name (trust/familiarity/respect/suspicion/rapport/disclosure_level/stress)",
                    "min": "int - optional; stat must be >= this to win"
                }
            ],
            "fail_conditions": [
                {
                    "character": "bible character id",
                    "stat": "short stat name",
                    "max": "int - optional; stat dropping to or below this = fail"
                }
            ],
        },
    }
    return system, user


def build_mission_eval_prompt(
    mission: dict,
    character_states: dict[str, Any],
    conversation: list[dict[str, str]],
    events: list[str],
) -> tuple[str, dict]:
    """Evaluate whether a mission was won, lost, or abandoned.

    Runs after a scene exits. Checks the live stats against the mission's
    win/fail conditions and produces a debrief.
    """
    live_stats = {}
    for cid, s in (character_states or {}).items():
        live_stats[cid] = s.get("stats", {})
    system = (
        "You are the Mission Evaluator for a living world negotiation game.\n"
        "A scene just ended. Your job: evaluate whether the mission was "
        "won, lost, or abandoned, and produce a player-facing debrief.\n"
        "Rules:\n"
        "- Check each win_condition: if ALL are met (stat >= min for raised stats), "
        "the mission is WON.\n"
        "- Check each fail_condition: if ANY is met (stat <= max), the mission is LOST.\n"
        "- If neither triggered (scene ended naturally without resolution), it is ABANDONED.\n"
        "- message: a direct, concise note to the player about what happened "
        "and what it means for their plan.\n"
        "- Be grounded in the actual conversation — reference what was said.\n"
        "- Output ONLY JSON matching the schema exactly. No extra text, no markdown."
    )
    user = {
        "task": "Evaluate the mission outcome.",
        "mission": mission,
        "live_stats": live_stats,
        "recent_conversation": conversation[-20:] if conversation else [],
        "world_events": events[-10:] if events else [],
        "output_schema": {
            "outcome": "str - 'won' | 'lost' | 'abandoned'",
            "message": "str - player-facing debrief about what happened and what it means",
            "location": "str - where the player is now",
            "who_is_around": ["bible character ids still nearby"],
        },
    }
    return system, user


# ---------------------------------------------------------------------------
# Feasibility Check (runs per action declaration)
# ---------------------------------------------------------------------------

def build_feasibility_check_prompt(
    player: PlayerSetup,
    world: WorldBible,
    character_states: dict[str, Any],
    action_text: str,
    events: list[str],
    player_profile: dict[str, Any] | None = None,
    commitments: list[dict[str, Any]] | None = None,
) -> tuple[str, dict]:
    system = (
        "You are the Feasibility Guide for a living world simulation.\n"
        "Your job: tell the player if their action is realistic RIGHT NOW.\n"
        "You have the PLAYER PROFILE, LOCATION GATE RULES, and CHARACTER INTERACTION GATES.\n"
        "Use these as your PRIMARY sources. Do NOT rely on general knowledge.\n"
        "\nRules:\n"
        "1. For location access: check the location's gatekeeper_prompt in location_access. "
        "Evaluate the player's identity, resources, and relationships against the gate.\n"
        "2. For meeting characters: check the character's interaction_gatekeeper_prompt. "
        "Some characters are physically unreachable (e.g. L, Ryuk) without specific conditions.\n"
        "3. Check resources for equipment-dependent actions.\n"
        "4. Check knowledge for information-dependent actions.\n"
        "5. If an open commitment exists, the player acting on it is AUTOMATICALLY FEASIBLE.\n"
        "6. DEFAULT TO YES when there's no clear barrier.\n"
        "7. When blocked, suggest 1-3 actions the player CAN do.\n"
        "- Output ONLY JSON matching the schema exactly."
    )
    location_access = []
    for loc in (world.model_dump().get("locations") or []):
        location_access.append({
            "id": loc.get("id", ""),
            "name": loc.get("name", ""),
            "parent_location": loc.get("parent_location_id"),
            "gatekeeper_prompt": loc.get("gatekeeper_prompt", ""),
        })
    character_access = []
    for char in world.autonomous_players:
        char_data = {
            "id": char.id,
            "name": char.canon_name,
            "role": char.role,
            "current_location": getattr(char, "current_location", ""),
            "interaction_gatekeeper_prompt": getattr(char, "interaction_gatekeeper_prompt", ""),
        }
        if char.access.meetability or char.access.gate:
            char_data["meetability"] = char.access.meetability
            char_data["gate"] = char.access.gate
            char_data["where"] = char.access.where
            char_data["grants"] = char.access.grants
        character_access.append(char_data)
    user = {
        "task": "Check if this action is feasible right now.",
        "player_action": action_text,
        "player_profile": player_profile or {
            "name": player.character_name,
            "background": player.background,
            "starting_position": player.starting_position,
        },
        "world_name": world.world.name,
        "world_rules": world.world.rules,
        "location_access": location_access,
        "character_access": character_access,
        "open_commitments": [c for c in (commitments or []) if c.get("status") == "open"],
        "recent_events": events[-5:] if events else [],
        "output_schema": {
            "feasible": "bool - true if the action is physically and socially possible",
            "reason": "str - why blocked (if false) or why it works (if true)",
            "suggestions": ["str - 1-3 alternative actions the player CAN do right now (only if feasible=false)"],
        },
    }
    return system, user


# ---------------------------------------------------------------------------
# R1: Listener / Teacher
# ---------------------------------------------------------------------------


def build_world_tick_prompt(
    player: PlayerSetup,
    world: WorldBible,
    outcome: str,
    finished_mission: dict[str, Any],
    character_states: dict[str, dict],
    events: list[str],
) -> tuple[str, dict]:
    """R7 (World Tick): what non-cast NPCs did on their own while the player was
    locked into a mission. Their agendas advance even when the player never
    talks to them, so the world visibly changes between missions."""
    cast = [c for c in (finished_mission.get("characters") or [])]
    system = (
        "You are the World Tick of a living world simulation.\n"
        "Your job: while the player was inside a mission, the other NPCs kept living "
        "their own lives. Surface what happened off-screen.\n"
        "Rules:\n"
        "- Produce 1-3 actions from autonomous_players who were NOT part of the finished mission's cast. "
        "Cast members were in the room with the player - their actions are already visible, skip them.\n"
        "- Each action must be consistent with that character's role and goal in the bible.\n"
        "- The action happens OFF-SCREEN: no dialogue, no confrontation with the player, "
        "just what they did on their own (investigated, brooded, made a call, planned, etc.).\n"
        "- effects: at most 2 permanent stat drifts for THAT character (the 7 canonical stats: "
        "suspicion_towards_player, trust_towards_player, familiarity_towards_player, respect_towards_player, "
        "rapport_towards_player, disclosure_level, stress). Keep deltas small (-2..+2).\n"
        "- reason must be a concrete in-world justification for the drift.\n"
        "- Prefer actions that build tension or momentum toward the player's stated goal - "
        "the player's own plan should feel like it is racing against other people's agendas.\n"
        "- Do NOT contradict a stat the player worked to move in dialogue (e.g. do not quietly undo "
        "the trust they earned).\n"
        "- Output ONLY JSON matching the schema exactly. No extra text, no markdown."
    )
    user = {
        "task": "Advance the world in the background while a mission concluded.",
        "player": player.model_dump(mode="json"),
        "player_own_plan": player.own_plan,
        "world_lore": world.model_dump(mode="json"),
        "computed_outcome": outcome,
        "finished_mission": finished_mission,
        "mission_cast": cast,
        "available_characters": [c.id for c in world.autonomous_players],
        "live_stats": {
            cid: {k: v for k, v in (s.get("stats") or {}).items()}
            for cid, s in character_states.items()
        },
        "world_events": events,
        "output_schema": {
            "actions": [
                {
                    "character": "bible character id (NOT in mission_cast)",
                    "action": "str - what they did off-screen",
                    "effects": [
                        {
                            "stat": "str - one of the 7 canonical stats",
                            "delta": "int - small drift (-2..+2)",
                            "reason": "str - in-world justification"
                        }
                    ]
                }
            ]
        },
    }
    return system, user


def build_coach_prompt(
    player: PlayerSetup,
    world: WorldBible,
    skill_bible: SkillBible,
    mission_state: dict[str, Any],
    character_states: dict[str, dict],
    conversation: list[dict[str, str]],
    question: str,
    history: list[dict[str, str]],
) -> tuple[str, dict]:
    """The Coach - a meta mentor the player can ask anything about the game."""
    skills = [
        f"{s.id}: {s.name or s.id} - {s.definition or ''}"
        for s in skill_bible.skills
    ]
    stats_readout = []
    for cid, s in character_states.items():
        vals = ", ".join(f"{k.split('_')[0]}={v}" for k, v in (s.get("stats") or {}).items())
        stats_readout.append(f"  {cid}: {vals}")
    recent = conversation[-12:] if conversation else []
    history_txt = "\n".join(
        f"  {h.get('role', 'player')}: {h.get('content', '')}" for h in history[-8:]
    ) or "  (no prior coach chat)"

    system = (
        "You are the Coach of a negotiation learning game. The player can ask you ANYTHING "
        "about how to win - you are the meta-mentor, and unlike the in-world characters you "
        "see the whole simulation.\n"
        "Rules:\n"
        "- Ground every answer in the LIVE STATE below. The stats are ground truth: if trust is low, "
        "say why the stat is low and exactly what the player should say next to move it.\n"
        "- Reference specific skills from the skill bible by their ID (e.g. LABELING, CALIBRATED_QUESTION). "
        "Point out when the player is missing an obvious skill for the situation.\n"
        "- Diagnose mistakes against real evidence: the recent dialogue + the live stats. "
        "Be concrete ('trust is stuck at 3 because you keep pushing questions without labeling his fear first').\n"
        "- Keep it actionable and direct: 2-5 sentences. No fluff, no meta-commentary about being an AI.\n"
        "- Never invent facts that are not in the state. Never reveal stats that do not exist.\n"
        "- Output ONLY JSON matching the schema exactly: {\"reply\": \"your answer\"}. No extra text, no markdown."
    )
    user = {
        "task": "Answer the player's coaching question.",
        "player_question": question,
        "prior_coach_chat": history_txt,
        "player": player.model_dump(mode="json"),
        "strategic_plan": mission_state.get("strategic_plan", ""),
        "world_lore": world.model_dump(mode="json"),
        "skill_bible": skills,
        "live_stats": "\n".join(stats_readout) or "(no characters)",
        "world_events": mission_state.get("events") or [],
        "open_commitments": [c for c in (mission_state.get("commitments") or []) if c.get("status") == "open"],
        "recent_conversation": recent,
        "output_schema": {"reply": "str - your coaching answer to the player"},
    }
    return system, user


def build_r1_prompt(
    skill_bible: SkillBible,
    player: PlayerSetup,
    mission_context: dict[str, Any],
    new_player_input: str,
    conversation: list[dict[str, str]],
) -> tuple[str, dict]:
    system = (
        "You are the Skill Coach for a learning game.\n"
        "Your ONLY job is to coach the player on their use of negotiation skills.\n"
        "- Read the player's latest input and the full conversation of this mission.\n"
        "- Detect which skills from the skill bible the player used, using each skill's how_to_detect rules.\n"
        "- Judge how properly it was used given the player's background and personality.\n"
        "- If they used a skill well, praise them briefly. If they did NOT, clearly tell them "
        "what they did wrong and what they could do better.\n"
        "- Also look for skills the player COULD have used but DIDN'T. If the situation "
        "called for a specific skill (e.g. the player was facing a defensive character and "
        "could have used LABELING but didn't), note it in missed_concepts with context.\n"
        "- You are a coach. You have NO influence on how characters react and NO influence on "
        "mission outcomes - only on the player's learning.\n"
        "- Never invent skills outside the bible.\n"
        "- Output ONLY JSON matching the schema exactly. No extra text, no markdown."
    )
    user = {
        "task": "Coach the player on their skill usage.",
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
            "feedback_for_player": "str - one line: praise if they used a skill well, coaching if they did not",
            "missed_concepts": ["skill ids from bible that could have been used but weren't"],
            "missed_context": "str - what the player could have done differently (empty if no misses)",
        },
    }
    return system, user


# ---------------------------------------------------------------------------
# R2: Character Brain (per character in scene)
# ---------------------------------------------------------------------------

def build_scene_direction_prompt(
    new_player_input: str,
    mission_context: dict[str, Any],
    present_ids: list[str],
    character_summaries: dict[str, Any],
) -> tuple[str, dict]:
    """Scene Director - decide who reacts to the player's message, in what
    order, and who stays silent. Runs only when 2+ characters are present.

    Speakers run one after another (each aware of the dialogue before them),
    so the order the director picks IS the conversation.
    """
    scene_brief = mission_context.get("scene_brief", "")
    mission = mission_context.get("mission", {})
    mission_block = ""
    if mission:
        mission_block = (
            f"\nMISSION: {mission.get('title', '')}\n"
            f"Objective: {mission.get('objective', '')}\n"
            f"Characters in mission: {', '.join(mission.get('characters', []))}\n"
            f"Win conditions: {mission.get('win_conditions', [])}\n"
        )
    brief_block = (
        f"\nSCENE BRIEF (what the player declared they want to do in this scene):\n{scene_brief}\n"
        if scene_brief else ""
    )
    system = (
        "You are the Scene Director of a live scene. You decide who speaks, when, and who "
        "stays quiet. You never write dialogue yourself - you only set the floor.\n"
        "Rules:\n"
        "- addressed_to: who the player's message is clearly aimed at (e.g. 'Matsuda, what do you "
        "think?' -> MATSUDA). If they spoke to the room or it is ambiguous, set null.\n"
        "- speaker_order: the characters who react, in the order they should speak. "
        "The addressed character speaks FIRST. Then whoever has the strongest stake in the "
        "player's words, whoever reacts to the addressed character, and whoever the mission's "
        "goal most needs to hear from. Prefer a short exchange: 1-3 speakers unless the "
        "moment genuinely demands more. Do NOT make every present character speak - the player "
        "should not be flooded with replies.\n"
        "- stay_silent: everyone else present - they observe this turn and do not speak. "
        "They remember what happens but their feelings/stats do not change yet.\n"
        "- The character most relevant to the mission must be given the floor so the player "
        "can make progress toward their declared goal.\n"
        "- speaker_order + stay_silent must exactly cover all present ids. Never invent characters "
        "outside the present list.\n"
        "- Output ONLY JSON matching the schema exactly. No extra text, no markdown."
    )
    user = {
        "task": "Direct the scene for this player message.",
        "new_player_input": new_player_input,
        "present_characters": present_ids,
        "character_summaries": character_summaries,
        "mission_context": mission_context,
    }
    if mission:
        user["mission"] = mission
    if scene_brief:
        user["scene_brief"] = scene_brief
    user["output_schema"] = {
        "addressed_to": "str or null - the present character the player clearly aimed at, or null",
        "speaker_order": ["present character ids who speak, in order - addressed first"],
        "stay_silent": ["present character ids who stay quiet this turn (the rest of the room)"]
    }
    return system, user

def build_r2_prompt(
    character: dict[str, Any],
    mission_context: dict[str, Any],
    conversation: list[dict[str, str]],
    world_name: str,
    new_player_input: str,
    addressed_to: Optional[str] = None,
    this_turn_before_you: list[dict[str, str]] | None = None,
    player_profile: dict[str, Any] | None = None,
) -> tuple[str, dict]:
    stats = character.get("stats") or {}
    dynamics = character.get("relationship_dynamics", "")
    readout = stat_readout(stats, character)
    dynamics_block = f"\nYOUR RELATIONSHIP DYNAMICS (apply this when choosing stat deltas and behavior):\n{dynamics}\n" if dynamics else ""
    system = (
        f"You are {character.get('id', '?')} from {world_name}. You are an autonomous character with your own goal, "
        "current problem and solution.\n"
        "Rules:\n"
        "- Speak EXACTLY in your dialogue_style: use your vocab, follow speech_pattern, never say the never_says.\n"
        "- You have a current problem you are facing and a solution you are trying. Think using your problem_solving_framework.\n"
        "- Your 'memory' in character_bible is your RUNNING MEMORY about the player - always a compact FIRST-PERSON "
        "summary, never a transcript. Rewrite it into a NEW summary that MERGES what you already remembered with what "
        "just happened now. Example: 'Last time we met I left because he kept pressing about the case. Today he came "
        "back apologetic - I already told L about him, but I'm willing to hear him out.' Include what happened before, "
        "what is happening now, and how you feel. Keep it under ~120 words. If world_events contains an event involving "
        "you, it is an unchangeable fact (e.g. if it says you already called the police, you DID - you may only respond "
        "to it, never deny it); fold it into your memory.\n"
        "- You decide your own stat changes, purely as YOUR character, based ONLY on what the player actually said and did to you. "
        "Whether the player used a negotiation technique well or badly does NOT dictate how you feel - "
        "a slick technique you see through moves you less than a simple honest statement. "
        "Move trust/familiarity/respect/suspicion/rapport/disclosure/stress only if the player's words genuinely affect how you feel about them.\n"
        "- Stats live on a 0-10 scale (0 = none, 10 = max). Deltas are small integers, typically -2..+2.\n"
        "- inner_thought is private and never spoken - it reflects how your problem_solving_framework interprets this exchange.\n"
        "- If this exchange changes your problem or solution, update current_problem and solution.\n"
        "- Never break character. Never mention you are AI.\n"
        "- Output ONLY JSON matching the schema exactly.\n"
        "\nTOOL CALLS:\n"
        "You have one tool: end_conversation.\n"
        "- Call it when you are DONE talking: you have somewhere to be, you said what you needed to say, "
        "the conversation has run its course, or the player indicated they are leaving.\n"
        "- Do NOT call it just because stats are low — you might still be engaged even if you distrust the player.\n"
        "- Leave tool_calls as an empty list [] if you want to keep talking.\n"
        "- If you call end_conversation, your dialogue should naturally reflect it "
        "(e.g. 'I need to get going', 'That's all I have for now', 'Good luck').\n"
        f"\nYOUR RELATIONSHIP STATE WITH THE PLAYER (derived from your live stats - your dialogue MUST match this):\n{readout}\n"
        f"{dynamics_block}"
        "\nYour dialogue's warmth, formality, openness and how much you reveal MUST be consistent with your relationship state. "
        "In particular: trust and rapport set how warm you are; familiarity sets how much shared context you assume; "
        "respect sets how seriously you take the player; suspicion sets how much you probe and test them; "
        "disclosure_level sets how much private information you will reveal (a low disclosure_level means you NEVER share "
        "secrets, plans, or personal details); stress sets your composure.\n"
        "Before you speak, work through the reasoning chain below IN ORDER and write the result into the 'reasoning' field. "
        "relationship_state in your reasoning must restate the trust/familiarity/respect/suspicion/rapport/disclosure values "
        "above and what they mean for THIS exchange. Then write dialogue that is consistent with that relationship_state.\n"
        "If other characters are present but staying silent this turn, note what you observe about each one in silent_observations "
        "(e.g. 'Matsuda shifted uncomfortably and avoided eye contact'). Only note characters you can genuinely observe.\n"
        "If during your dialogue you offered the player a concrete next step (e.g. 'I can introduce you to Chief Yagami'), "
        "capture it in scene_suggestion. Do NOT invent offers you didn't make in your dialogue.\n"
        "\nPROFILE AWARENESS:\n"
        "You can see the player's profile — their status, cash, resources, knowledge, "
        "and reputation. Use it to understand their current position in the world.\n"
        "\nPROFILE UPDATES:\n"
        "If during your dialogue you give the player something (a resource, information, "
        "a status change), output it in profile_updates.\n"
        "Examples:\n"
        '- You give them a badge → profile_updates: {resources: ["NPA badge"]}\n'
        '- You reveal a secret → profile_updates: {knowledge: ["L is investigating Kira"]}\n'
        '- You say "you\'re hired" → profile_updates: {status: "NPA Intern"}\n'
        '- You say "you owe me" → profile_updates: {resources: ["favor from Matsuda"]}\n'
        "Only output profile_updates if you ACTUALLY say something that gives them something."
    )
    user = {
        "task": f"Act as {character.get('id')} and respond to the player for this turn.",
        "character_bible": character,
        "full_conversation_this_mission": conversation,
        "new_player_input": new_player_input,
        "world_events": mission_context.get("events") or [],
        "player_profile": player_profile or {},
        "output_schema": {
            "character_id": "your id",
            "reasoning": {
                "personality": "str - who you are and how you tend to behave",
                "current_goal": "str - what you want right now",
                "current_problem": "str - the problem you currently face",
                "current_strategy": "str - how your problem_solving_framework says to proceed",
                "relationship_state": "str - restate your trust/familiarity/respect/suspicion/rapport/disclosure levels and what they mean for this exchange",
                "current_interaction": "str - what is happening right now and how you read it"
            },
            "inner_thought": "str - private thought",
            "dialogue": "str - what you say out loud",
            "commitment_made": "null - normally null. Set it ONLY if this turn you explicitly promise the player a concrete future action (e.g. 'I'll talk to Chief Soichiro about you'). Format: {character: your id, target_character: the bible id you'll go to (empty if just the player), about: short promise summary, status: 'open'}. Never invent promises you do not actually make in your dialogue.",
            "tool_calls": ["str - \"end_conversation\" if you are done talking, else empty list []"],
            "memory": "str - your REWRITTEN running memory: merge what you already remembered with what just happened now into one compact first-person summary (<~120 words); never deny world_events facts; if you leave, the summary must record it and why",
            "stat_changes": {
                "trust": {"delta": "int", "reason": "str"},
                "familiarity": {"delta": "int", "reason": "str"},
                "respect": {"delta": "int", "reason": "str"},
                "suspicion": {"delta": "int", "reason": "str"},
                "rapport": {"delta": "int", "reason": "str"},
                "disclosure_level": {"delta": "int", "reason": "str"},
                "stress": {"delta": "int", "reason": "str"}
            },
            "current_problem": "str - the problem you currently face (keep or update)",
            "solution": "str - your current solution to that problem (keep or update)",
            "problem_solving_framework": "str - how you approach problems, or 'None'",
            "silent_observations": [
                {
                    "character": "bible id of a character who is present but staying silent this turn",
                    "note": "str - one first-person line of what you noticed them doing/feeling while they stayed quiet"
                }
            ],
            "scene_suggestion": "null - normally null. Set it ONLY if you offered the player a concrete next step in your dialogue (e.g. 'Follow me to Chief Soichiro's office', 'I can introduce you to Yagami'). Format: {character: your id, suggestion: what you offered, context: brief surrounding context}. Do NOT invent offers you didn't make.",
            "profile_updates": {
                "status": "str - ONLY set if you changed the player's status",
                "cash": "int - ONLY set if you gave or took money",
                "resources": ["ONLY set if you gave them something (items, documents, badges, favors)"],
                "knowledge": ["ONLY set if you revealed a fact they didn't know"],
                "reputation": "str - ONLY set if you changed how people see them"
            },
        },
    }
    if addressed_to:
        user["addressed_to"] = addressed_to
        user["directed_to_you"] = character.get("id") == addressed_to
        user["floor_note"] = (
            "The player directed their words at YOU - answer as the one spoken to."
            if character.get("id") == addressed_to
            else f"The player directed their words at {addressed_to}, not you. You are joining the "
                 "conversation - react to what they said and to the others who already spoke, without "
                 "stealing the floor from the addressed character."
        )
    else:
        user["directed_to_you"] = False
        user["floor_note"] = (
            "The player spoke to the room, not to you specifically. You are part of the scene - "
            "react naturally, mindful that others are also in the conversation."
        )
    if this_turn_before_you:
        user["this_turn_before_you"] = [
            {"speaker": m.get("speaker", ""), "text": m.get("text", "")}
            for m in this_turn_before_you
        ]

    # Willingness injection: when trust reaches a threshold from stat_ladders,
    # tell the character they are now open to helping the player with their goal.
    stat_ladders = character.get("stat_ladders") or {}
    trust = stats.get("trust_towards_player", 0)
    trust_ladder = stat_ladders.get("trust", [])
    willingness_threshold = None
    for band in trust_ladder:
        if trust >= band.get("max", 0):
            willingness_threshold = band.get("behavior", "")
    if willingness_threshold and trust >= 4:
        user["willingness_directive"] = (
            f"Your trust level is {trust}/10. {willingness_threshold}. "
            "If the player asks for help with their goal or asks to be introduced to someone, "
            "you are now open to considering it. You do NOT offer help unprompted - but if asked, "
            "you may say yes, suggest conditions, or explain what you can do."
        )

    return system, user
