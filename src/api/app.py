import asyncio
from datetime import UTC, datetime
from fastapi import HTTPException, WebSocketDisconnect
from sounddevice import query_devices
from sqlmodel import select

from ..models.agent import CueType
from ..models.db import LiveContext, Sentence, Session, Speaker
from .models import (
    AppRequest,
    AppState,
    AppWebSocket,
    AuricueApp,
    DevicePatch,
    DevicesUpdate,
    SessionCreate,
    SessionPatch,
    WeightUpdate,
)
from .utils import db_adapter, devices, lifespan, weights


app = AuricueApp(title="Auricue", lifespan=lifespan)
app.state = AppState()


async def _ws_sender(ws: AppWebSocket, q: asyncio.Queue[dict]) -> None:
    while True:
        await ws.send_json(await q.get())


@app.websocket("/api/session")
async def session_ws(ws: AppWebSocket) -> None:
    """Bidirectional live session control and event stream."""

    await ws.accept()
    q: asyncio.Queue[dict] = asyncio.Queue()
    ws.app.state.subscribe(q)
    await ws.send_json({
        "type": "status",
        "running": ws.app.state.is_running(),
        "session_id": ws.app.state.get_session_id()
    })
    sender = asyncio.create_task(_ws_sender(ws, q))
    try:
        while True:
            msg = await ws.receive_json()
            action = msg.get("action")
            if action == "start":
                ws.app.state.start()
            elif action == "stop":
                await ws.app.state.stop()
    except WebSocketDisconnect:
        pass
    finally:
        sender.cancel()
        ws.app.state.unsubscribe(q)


@app.get("/api/devices")
async def get_devices() -> dict:
    """List host audio devices and active selection."""

    devs = [
        {
            "id": d["index"], "name": d["name"],
            "inputs": d["max_input_channels"],
            "outputs": d["max_output_channels"]
        }
        for d in query_devices()
    ]
    return { "devices": devs, "selected": devices }


@app.patch("/api/devices")
async def update_devices(body: DevicesUpdate, req: AppRequest) -> dict:
    """Update selected input and output audio device IDs."""

    if body.device_in is not None:
        devices["device_in"] = body.device_in
    if body.device_out is not None:
        devices["device_out"] = body.device_out
    req.app.state.set_devices(body.device_in, body.device_out)
    return devices


@app.patch("/api/devices/{device_id}")
async def set_device_role(
    device_id: int, body: DevicePatch, req: AppRequest
) -> dict:
    """Assign device ID as current input or output."""

    key = "device_in" if body.role == "in" else "device_out"
    devices[key] = device_id
    if body.role == "in":
        req.app.state.set_devices(device_in=device_id)
    else:
        req.app.state.set_devices(device_out=device_id)
    return devices


@app.get("/api/weights")
async def get_weights() -> dict[str, str]:
    """Return active cue sensitivity weights."""

    return { k.value: v.value for k, v in weights.items() }


@app.get("/api/weights/{cue_type}")
async def get_weight(cue_type: CueType) -> dict[str, str]:
    """Return weight for single cue category."""

    if cue_type not in weights:
        raise HTTPException(status_code=404, detail="Unknown cue type")
    return { "cue_type": cue_type.value, "value": weights[cue_type].value }


@app.patch("/api/weights/{cue_type}")
async def set_weight(
    cue_type: CueType, body: WeightUpdate, req: AppRequest
) -> dict[str, str]:
    """Update sensitivity weight for cue category."""

    weights[cue_type] = body.value
    req.app.state.set_weight(cue_type, body.value)
    return { "cue_type": cue_type.value, "value": body.value.value }


@app.post("/api/session")
async def create_session(body: SessionCreate | None = None) -> Session:
    """Create and persist a new conversation session."""

    fw = (body and body.fact_weight) or weights[CueType.FACT]
    cw = (body and body.context_weight) or weights[CueType.CONTEXT]
    sw = (body and body.strategy_weight) or weights[CueType.STRATEGY]
    sess = Session(fact_weight=fw, context_weight=cw, strategy_weight=sw)
    await db_adapter.save(sess)
    return sess


