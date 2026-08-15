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
# R0: Mission Architect (runs once per player plan)
# ---------------------------------------------------------------------------

def build_r0_prompt(
    player: PlayerSetup,
    world: WorldBible,
    character_states: dict[str, Any] | None = None,
) -> tuple[str, dict]:
    system = (
        "You are the Mission Architect for a simulation world.\n"
        "Your only job is to turn the PLAYER'S OWN plan into a mission chain.\n"
        "Rules:\n"
        "- Break the player's own_plan into 4-5 missions that lead to their goal.\n"
        "- TWO-TIER PLANNING: only the FIRST mission is concrete and playable. Later missions are ROUGH OUTLINES - "
        "the world is alive and dialogue may change what happens next, so do NOT over-specify the future.\n"
        "  * The FIRST mission (id 1) gets FULL detail: location, objective, reward, exact characters, and "
        "  win_conditions + fail_conditions (see stat rules below). This is what the player plays immediately.\n"
        "  * Every LATER mission (id 2+) is an OUTLINE: set detail_level 'outline', give it a title, a ONE-LINE "
        "  description of its purpose, and the rough characters it will involve. Leave objective, reward, "
        "  win_conditions and fail_conditions EMPTY/[] - they will be generated when the mission actually begins.\n"
        "- 'characters' MUST only use ids from the world bible's autonomous_players. Never invent characters.\n"
        "- Missions escalate: earlier missions are low-stakes (a single character), later ones raise the stakes.\n"
        "- Read current_character_states: those are the LIVE stats/goals/current problems AFTER the cast was projected. "
        "The first mission's objective must reference the current values (e.g. 'Raise Matsuda trust from 2 to 7').\n"
        "- The FIRST mission MUST define win_conditions and fail_conditions, using the short stat names "
        "(trust, familiarity, respect, suspicion, rapport, disclosure_level, stress) and bible character ids.\n"
        "  * win_conditions: the stat values that mean the objective is achieved, e.g. "
        "[{\"character\": \"MATSUDA\", \"stat\": \"trust\", \"min\": 5}]. Use 'min' for 'raise to at least X' "
        "and 'max' for 'lower to at most X'. Base the target on the CURRENT value from current_character_states.\n"
        "  * fail_conditions: the stat values that mean the character is frustrated enough to walk away or kick the "
        "player out, e.g. [{\"character\": \"MATSUDA\", \"stat\": \"trust\", \"max\": 1}] or "
        "[{\"character\": \"MATSUDA\", \"stat\": \"stress\", \"min\": 8}]. Set these so a badly-botched mission can actually fail.\n"
        "- Do NOT write dialogue or narration. Missions are objectives, not story.\n"
        "- Output ONLY JSON matching the schema exactly. No extra text, no markdown."
    )
    live = {}
    if character_states:
        for cid, s in character_states.items():
            live[cid] = {
                "goal": s.get("goal", ""),
                "problem_solving_framework": s.get("problem_solving_framework", ""),
                "current_problem": s.get("current_problem", ""),
                "solution": s.get("solution", ""),
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
                    "description": "str - mission 1: what must happen in-world; later missions: ONE-LINE purpose only",
                    "why_important": "str - how it serves the player's goal",
                    "detail_level": "str - 'detailed' for mission 1; 'outline' for every later mission",
                    "location": "str - in-world place",
                    "characters": ["bible character ids present in this mission"],
                    "objective": "str - measurable goal e.g. 'Raise Matsuda trust from 2 to 7' (OUTLINE missions: empty string)",
                    "reward": "str - what the player gains on success (OUTLINE missions: empty string)",
                    "win_conditions": [
                        {
                            "character": "bible character id",
                            "stat": "short stat name (trust/familiarity/respect/suspicion/rapport/disclosure_level/stress)",
                            "min": "int - optional; stat must be >= this value to win",
                            "max": "int - optional; stat must be <= this value to win"
                        }
                    ],
                    "fail_conditions": [
                        {
                            "character": "bible character id",
                            "stat": "short stat name",
                            "min": "int - optional; stat reaching this means the character is overwhelmed",
                            "max": "int - optional; stat dropping to this means the character gives up on you"
                        }
                    ],
                }
            ]
        },
    }
    return system, user


