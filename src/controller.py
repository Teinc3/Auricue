import asyncio
import time
from collections import deque
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from itertools import groupby

from .lib import (
    BluetoothAdapter,
    DatabaseAdapter,
    DeepgramAdapter,
    GeminiAdapter,
)
from .logger import close_session_log, logger, open_session_log
from .models import (
    CueType,
    CueWeight,
    DeepgramResults,
    LiveContext,
    Sentence,
    Session,
    Speaker,
)


class Controller:
    """Orchestrates live audio streaming, DB persistence, and TTS cues."""

    WINDOW_MAX = 100
    COMPACT_CHUNK = 50
    CUE_HISTORY_MAX = 15
    CUE_COOLDOWN = 5.0

    def __init__(self) -> None:
        self.bt = BluetoothAdapter()
        self.dg = DeepgramAdapter()
        self.agent = GeminiAdapter()
        self.db = DatabaseAdapter()
        self.weights: dict[CueType, CueWeight] = {
            CueType.FACT: CueWeight.MEDIUM,
            CueType.CONTEXT: CueWeight.MEDIUM,
            CueType.STRATEGY: CueWeight.MEDIUM
        }
        self.subscribers: set[asyncio.Queue[dict]] = set()
        self.primary_speaker: int | None = None
        self._stop_event = asyncio.Event()
        self._task: asyncio.Task[None] | None = None
        self._stream_t0 = 0.0
        self.start_new_session()

    @property
    def is_running(self) -> bool:
        return self._task is not None and not self._task.done()

    def emit(self, event_type: str, **payload: object) -> None:
        msg = { "type": event_type, **payload }
        for q in self.subscribers:
            q.put_nowait(msg)

    def set_devices(
        self, device_in: int | None = None, device_out: int | None = None
    ) -> None:
        """Update active input and/or output PortAudio device IDs."""

        if device_in is not None:
            self.bt.device_in = device_in
        if device_out is not None:
            self.bt.device_out = device_out

    def set_weight(self, cue_type: CueType, weight: CueWeight) -> None:
        """Update sensitivity weight for cue category."""

        self.weights[cue_type] = weight
        if cue_type == CueType.FACT:
            self.session.fact_weight = weight
        elif cue_type == CueType.CONTEXT:
            self.session.context_weight = weight
        elif cue_type == CueType.STRATEGY:
            self.session.strategy_weight = weight
        self.emit(
            "weights",
            weights={ k.value: v.value for k, v in self.weights.items() }
        )

    def speaker_info(self) -> dict[str, int | None]:
        """Return detected speaker count and the user's speaker index."""

        return {
            "speakerCount": len(self.speakers),
            "primarySpeaker": self.primary_speaker
        }

    def set_primary_speaker(self, idx: int | None) -> dict[str, int | None]:
        """Set the user's speaker index for this and later sessions."""

        self.primary_speaker = self.session.primary_speaker = idx
        info = self.speaker_info()
        self.emit("speaker", **info)
        return info

    def start_new_session(
        self, fact_weight: CueWeight | None = None,
        context_weight: CueWeight | None = None,
        strategy_weight: CueWeight | None = None
    ) -> None:
        """Initialise fresh per-recording session and pipeline buffers."""

        close_session_log()
        self.dg.sample_rate = self.bt.sample_rate
        fw = fact_weight or self.weights[CueType.FACT]
        cw = context_weight or self.weights[CueType.CONTEXT]
        sw = strategy_weight or self.weights[CueType.STRATEGY]
        self.session = Session(
            fact_weight=fw, context_weight=cw, strategy_weight=sw,
            primary_speaker=self.primary_speaker
        )
        self.speakers: dict[int, Speaker] = {}
        self.window: list[str] = []
        self.recent_cues: deque[str] = deque(maxlen=self.CUE_HISTORY_MAX)
        self.cue_queue: asyncio.Queue[
            tuple[Sentence, str, int]
        ] = asyncio.Queue()
        self._compact_task: asyncio.Task[None] | None = None
        self._seq = 0
        self._last_cue = -self.CUE_COOLDOWN
        self._stream_t0 = 0.0

    async def _timed_stream(self) -> AsyncIterator[bytes]:
        """Wrap audio stream, anchoring stream_t0 upon first yielded chunk."""

        self._stream_t0 = time.monotonic()
        self.session.start_time = datetime.now(UTC)
        async for chunk in self.bt.read_stream():
            if self._stop_event.is_set():
                break
            yield chunk

    async def _get_speaker(self, speaker_idx: int) -> Speaker:
        """Return cached session Speaker or persist a new one."""

        if speaker_idx not in self.speakers:
            spk = Speaker(
                session_id=self.session.id, speaker_idx=speaker_idx
            )
            await self.db.save(spk)
            self.speakers[speaker_idx] = spk
            self.emit("speaker", **self.speaker_info())
        return self.speakers[speaker_idx]

    async def _ingest_result(self, res: DeepgramResults) -> None:
        """Split DeepgramResults by speaker, persist, and enqueue."""

        now = time.monotonic()
        alt = res.channel.alternatives[0]
        base = self.session.start_time
        for spk_idx, grp in groupby(alt.words, key=lambda w: w.speaker):
            chunk = list(grp)
            text = " ".join(w.punctuated_word or w.word for w in chunk).strip()
            spk = await self._get_speaker(spk_idx)
            self._seq += 1
            word_end = chunk[-1].end
            dg_ms = max(0, int((now - (self._stream_t0 + word_end)) * 1000))
            sent = Sentence(
                session_id=self.session.id, speaker_id=spk.id,
                seq_num=self._seq, transcript=text,
                confidence_level=alt.confidence,
                diarisation_latency=dg_ms,
                start_time=base + timedelta(seconds=chunk[0].start),
                end_time=base + timedelta(seconds=word_end)
            )
            await self.db.save(sent)
            line = f"Speaker {spk_idx}: {text}"
            logger.info("[%dms] %s", dg_ms, line)
            self.window.append(line)
            self.cue_queue.put_nowait((sent, line, dg_ms))
            self.emit(
                "sentence", id=sent.id, seq_num=self._seq, speaker_idx=spk_idx,
                transcript=text, confidence=alt.confidence,
                diarisation_latency=dg_ms,
                start_time=sent.start_time.isoformat(),
                end_time=sent.end_time.isoformat()
            )

    async def _compact_context(self, flush: bool = False) -> None:
        """Summarise oldest COMPACT_CHUNK lines in background and update DB."""

        batch = self.window if flush else self.window[:self.COMPACT_CHUNK]
        if not batch:
            return
        spk_ctx = { k: v.context for k, v in self.speakers.items() }
        res = await self.agent.summarise_context(
            batch, self.session.context, spk_ctx, weights=self.session.weights
        )
        self.session.context = res.context
        for p in res.speakers:
            if p.speaker_idx in self.speakers:
                self.speakers[p.speaker_idx].context = p.context
        del self.window[:len(batch)]
        await self.db.save(self.session, *self.speakers.values())
        self.emit(
            "context", context=self.session.context,
            speakers=[
                { "speaker_idx": k, "context": v.context }
                for k, v in self.speakers.items()
            ]
        )

    async def _cue_worker(self) -> None:
        """Coalesce queued sentences, query Gemini, and speak cues."""

        while True:
            target_sent, first_line, dg_ms = await self.cue_queue.get()
            lines = [first_line]
            while not self.cue_queue.empty():
                target_sent, line, dg_ms = self.cue_queue.get_nowait()
                lines.append(line)
            spk_ctx = { k: v.context for k, v in self.speakers.items() }
            t0 = time.monotonic()
            cue = await self.agent.generate_cue(
                "\n".join(lines), history=self.window[:-len(lines)],
                context=self.session.context, cues=list(self.recent_cues),
                speakers=spk_ctx, weights=self.session.weights,
                primary_speaker=self.session.primary_speaker
            )
            agent_ms = int((time.monotonic() - t0) * 1000)
            if not cue:
                logger.debug("[%dms | %dms] No cue", dg_ms, agent_ms)
                continue
            self.recent_cues.append(f"[{cue.cue_type}] {cue.content}")
            src = cue.source.model_dump() if cue.source else None
            cooling = (time.monotonic() - self._last_cue) < self.CUE_COOLDOWN
            surfaced = cue.important or not cooling
            live_ctx = LiveContext(
                sentence_id=target_sent.id, cue_type=cue.cue_type, source=src,
                agent_latency=agent_ms, content=cue.content,
                important=cue.important, surfaced=surfaced
            )
            await self.db.save(live_ctx)
            self.emit(
                "cue", sentence_id=target_sent.id,
                cue_type=cue.cue_type.value, content=cue.content,
                important=cue.important, surfaced=surfaced, source=src,
                agent_latency=agent_ms
            )
            if not surfaced:
                logger.debug(
                    "[%dms | %dms] ~ Suppressed [%s] %s",
                    dg_ms, agent_ms, cue.cue_type, cue.content
                )
                continue
            tag = "!" if cue.important else "="
            logger.info(
                "[%dms | %dms] %s Cue [%s] %s (source=%s)",
                dg_ms, agent_ms, tag, cue.cue_type, cue.content, src
            )
            await self.bt.speak(cue.content, right=True)
            self._last_cue = time.monotonic()

    async def end_session(self) -> None:
        """Finalise session: compact trailing dialogue and stamp end time."""

        if self.session.end_time is not None:
            return
        if self._compact_task and not self._compact_task.done():
            self._compact_task.cancel()
            try:
                await self._compact_task
            except asyncio.CancelledError:
                pass
        self.session.end_time = datetime.now(UTC)
        if self.window:
            try:
                await self._compact_context(flush=True)
            except Exception as e:
                logger.warning("Final context compaction failed: %s", e)
        await self.db.save(self.session, *self.speakers.values())
        logger.debug(
            "Session %s ended. Context: %s", self.session.id,
            self.session.context
        )
        close_session_log()

    def start(self) -> None:
        """Spawn live session pipeline in background task."""

        if self.is_running:
            return
        self._stop_event.clear()
        self._task = asyncio.create_task(self._run_session())

    async def stop(self) -> None:
        """Signal stop to audio stream and await final session flush."""

        if not self.is_running or not self._task:
            return
        self._stop_event.set()
        await self._task

    async def _run_session(self) -> None:
        """Execute one complete recording session pipeline."""

        self.start_new_session()
        await self.db.init()
        await self.db.save(self.session)
        open_session_log(self.session.id)
        self.emit("status", running=True, session_id=self.session.id)
        worker = asyncio.create_task(self._cue_worker())
        try:
            async for res in self.dg.transcribe_stream(self._timed_stream()):
                await self._ingest_result(res)
                idle = not self._compact_task or self._compact_task.done()
                if len(self.window) >= self.WINDOW_MAX and idle:
                    self._compact_task = asyncio.create_task(
                        self._compact_context()
                    )
        finally:
            worker.cancel()
            await self.end_session()
            self.emit("status", running=False, session_id=self.session.id)

    async def run(self) -> None:
        """Run the non-blocking e2e pipeline."""

        try:
            await self._run_session()
        finally:
            await self.db.close()


__all__ = ["Controller"]
