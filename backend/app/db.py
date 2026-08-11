"""SQLite persistence (Piece 4) - game state + full LLM audit trail.

- Sessions: player setup, mission state, live character states, conversation.
- Turn logs: the raw R1/R2/R3 outputs + final GameTurn per turn, so we can
  always inspect exactly what the LLM did (debugging) and rebuild context.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel, create_engine, Session as DBSession, select

logger = logging.getLogger("db")

DB_DIR = Path(__file__).resolve().parents[1] / "data"
DB_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DB_DIR / "game.db"

engine = create_engine(f"sqlite:///{DB_PATH}", connect_args={"check_same_thread": False})


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class SessionRow(SQLModel, table=True):
    __tablename__ = "sessions"

    id: str = Field(primary_key=True, default_factory=lambda: uuid.uuid4().hex[:12])
    world_choice: str = ""
    skill_choice: str = ""
    player_setup: dict = Field(default_factory=dict, sa_column=Column(JSON))
    mission_state: dict = Field(default_factory=dict, sa_column=Column(JSON))
    character_states: dict = Field(default_factory=dict, sa_column=Column(JSON))
    conversation: list = Field(default_factory=list, sa_column=Column(JSON))
    created_at: str = Field(default_factory=_now)
    updated_at: str = Field(default_factory=_now)


class TurnLogRow(SQLModel, table=True):
    __tablename__ = "turn_logs"

    id: str = Field(primary_key=True, default_factory=lambda: uuid.uuid4().hex[:12])
    session_id: str = ""
    turn_number: int = 0
    player_input: str = ""
    r1_output: dict = Field(default_factory=dict, sa_column=Column(JSON))
    r2_outputs: list = Field(default_factory=list, sa_column=Column(JSON))
    r3_output: dict = Field(default_factory=dict, sa_column=Column(JSON))
    game_turn: dict = Field(default_factory=dict, sa_column=Column(JSON))
    model: str = ""
    provider: str = ""
    created_at: str = Field(default_factory=_now)


def init_db() -> None:
    SQLModel.metadata.create_all(engine)


def create_session(player_setup: dict, world_choice: str, skill_choice: str) -> SessionRow:
    with DBSession(engine) as db:
        row = SessionRow(
            world_choice=world_choice,
            skill_choice=skill_choice,
            player_setup=player_setup,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return row


def get_session(session_id: str) -> Optional[SessionRow]:
    with DBSession(engine) as db:
        return db.get(SessionRow, session_id)


def save_session_state(session_id: str, mission_state: dict, character_states: dict, conversation: list) -> None:
    with DBSession(engine) as db:
        row = db.get(SessionRow, session_id)
        if row is None:
            return
        row.mission_state = mission_state
        row.character_states = character_states
        row.conversation = conversation
        row.updated_at = _now()
        db.add(row)
        db.commit()


def log_turn(
    session_id: str,
    turn_number: int,
    player_input: str,
    r1_output: dict,
    r2_outputs: list,
    r3_output: dict,
    game_turn: dict,
    model: str,
    provider: str,
) -> None:
    with DBSession(engine) as db:
        db.add(
            TurnLogRow(
                session_id=session_id,
                turn_number=turn_number,
                player_input=player_input,
                r1_output=r1_output,
                r2_outputs=r2_outputs,
                r3_output=r3_output,
                game_turn=game_turn,
                model=model,
                provider=provider,
            )
        )
        db.commit()


def last_turn_number(session_id: str) -> int:
    with DBSession(engine) as db:
        rows = db.exec(select(TurnLogRow).where(TurnLogRow.session_id == session_id)).all()
    return max((r.turn_number for r in rows), default=0)