# ---------------------------------------------------------------------------
# R1: Listener / Teacher
# ---------------------------------------------------------------------------

def build_flesh_prompt(
    player: PlayerSetup,
    world: WorldBible,
    outline: dict[str, Any],
    character_states: dict[str, Any],
    commitments: list[dict[str, Any]],
    events: list[str],
) -> tuple[str, dict]:
    """Turn a ROUGH OUTLINE mission into a fully playable one, right before the
    player enters it, so the detail can use the CURRENT live world state."""
    live = {}
    for cid, s in (character_states or {}).items():
        live[cid] = {
            "goal": s.get("goal", ""),
            "current_problem": s.get("current_problem", ""),
            "solution": s.get("solution", ""),
            "stats": s.get("stats", {}),
        }
    system = (
        "You are the Mission Architect, fleshing out ONE mission the player is about to enter.\n"
        "Rules:\n"
        "- This mission was previously only an OUTLINE (title + rough purpose + rough cast). Fill in the details now, "
        "using the CURRENT live stats and anything the characters promised (commitments) or did (world events).\n"
        "- Keep the mission's title and purpose; make the concrete objective, reward, location and characters concrete.\n"
        "- 'characters' MUST only use ids from the world bible's autonomous_players. Never invent characters.\n"
        "- The objective MUST reference the current stat values (e.g. 'Raise Matsuda trust from 3 to 6').\n"
        "- Define win_conditions and fail_conditions using the short stat names "
        "(trust, familiarity, respect, suspicion, rapport, disclosure_level, stress):\n"
        "  * win_conditions: e.g. [{\"character\": \"MATSUDA\", \"stat\": \"trust\", \"min\": 6}] - 'min' to raise, 'max' to lower.\n"
        "  * fail_conditions: the point where the character walks away or kicks the player out, e.g. "
        "[{\"character\": \"MATSUDA\", \"stat\": \"trust\", \"max\": 1}].\n"
        "- If an open commitment from a character in this mission points at a specific action (e.g. 'I'll ask Chief "
        "Soichiro'), make the objective about following through on that promise.\n"
        "- Do NOT write dialogue or narration.\n"
        "- Output ONLY JSON matching the schema exactly. No extra text, no markdown."
    )
    user = {
        "task": "Flesh out this outline mission into a playable mission.",
        "outline_mission": outline,
        "player": player.model_dump(mode="json"),
        "player_own_plan": player.own_plan,
        "world_lore": world.model_dump(mode="json"),
        "available_characters": [c.id for c in world.autonomous_players],
        "current_character_states": live,
        "commitments": commitments,
        "world_events": events,
        "output_schema": {
            "mission_chain": [
                {
                    "id": "int - keep the outline's id",
                    "title": "str - short mission name",
                    "description": "str - what must happen in-world",
                    "why_important": "str - how it serves the player's goal",
                    "detail_level": "str - 'detailed'",
                    "location": "str - in-world place",
                    "characters": ["bible character ids present in this mission"],
                    "objective": "str - measurable goal referencing current stats",
                    "reward": "str - what the player gains on success",
                    "win_conditions": [
                        {
                            "character": "bible character id",
                            "stat": "short stat name",
                            "min": "int - optional; stat must be >= this value to win",
                            "max": "int - optional; stat must be <= this value to win"
                        }
                    ],
                    "fail_conditions": [
                        {
                            "character": "bible character id",
                            "stat": "short stat name",
                            "min": "int - optional; stat reaching this means the character is overwhelmed",
                            "max": "int - optional; stat dropping to this means the character gives up on you"
                        }
                    ],
                }
            ]
        },
    }
    return system, user


