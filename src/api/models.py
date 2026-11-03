from typing import Literal
from pydantic import BaseModel

from ..models.agent import CueWeight


class DevicePatch(BaseModel):
    role: Literal["in", "out"]


class DevicesUpdate(BaseModel):
    device_in: int | None = None
    device_out: int | None = None


class WeightUpdate(BaseModel):
    value: CueWeight


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
    "DevicePatch", "DevicesUpdate", "SessionCreate", "SessionPatch",
    "WeightUpdate"
]

