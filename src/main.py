import asyncio
import sys
import uvicorn

from .api.app import app
from .controller import Controller


def setup_app_state(controller: Controller) -> None:
    """Wire controller callbacks into FastAPI app.state."""

    app.state.start = controller.start
    app.state.stop = controller.stop
    app.state.subscribe = controller.subscribers.add
    app.state.unsubscribe = controller.subscribers.discard
    app.state.is_running = lambda: controller.is_running
    app.state.get_session_id = lambda: (
        controller.session.id if controller.session else None
    )
    app.state.set_devices = controller.set_devices
    app.state.set_weight = controller.set_weight
    app.state.get_speaker = controller.speaker_info
    app.state.set_primary_speaker = controller.set_primary_speaker


async def main() -> None:
    """Bootstrap entry point for Auricue API server and Controller."""

    controller = Controller()
    if "--cli" in sys.argv:
        controller.bt.select_devices()
        print("Auricue active...")
        await controller.run()
        return
    setup_app_state(controller)
    config = uvicorn.Config(app, host="127.0.0.1", port=5731)
    server = uvicorn.Server(config)
    await server.serve()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nAuricue stopped.")
        exit(0)
