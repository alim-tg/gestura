import argparse
import logging
import sys

from .config import Settings
from .model import ensure_model


def main():
    parser = argparse.ArgumentParser(prog="gestura")
    sub = parser.add_subparsers(dest="command", required=True)
    serve = sub.add_parser("serve", help="camera, recognition and web UI")
    serve.add_argument("--camera", type=int, default=Settings.camera)
    serve.add_argument("--width", type=int, default=Settings.width)
    serve.add_argument("--height", type=int, default=Settings.height)
    serve.add_argument("--hands", type=int, default=Settings.max_hands)
    serve.add_argument("--no-mirror", action="store_true")
    serve.add_argument("--host", default=Settings.host)
    serve.add_argument("--port", type=int, default=Settings.port)
    sub.add_parser("model", help="download the MediaPipe gesture model")
    args = parser.parse_args(sys.argv[1:] or ["serve"])

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s", datefmt="%H:%M:%S")
    ensure_model()
    if args.command == "model":
        return

    import uvicorn

    from .power import disable_power_throttling
    from .server import create_app

    disable_power_throttling()
    settings = Settings(
        camera=args.camera,
        width=args.width,
        height=args.height,
        max_hands=args.hands,
        mirror=not args.no_mirror,
        host=args.host,
        port=args.port,
    )
    print(f"gestura on http://{settings.host}:{settings.port}")
    uvicorn.run(create_app(settings), host=settings.host, port=settings.port, log_level="warning", timeout_graceful_shutdown=2)