@app.get("/api/sessions")
async def list_sessions() -> list[Session]:
    """List all persisted conversation sessions."""

    async with db_adapter.sessions() as s:
        res = await s.execute(select(Session).order_by(Session.id.desc()))
        return list(res.scalars().all())


@app.get("/api/session")
async def get_latest_session() -> Session:
    """Get the latest conversation session."""

    async with db_adapter.sessions() as s:
        res = await s.execute(select(Session).order_by(Session.id.desc()))
        sess = res.scalars().first()
        if not sess:
            raise HTTPException(status_code=404, detail="No session found")
        return sess


@app.get("/api/session/{session_id}")
async def get_session(session_id: int) -> Session:
    """Get single session by ID."""

    async with db_adapter.sessions() as s:
        res = await s.execute(select(Session).where(Session.id == session_id))
        sess = res.scalars().first()
        if not sess:
            raise HTTPException(status_code=404, detail="Session not found")
        return sess


@app.patch("/api/session/{session_id}")
async def patch_session(session_id: int, body: SessionPatch) -> Session:
    """Update mutable fields on a session."""

    async with db_adapter.sessions() as s:
        res = await s.execute(select(Session).where(Session.id == session_id))
        sess = res.scalars().first()
        if not sess:
            raise HTTPException(status_code=404, detail="Session not found")
        if body.context is not None:
            sess.context = body.context
        if body.end_session:
            sess.end_time = datetime.now(UTC)
        if body.fact_weight is not None:
            sess.fact_weight = body.fact_weight
        if body.context_weight is not None:
            sess.context_weight = body.context_weight
        if body.strategy_weight is not None:
            sess.strategy_weight = body.strategy_weight
        s.add(sess)
        await s.commit()
        await s.refresh(sess)
        return sess


@app.get("/api/session/{session_id}/speakers")
async def get_session_speakers(session_id: int) -> list[Speaker]:
    """List all speakers for session."""

    async with db_adapter.sessions() as s:
        stmt = (
            select(Speaker)
            .where(Speaker.session_id == session_id)
            .order_by(Speaker.speaker_idx.asc())
        )
        res = await s.execute(stmt)
        return list(res.scalars().all())


@app.get("/api/session/{session_id}/speaker/{speaker_idx}")
async def get_session_speaker(session_id: int, speaker_idx: int) -> Speaker:
    """Get speaker profile context by speaker index."""

    async with db_adapter.sessions() as s:
        stmt = select(Speaker).where(
            Speaker.session_id == session_id,
            Speaker.speaker_idx == speaker_idx
        )
        res = await s.execute(stmt)
        spk = res.scalars().first()
        if not spk:
            raise HTTPException(status_code=404, detail="Speaker not found")
        return spk


@app.get("/api/session/{session_id}/sentences")
@app.get("/api/session/{session_id}/transcripts")
async def get_session_sentences(session_id: int) -> list[Sentence]:
    """List diarised sentences in chronological order."""

    async with db_adapter.sessions() as s:
        stmt = (
            select(Sentence)
            .where(Sentence.session_id == session_id)
            .order_by(Sentence.seq_num.asc())
        )
        res = await s.execute(stmt)
        return list(res.scalars().all())


@app.get("/api/session/{session_id}/cues")
@app.get("/api/session/{session_id}/contexts")
async def get_session_cues(session_id: int) -> list[LiveContext]:
    """List all generated cues for session."""

    async with db_adapter.sessions() as s:
        stmt = (
            select(LiveContext)
            .join(Sentence, LiveContext.sentence_id == Sentence.id)
            .where(Sentence.session_id == session_id)
            .order_by(LiveContext.id.asc())
        )
        res = await s.execute(stmt)
        return list(res.scalars().all())


__all__ = ["app"]
