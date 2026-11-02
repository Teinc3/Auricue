from enum import StrEnum
from pydantic import BaseModel


class CueType(StrEnum):
    """Categories of conversational audio cues."""

    FACT = "FACT"
    CONTEXT = "CONTEXT"
    STRATEGY = "STRATEGY"
    OTHER = "OTHER"
    NONE = "NONE"


class CueWeight(StrEnum):
    """Per-session sensitivity weighting for each cue category."""

    NONE = "NONE"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class CueSource(BaseModel):
    """Grounding citation for an AgentCue."""

    authority: str
    uri: str
    year: int | None = None


class AgentCue(BaseModel):
    """Structured real-time cue emitted by GeminiAdapter."""

    cue_type: CueType
    content: str
    important: bool = False
    source: CueSource | None = None


class SpeakerProfile(BaseModel):
    """Compacted profile context for a single diarised speaker."""

    speaker_idx: int
    context: str


class ContextSummary(BaseModel):
    """Compacted session topic context and per-speaker profiles."""

    context: str
    speakers: list[SpeakerProfile] = []


__all__ = [
    "AgentCue", "ContextSummary", "CueSource", "CueType", "CueWeight",
    "SpeakerProfile"
]
