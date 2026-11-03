import asyncio
from collections.abc import Awaitable, Callable
from typing import Literal
from fastapi import FastAPI, Request, WebSocket
from pydantic import BaseModel, Field
from starlette.datastructures import State

from ..models.agent import CueType, CueWeight
from .utils import async_noop


class AppState(State):
    """Typed application state for Controller lifecycle actions."""

    start: Callable[[], None]
    stop: Callable[[], Awaitable[None]]
    subscribe: Callable[[asyncio.Queue[dict]], None]
    unsubscribe: Callable[[asyncio.Queue[dict]], None]
    is_running: Callable[[], bool]
    get_session_id: Callable[[], int | None]
    set_devices: Callable[..., None]
    set_weight: Callable[[CueType, CueWeight], None]
    get_speaker: Callable[[], dict[str, int | None]]
    set_primary_speaker: Callable[[int | None], dict[str, int | None]]

    def __init__(self) -> None:
        super().__init__()
        self.start = lambda: None
        self.stop = async_noop
        self.subscribe = lambda _: None
        self.unsubscribe = lambda _: None
        self.is_running = lambda: False
        self.get_session_id = lambda: None
        self.set_devices = lambda _in=None, _out=None: None
        self.set_weight = lambda _t, _w: None
        self.get_speaker = lambda: {}
        self.set_primary_speaker = lambda _: {}


class AuricueApp(FastAPI):
    state: AppState


class AppRequest(Request):
    @property
    def app(self) -> AuricueApp:
        return self.scope["app"]  # type: ignore[return-value]


class AppWebSocket(WebSocket):
    @property
    def app(self) -> AuricueApp:
        return self.scope["app"]  # type: ignore[return-value]


class DevicePatch(BaseModel):
    role: Literal["in", "out"]


class DevicesUpdate(BaseModel):
    device_in: int | None = None
    device_out: int | None = None


class WeightUpdate(BaseModel):
    value: CueWeight


class SpeakerUpdate(BaseModel):
    primarySpeaker: int | None = Field(default=None, ge=0)


class SessionCreate(BaseModel):
    fact_weight: CueWeight | None = None
    context_weight: CueWeight | None = None
    strategy_weight: CueWeight | None = None


class SessionPatch(BaseModel):
    context: str | None = None
    end_session: bool | None = None
    fact_weight: CueWeight | None = None
    context_weight: CueWeight | None = None
    strategy_weight: CueWeight | None = None


__all__ = [
    "AppRequest", "AppState", "AppWebSocket", "AuricueApp", "DevicePatch",
    "DevicesUpdate", "SessionCreate", "SessionPatch", "SpeakerUpdate",
    "WeightUpdate"
]
