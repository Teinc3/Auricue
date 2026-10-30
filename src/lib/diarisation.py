import asyncio
import json
import os
from collections.abc import AsyncIterator
from urllib.parse import urlencode
import websockets
from dotenv import load_dotenv

from ..models import DeepgramError, DeepgramMessageAdapter, DeepgramResults


load_dotenv()


class DeepgramAdapter:
    """Streams raw PCM bytes to Deepgram over WebSocket and yields results."""

    DEEPGRAM_WS_URL = "wss://api.deepgram.com/v1/listen"

    def __init__(
        self, model: str = "nova-3", sample_rate: int = 16000,
        channels: int = 1, endpointing: int = 300
    ) -> None:
        self.api_key = os.environ["DEEPGRAM_API_KEY"]
        self.model = model
        self.sample_rate = sample_rate
        self.channels = channels
        self.endpointing = endpointing

    def _build_url(self) -> str:
        """Build the Deepgram WebSocket URL with streaming query parameters."""

        query = urlencode({
            "model": self.model,
            "encoding": "linear16",
            "sample_rate": self.sample_rate,
            "channels": self.channels,
            "diarize": "true",
            "punctuate": "true",
            "smart_format": "true",
            "endpointing": str(self.endpointing),
            "no_delay": "true"
        })
        return f"{self.DEEPGRAM_WS_URL}?{query}"

    @staticmethod
    def _parse_results(raw: str | bytes) -> DeepgramResults | None:
        """Validate a raw WebSocket frame and return finalized Results."""

        msg = DeepgramMessageAdapter.validate_json(raw)
        if isinstance(msg, DeepgramError):
            raise RuntimeError(f"{msg.variant}: {msg.description}")
        if not isinstance(msg, DeepgramResults) or not msg.is_final:
            return None
        alts = msg.channel.alternatives
        if not alts or not alts[0].transcript.strip():
            return None
        return msg

    @staticmethod
    async def _pump_audio(
        audio_stream: AsyncIterator[bytes], ws: websockets.ClientConnection
    ) -> None:
        """Send raw binary PCM frames to Deepgram and close gracefully."""

        try:
            async for chunk in audio_stream:
                await ws.send(chunk)
            await ws.send(json.dumps({ "type": "CloseStream" }))
        except Exception:
            await ws.close()
            raise

    async def transcribe_stream(
        self, audio_stream: AsyncIterator[bytes]
    ) -> AsyncIterator[DeepgramResults]:
        """Stream raw PCM chunks and yield finalized DeepgramResults."""

        headers = { "Authorization": f"Token {self.api_key}" }
        async with websockets.connect(
            self._build_url(), additional_headers=headers
        ) as ws:
            sender = asyncio.create_task(self._pump_audio(audio_stream, ws))
            try:
                async for message in ws:
                    parsed = self._parse_results(message)
                    if parsed:
                        yield parsed
            finally:
                if not sender.done():
                    sender.cancel()
                else:
                    sender.result()


if __name__ == "__main__":
    from .bluetooth import BluetoothAdapter

    async def main() -> None:
        bt = BluetoothAdapter(device=0)
        dg = DeepgramAdapter(sample_rate=bt.sample_rate)
        print("Streaming mic audio to Deepgram...")
        async for res in dg.transcribe_stream(bt.read_stream()):
            alt = res.channel.alternatives[0]
            spk = alt.words[0].speaker if alt.words else 0
            print(f"[Speaker {spk}] ({alt.confidence:.2f}): {alt.transcript}")

    asyncio.run(main())


__all__ = ["DeepgramAdapter"]
