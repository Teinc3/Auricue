from enum import StrEnum
from pydantic import BaseModel


class CueType(StrEnum):
    """Categories of conversational audio cues."""

    FACT = "FACT"
    CONTEXT = "CONTEXT"
    STRATEGY = "STRATEGY"
    OTHER = "OTHER"
    NONE = "NONE"


class CueSource(BaseModel):
    """Grounding citation for an AgentCue."""

    authority: str
    uri: str
    year: int | None = None


class AgentCue(BaseModel):
    """Structured real-time cue emitted by GeminiAdapter."""

    cue_type: CueType
    content: str
    source: CueSource | None = None


__all__ = ["AgentCue", "CueSource", "CueType"]
