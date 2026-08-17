"""Merge R1 + R2 into the single Game Turn JSON (Piece 5).

This is packaging only - no LLM work. It shapes the raw outputs into
the one contract the frontend and audio layer consume.
"""

from __future__ import annotations

from typing import Any, Optional

from .types import (
    CharacterBrainOutput,
    GameTurn,
    GameTurnCharacter,
    GameTurnMessage,
    GameTurnScene,
    SkillFeedback,
)


def _stat_deltas(char: CharacterBrainOutput) -> dict[str, int]:
    d = {}
    for name in ("trust", "familiarity", "respect", "suspicion", "rapport", "disclosure_level", "stress"):
        ch = getattr(char.stat_changes, name, None)
        if ch is not None and ch.delta != 0:
            d[name] = ch.delta
    return d


def merge_turn(
    turn_id: int,
    r1_output: SkillFeedback,
    r2_outputs: list[CharacterBrainOutput],
    player_input: str,
    player_name: str,
    characters_state: list[dict[str, Any]],
    scene_state: Optional[dict[str, Any]] = None,
) -> GameTurn:
    """Build the final GameTurn from the raw outputs and persisted state."""

    scene = GameTurnScene(
        title=scene_state.get("title", "") if scene_state else "",
        location=scene_state.get("location", "") if scene_state else "",
        characters=scene_state.get("present_ids", []) if scene_state else [],
        reason=scene_state.get("reason", "") if scene_state else "",
        strategic_plan=scene_state.get("strategic_plan", "") if scene_state else "",
        scene_hooks=[],
    )

    chars_by_id = {c["id"]: c for c in characters_state}
    characters: list[GameTurnCharacter] = []
    for out in r2_outputs:
        cid = out.character_id
        state = chars_by_id.get(cid, {})
        memory = list(state.get("memory", []))
        chars_by_id[cid]["memory"] = memory
        characters.append(
            GameTurnCharacter(
                id=cid,
                name=state.get("name", cid),
                stats=state.get("stats", {}),
                stat_deltas=_stat_deltas(out),
                memory=memory,
                current_problem=state.get("current_problem", ""),
                solution=state.get("solution", ""),
                problem_solving_framework=state.get("problem_solving_framework", ""),
                relationship_state=out.reasoning.relationship_state if out.reasoning else "",
                pfp=state.get("pfp", f"/pfp/{cid.lower()}.png"),
                present=state.get("present", True),
            )
        )

    messages: list[GameTurnMessage] = []
    if player_input.strip():
        messages.append(
            GameTurnMessage(
                speaker="PLAYER",
                text=player_input,
                skill_feedback=(
                    SkillFeedback.model_validate(r1_output.model_dump(mode="json"))
                    if r1_output.feedback_for_player.strip()
                    else None
                ),
            )
        )
    for out in r2_outputs:
        if out.dialogue.strip():
            messages.append(
                GameTurnMessage(
                    speaker=out.character_id,
                    text=out.dialogue,
                    inner_thought=out.inner_thought or None,
                    stat_deltas=_stat_deltas(out),
                )
            )

    return GameTurn(
        turn_id=turn_id,
        messages=messages,
        characters=characters,
        scene=scene,
    )
