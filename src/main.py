import asyncio

from .controller import Controller


async def main() -> None:
    controller = Controller()
    controller.bt.select_devices()
    print("Auricue active...")
    await controller.run()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nAuricue stopped.")
        exit(0)
