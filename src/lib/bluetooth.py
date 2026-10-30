import array
import asyncio
import tempfile
import wave
from collections.abc import AsyncIterator
from sounddevice import (
    CallbackFlags,
    CoreAudioSettings,
    RawInputStream,
    RawOutputStream,
)


class BluetoothAdapter:
    """Mock Bluetooth adapter with device microphone"""

    def __init__(
        self, device_in: int | None = 0, device_out: int | None = 1,
        sample_rate: int = 16000, chunk_size: int = 1600
    ):
        self.device_in = device_in
        self.device_out = device_out
        self.sample_rate = sample_rate
        self.chunk_size = chunk_size

    async def read_stream(self) -> AsyncIterator[bytes]:
        """Read raw 16-bit mono PCM chunks from the host microphone."""

        loop = asyncio.get_running_loop()
        queue: asyncio.Queue[bytes] = asyncio.Queue()

        def _callback(
            data: bytes, frames: int, time_info: object, status: CallbackFlags
        ):
            loop.call_soon_threadsafe(queue.put_nowait, bytes(data))

        stream = RawInputStream(
            device=self.device_in, samplerate=self.sample_rate,
            blocksize=self.chunk_size, channels=1, dtype="int16",
            callback=_callback
        )
        with stream:
            while True:
                yield await queue.get()

    async def write_chunk(
        self, data: bytes, right: bool | None = None, vol: float = 1.0
    ) -> None:
        """Send audio bytes back to the earpiece."""

        if vol != 1.0:
            samples = array.array("h", data)
            data = array.array("h", (int(s * vol) for s in samples)).tobytes()

        settings = (
            None if right is None
            else CoreAudioSettings(channel_map=[-1, 0] if right else [0, -1])
        )

        def _play() -> None:
            with RawOutputStream(
                device=self.device_out, samplerate=self.sample_rate,
                channels=1, dtype="int16", extra_settings=settings
            ) as s:
                s.write(data)

        await asyncio.to_thread(_play)

    async def speak(
        self, text: str, right: bool | None = None, vol: float = 1.0
    ) -> None:
        """Synthesize text via macOS say and play on the output device."""

        with tempfile.NamedTemporaryFile(suffix=".wav") as tmp:
            proc = await asyncio.create_subprocess_exec(
                "say", "-o", tmp.name,
                f"--data-format=LEI16@{self.sample_rate}", text
            )
            await proc.wait()
            with wave.open(tmp.name, "rb") as wf:
                data = wf.readframes(wf.getnframes())
        await self.write_chunk(data, right=right, vol=vol)


if __name__ == "__main__":
    async def main() -> None:
        adapter = BluetoothAdapter(device_in=0, device_out=1)
        await adapter.speak("I love skibidi toilet.")
    asyncio.run(main())


__all__ = ["BluetoothAdapter"]
