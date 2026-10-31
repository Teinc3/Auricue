from datetime import datetime
from sqlalchemy import JSON, UniqueConstraint
from sqlmodel import Field, SQLModel

from .agent import CueType


class Session(SQLModel, table=True):
    """Conversation session holding rolling compacted topic context."""

    id: int | None = Field(default=None, primary_key=True)
    context: str = ""
    start_time: datetime = Field(default_factory=datetime.utcnow)
    end_time: datetime | None = None


class Speaker(SQLModel, table=True):
    """Session-scoped diarised speaker profile."""

    # Session-scoped speaker
    # link to global profile if trans-session state identification added
    __table_args__ = (UniqueConstraint("session_id", "speaker_idx"),)

    id: int | None = Field(default=None, primary_key=True)
    session_id: int = Field(foreign_key="session.id", index=True)
    speaker_idx: int
    context: str = ""


class Sentence(SQLModel, table=True):
    """Diarised utterance persisted in session sequence order."""

    __table_args__ = (UniqueConstraint("session_id", "seq_num"),)

    id: int | None = Field(default=None, primary_key=True)
    session_id: int = Field(foreign_key="session.id", index=True)
    speaker_id: int = Field(foreign_key="speaker.id")
    seq_num: int
    transcript: str
    confidence_level: float
    start_time: datetime
    end_time: datetime


class LiveContext(SQLModel, table=True):
    """Generated audio cue linked to its triggering Sentence."""

    id: int | None = Field(default=None, primary_key=True)
    sentence_id: int = Field(foreign_key="sentence.id", index=True)
    content: str
    cue_type: CueType
    source: dict | None = Field(default=None, sa_type=JSON)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    surfaced: bool = False


__all__ = ["LiveContext", "Sentence", "Session", "Speaker"]
