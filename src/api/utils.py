from contextlib import asynccontextmanager
from fastapi import FastAPI
from sounddevice import default as sd_default

from ..lib.db import DatabaseAdapter
from ..models.agent import CueType, CueWeight


db_adapter = DatabaseAdapter()
devices: dict[str, int | None] = {}
weights: dict[CueType, CueWeight] = {
    CueType.FACT: CueWeight.MEDIUM,
    CueType.CONTEXT: CueWeight.MEDIUM,
    CueType.STRATEGY: CueWeight.MEDIUM
}


async def async_noop() -> None:
    pass


def default_devices() -> dict[str, int | None]:
    """Resolve default sounddevice input/output IDs."""

    d_in, d_out = sd_default.device
    return {
        "device_in": d_in if d_in >= 0 else None,
        "device_out": d_out if d_out >= 0 else None
    }


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Initialise database and default audio devices."""

    devices.update(default_devices())
    await db_adapter.init()
    yield
    await db_adapter.close()


__all__ = [
    "db_adapter", "default_devices", "devices", "lifespan", "weights",
    "async_noop"
]
