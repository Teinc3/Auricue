from enum import StrEnum
from pydantic import BaseModel


class CueType(StrEnum):
    """Categories of conversational audio cues."""

    FACT = "FACT"
    CONTEXT = "CONTEXT"
    STRATEGY = "STRATEGY"
    OTHER = "OTHER"


class AgentCue(BaseModel):
    """Structured real-time cue emitted by GeminiAdapter."""

    cue_type: CueType
    content: str
    source: str | None = None


__all__ = ["AgentCue", "CueType"]
