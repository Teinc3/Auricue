import asyncio
from collections.abc import AsyncIterator
from sounddevice import CallbackFlags, RawInputStream, RawOutputStream


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

    async def write_chunk(self, data: bytes) -> None:
        """Send audio bytes back to the earpiece."""

        def _play() -> None:
            with RawOutputStream(
                device=self.device_out, samplerate=self.sample_rate,
                channels=1, dtype="int16"
            ) as s:
                s.write(data)

        await asyncio.to_thread(_play)


if __name__ == "__main__":
    import array
    import math

    async def beep(adapter: BluetoothAdapter, freq: float = 440.0) -> None:
        """Play a 440 Hz test tone on the output device."""

        n = int(adapter.sample_rate * 1)
        amp = int(32767 * 0.05)
        step = 2.0 * math.pi * freq / adapter.sample_rate
        pcm = array.array(
            "h", (int(amp * math.sin(i * step)) for i in range(n))
        )
        await adapter.write_chunk(pcm.tobytes())

    async def main() -> None:
        adapter = BluetoothAdapter(device_in=0, device_out=1)
        print(f"Playing 440Hz test tone on device {adapter.device_out}...")
        await beep(adapter)

    asyncio.run(main())


__all__ = ["BluetoothAdapter"]
