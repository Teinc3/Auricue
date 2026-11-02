import asyncio
import time
from collections import deque
from datetime import UTC, datetime, timedelta
from itertools import groupby

from ..lib import (
    BluetoothAdapter,
    DatabaseAdapter,
    DeepgramAdapter,
    GeminiAdapter,
)
from ..models import DeepgramResults, LiveContext, Sentence, Session, Speaker


class Controller:
    """Orchestrates live audio streaming, DB persistence, and TTS cues."""

    WINDOW_MAX = 200
    COMPACT_CHUNK = 100
    CUE_HISTORY_MAX = 15
    CUE_COOLDOWN = 5.0

    def __init__(self) -> None:
        self.bt = BluetoothAdapter()
        self.dg = DeepgramAdapter()
        self.agent = GeminiAdapter()
        self.db = DatabaseAdapter()
        self.start_new_session()

    def start_new_session(self) -> None:
        """Initialise fresh per-recording session and pipeline buffers."""

        self.dg.sample_rate = self.bt.sample_rate
        self.session = Session()
        self.speakers: dict[int, Speaker] = {}
        self.window: list[str] = []
        self.recent_cues: deque[str] = deque(maxlen=self.CUE_HISTORY_MAX)
        self.cue_queue: asyncio.Queue[tuple[Sentence, str]] = asyncio.Queue()
        self._compact_task: asyncio.Task[None] | None = None
        self._seq = 0
        self._last_cue = -self.CUE_COOLDOWN

    async def _get_speaker(self, speaker_idx: int) -> Speaker:
        """Return cached session Speaker or persist a new one."""

        if speaker_idx not in self.speakers:
            spk = Speaker(
                session_id=self.session.id, speaker_idx=speaker_idx
            )
            await self.db.save(spk)
            self.speakers[speaker_idx] = spk
        return self.speakers[speaker_idx]

    async def _ingest_result(self, res: DeepgramResults) -> None:
        """Split DeepgramResults by speaker, persist, and enqueue."""

        alt = res.channel.alternatives[0]
        base = self.session.start_time
        for spk_idx, grp in groupby(alt.words, key=lambda w: w.speaker):
            chunk = list(grp)
            text = " ".join(w.punctuated_word or w.word for w in chunk).strip()
            spk = await self._get_speaker(spk_idx)
            self._seq += 1
            sent = Sentence(
                session_id=self.session.id, speaker_id=spk.id,
                seq_num=self._seq, transcript=text,
                confidence_level=alt.confidence,
                start_time=base + timedelta(seconds=chunk[0].start),
                end_time=base + timedelta(seconds=chunk[-1].end)
            )
            await self.db.save(sent)
            line = f"Speaker {spk_idx}: {text}"
            print(line)
            self.window.append(line)
            self.cue_queue.put_nowait((sent, line))

    async def _compact_context(self) -> None:
        """Summarise oldest COMPACT_CHUNK lines in background and update DB."""

        batch = self.window[:self.COMPACT_CHUNK]
        spk_ctx = { k: v.context for k, v in self.speakers.items() }
        res = await self.agent.summarise_context(
            batch, self.session.context, spk_ctx
        )
        self.session.context = res.context
        for p in res.speakers:
            if p.speaker_idx in self.speakers:
                self.speakers[p.speaker_idx].context = p.context
        del self.window[:len(batch)]
        await self.db.save(self.session, *self.speakers.values())

    async def _cue_worker(self) -> None:
        """Coalesce queued sentences, query Gemini, and speak cues."""

        while True:
            target_sent, first_line = await self.cue_queue.get()
            lines = [first_line]
            while not self.cue_queue.empty():
                target_sent, line = self.cue_queue.get_nowait()
                lines.append(line)
            spk_ctx = { k: v.context for k, v in self.speakers.items() }
            cue = await self.agent.generate_cue(
                "\n".join(lines), history=self.window[:-len(lines)],
                context=self.session.context, cues=list(self.recent_cues),
                speakers=spk_ctx
            )
            if not cue:
                continue
            self.recent_cues.append(f"[{cue.cue_type}] {cue.content}")
            src = cue.source.model_dump() if cue.source else None
            cooling = (time.monotonic() - self._last_cue) < self.CUE_COOLDOWN
            surfaced = cue.important or not cooling
            live_ctx = LiveContext(
                sentence_id=target_sent.id, cue_type=cue.cue_type, source=src,
                content=cue.content, important=cue.important, surfaced=surfaced,
            )
            await self.db.save(live_ctx)
            if not surfaced:
                print(f"~ Suppressed [{cue.cue_type}] {cue.content}")
                continue
            tag = "!" if cue.important else "="
            print(f"{tag} Cue [{cue.cue_type}] {cue.content} (source={src})")
            await self.bt.speak(cue.content, right=True)
            self._last_cue = time.monotonic()

    async def run(self) -> None:
        """Run the non-blocking audio -> STT -> Gemini -> TTS pipeline."""

        self.start_new_session()
        await self.db.init()
        await self.db.save(self.session)
        worker = asyncio.create_task(self._cue_worker())
        try:
            async for res in self.dg.transcribe_stream(self.bt.read_stream()):
                await self._ingest_result(res)
                idle = not self._compact_task or self._compact_task.done()
                if len(self.window) >= self.WINDOW_MAX and idle:
                    self._compact_task = asyncio.create_task(
                        self._compact_context()
                    )
        finally:
            worker.cancel()
            if self._compact_task:
                self._compact_task.cancel()
            self.session.end_time = datetime.now(UTC)
            await self.db.save(self.session)
            await self.db.close()


__all__ = ["Controller"]