def build_reconcile_prompt(
    player: PlayerSetup,
    world: WorldBible,
    outcome: str,
    finished_conversation: list[dict[str, str]],
    commitments: list[dict[str, Any]],
    remaining_outline: list[dict[str, Any]],
    events: list[str],
) -> tuple[str, dict]:
    """R6 (Scenario Director): after a mission ends, re-align the rough outline
    with what actually happened - promises made in dialogue now shape the next
    scenario instead of a rigid pre-fixed order."""
    system = (
        "You are the Scenario Director of a living world simulation.\n"
        "Your job: keep the player's plan on track while letting dialogue change what happens next.\n"
        "Rules:\n"
        "- The player has a HIGH-LEVEL plan. The remaining missions are only rough outlines - mutable.\n"
        "- The just-finished conversation may contain commitments characters made (see commitments, status 'open').\n"
        "- Decide whether the NEXT outline mission should be revised to follow through on open commitments, "
        "or stay as-is. Only revise when a commitment genuinely redirects the situation "
        "(e.g. Matsuda promised to ask Chief Soichiro -> the next mission should involve Soichiro).\n"
        "- Set material_shift=true ONLY when you changed the next mission because of something in dialogue. "
        "If the outline already matches, keep it and material_shift=false.\n"
        "- shift_summary: one player-facing sentence about what changed, e.g. "
        "'Matsuda told you he will ask Chief Soichiro about you, so your next step centers on him.' "
        "Empty if material_shift is false.\n"
        "- Update every commitment's status: 'fulfilled' if the character followed through this mission, "
        "'broken' if the character clearly abandoned it, otherwise keep 'open'. Return the full list.\n"
        "- revised_next: the revised detail for the NEXT mission only (keep id). null to leave it unchanged.\n"
        "- 'characters' in revised_next MUST only use ids from the world bible's autonomous_players.\n"
        "- Output ONLY JSON matching the schema exactly. No extra text, no markdown."
    )
    user = {
        "task": "Reconcile the remaining plan with what just happened.",
        "player": player.model_dump(mode="json"),
        "player_own_plan": player.own_plan,
        "world_lore": world.model_dump(mode="json"),
        "computed_outcome": outcome,
        "available_characters": [c.id for c in world.autonomous_players],
        "finished_conversation": finished_conversation,
        "commitments": commitments,
        "remaining_outline": remaining_outline,
        "world_events": events,
        "output_schema": {
            "revised_next": {
                "title": "str - revised name for the next mission (or unchanged)",
                "description": "str - one-line purpose for the next mission",
                "location": "str - where it happens",
                "characters": ["bible character ids"]
            },
            "commitments": [
                {
                    "character": "bible character id",
                    "target_character": "bible character id (or empty)",
                    "about": "str - short promise summary",
                    "status": "str - 'open' | 'fulfilled' | 'broken'"
                }
            ],
            "material_shift": "bool - did dialogue actually change the next mission?",
            "shift_summary": "str - one player-facing sentence; empty if no shift"
        },
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
        },
    }
    return system, user


# ---------------------------------------------------------------------------
# R2: Character Brain (per character in scene)
# ---------------------------------------------------------------------------

