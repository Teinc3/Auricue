import asyncio
from collections.abc import AsyncIterator
from sounddevice import CallbackFlags, RawInputStream


class BluetoothAdapter:
    """Mock Bluetooth adapter with device microphone"""

    def __init__(
        self, device: int | None = 1,
        sample_rate: int = 16000, chunk_size: int = 1600
    ):
        self.device = device
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
            device=self.device, samplerate=self.sample_rate,
            blocksize=self.chunk_size, channels=1, dtype="int16",
            callback=_callback
        )
        with stream:
            while True:
                yield await queue.get()

    async def write_chunk(self, data: bytes) -> None:
        """Send audio bytes back to the earpiece."""

        # Wire to sd.RawOutputStream when TTS is added
        raise NotImplementedError(
            "BluetoothAdapter.write_chunk is not implemented yet"
        )


if __name__ == "__main__":
    import array
    import math

    def calculate_intensity(chunk: bytes) -> float:
        """Calculate normalized RMS intensity of a 16-bit PCM chunk."""

        if not chunk:
            return 0.0
        samples = array.array("h", chunk)
        return math.sqrt(sum(s * s for s in samples) / len(samples)) / 32768.0

    async def main() -> None:
        print("Starting BluetoothAdapter read stream on device 1...")
        adapter = BluetoothAdapter(device=1)
        async for chunk in adapter.read_stream():
            intensity = calculate_intensity(chunk)
            print(f"Chunk intensity: {intensity:.4f}")

    asyncio.run(main())


__all__ = ["BluetoothAdapter"]
