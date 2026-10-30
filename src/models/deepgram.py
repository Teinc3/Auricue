from typing import Annotated, Literal
from pydantic import BaseModel, Field, TypeAdapter


class DeepgramWord(BaseModel):
    """Word-level transcription and speaker diarisation entry."""

    word: str
    start: float
    end: float
    confidence: float
    punctuated_word: str | None = None
    speaker: int | None = None


class DeepgramAlternative(BaseModel):
    """Single transcription alternative for a channel."""

    transcript: str
    confidence: float
    words: list[DeepgramWord] = []


class DeepgramChannel(BaseModel):
    """Audio channel transcription container."""

    alternatives: list[DeepgramAlternative]


class DeepgramResults(BaseModel):
    """Inbound Deepgram live transcription Results frame."""

    type: Literal["Results"] = "Results"
    channel_index: list[int]
    duration: float
    start: float
    is_final: bool = False
    speech_final: bool = False
    from_finalize: bool = False
    channel: DeepgramChannel


class DeepgramMetadata(BaseModel):
    """Inbound Deepgram session Metadata frame."""

    type: Literal["Metadata"] = "Metadata"
    transaction_key: str
    request_id: str
    sha256: str
    created: str
    duration: float
    channels: int


class DeepgramSpeechStarted(BaseModel):
    """Inbound Deepgram VAD SpeechStarted frame."""

    type: Literal["SpeechStarted"] = "SpeechStarted"
    channel: list[int]
    timestamp: float


class DeepgramUtteranceEnd(BaseModel):
    """Inbound Deepgram UtteranceEnd frame."""

    type: Literal["UtteranceEnd"] = "UtteranceEnd"
    channel: list[int]
    last_word_end: float


class DeepgramError(BaseModel):
    """Inbound Deepgram Error frame."""

    type: Literal["Error"] = "Error"
    variant: str
    description: str
    code: str | None = None
    message: str | None = None


DeepgramMessage = Annotated[
    DeepgramResults
    | DeepgramMetadata
    | DeepgramSpeechStarted
    | DeepgramUtteranceEnd
    | DeepgramError,
    Field(discriminator="type")
]
DeepgramMessageAdapter: TypeAdapter[DeepgramMessage] = TypeAdapter(
    DeepgramMessage
)


__all__ = [
    "DeepgramAlternative", "DeepgramChannel", "DeepgramError",
    "DeepgramMessage", "DeepgramMessageAdapter", "DeepgramMetadata",
    "DeepgramResults", "DeepgramSpeechStarted", "DeepgramUtteranceEnd",
    "DeepgramWord"
]