def build_r2_prompt(
    character: dict[str, Any],
    mission_context: dict[str, Any],
    conversation: list[dict[str, str]],
    world_name: str,
    new_player_input: str,
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
    )
    user = {
        "task": f"Act as {character.get('id')} and respond to the player for this turn.",
        "character_bible": character,
        "full_conversation_this_mission": conversation,
        "new_player_input": new_player_input,
        "world_events": mission_context.get("events") or [],
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
            "problem_solving_framework": "str - how you approach problems, or 'None'"
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
        "- The mission's win/loss is already decided mechanically by the Mission Manager from the stat "
        "thresholds - see computed_mission_outcome in your payload. NEVER change that verdict.\n"
        "- If computed_mission_outcome is 'won', narrate the objective being achieved. If 'failed', narrate "
        "the character getting frustrated and leaving or kicking the player out. If 'ongoing', narrate the scene only.\n"
        "- Set current_mission_won true ONLY if computed_mission_outcome is 'won'.\n"
        "- You do NOT create missions or invent new story arcs. The mission chain is already fixed.\n"
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


# ---------------------------------------------------------------------------
# R4: Mission End Director - what a won/lost mission MEANS for the world
# ---------------------------------------------------------------------------

def build_r4_prompt(
    outcome: str,
    mission_context: dict[str, Any],
    culprit_states: dict[str, Any],
    r2_outputs: list[dict[str, Any]],
    player: PlayerSetup,
    world: WorldBible,
    conversation: list[dict[str, str]],
) -> tuple[str, dict]:
    system = (
        "You are the Mission End Director for a living world simulation.\n"
        "Your job: decide what the END of this mission means for the world and for the player. "
        "You run ONLY when the mission is definitively won or failed - never while it is ongoing.\n"
        "Rules:\n"
        "- outcome in your payload is already decided mechanically by the Mission Manager. NEVER change it.\n"
        "- You speak in the voice of the WORLD, not the player and not a narrator - you state consequences plainly.\n"
        "- CONSEQUENCES ARE DRIVEN BY THE CHARACTER'S LIVE STATS (culprit_states). For a FAILED mission:\n"
        "  * If suspicion >= 6 AND trust <= 2 -> severity 'harsh'. The character does not just leave: they act on it, "
        "e.g. MATSUDA directly reports the player to L. Emit a world_effect that raises the authority figure's "
        "suspicion of the player (character 'L', stat 'suspicion', positive delta) so the damage follows the player "
        "into future plans.\n"
        "  * Otherwise -> severity 'mild'. The character leaves politely ('ok, no problem, I'll go') with no further "
        "consequence, though the failed relationship is still remembered.\n"
        "- For a WON mission: the mission's reward is delivered - the character gives up the useful information "
        "the mission promised. Emit world_effects if the world genuinely changes (e.g. the character now trusts you "
        "more or shares a secret that raises their disclosure).\n"
        "- debrief.message is a short note DIRECTLY to the player about what just happened and what it means, e.g. "
        "'You failed the mission. The rest of the chain no longer makes sense - what will you do now?' "
        "Set debrief.location to where the player finds themselves now and debrief.who_is_around to the ids of "
        "characters in that place (the failed character is NOT among them - they already left).\n"
        "- memory is the affected character's REWRITTEN running memory: merge their prior memory (see culprit_states) "
        "with what they just did into ONE compact first-person summary (e.g. 'I already told L about this player - I "
        "won't trust them, but he keeps trying.'). It REPLACES the old memory - keep everything important, under ~120 words.\n"
        "- event_log is ONE line for the world events log (e.g. 'M1 lost - MATSUDA reported the player to L.'). It is a "
        "PERMANENT, undeniable fact that characters must treat as true from now on.\n"
        "- Output ONLY JSON matching the schema exactly. No extra text, no markdown."
    )
    user = {
        "task": f"Resolve the consequences of the {outcome.upper()} mission.",
        "computed_outcome": outcome,
        "mission_context": mission_context,
        "culprit_states": culprit_states,
        "request_2_outputs": r2_outputs,
        "player": player.model_dump(mode="json"),
        "world_lore": world.model_dump(mode="json"),
        "full_conversation_this_mission": conversation,
        "output_schema": {
            "severity": "str - 'mild' or 'harsh' (harsh only when a character's suspicion >= 6 and trust <= 2)",
            "action": "str - what the character actually does now (leaves politely / reports you to L / shares info on win)",
            "character": "str - the affected character's bible id (who memory is about)",
            "world_effects": [
                {
                    "character": "bible character id whose live stats change permanently",
                    "stat": "short stat name (trust/familiarity/respect/suspicion/rapport/disclosure_level/stress)",
                    "delta": "int - permanent change (small, e.g. +-2)",
                    "reason": "str - why"
                }
            ],
            "debrief": {
                "message": "str - direct note to the player about what happened and what it means",
                "location": "str - where the player is now",
                "who_is_around": ["bible character ids still present nearby (NOT the one who left)"]
            },
            "memory": "str - the affected character's REWRITTEN running memory (prior memory + what they just did, merged; replaces the old memory)",
            "event_log": "str - one line for the permanent world events log"
        },
    }
    return system, user
