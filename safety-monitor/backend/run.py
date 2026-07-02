"""Entry point: python run.py [--port 8765]"""

import argparse
import logging

import uvicorn

from safety_monitor.app import create_app


def main() -> None:
    parser = argparse.ArgumentParser(description="Safety Monitor backend")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--data-dir", default=None)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)
    app = create_app(args.data_dir)
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
