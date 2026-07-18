"""Entry point: python run.py [--port 8765] [--https-port 8766]

Two listeners, one app, one process:

- http://127.0.0.1:<port>   — the full API, loopback only (desktop app,
  local agents). Never bound to the LAN.
- https://<lan-ip>:<https-port> — the PHONE SURFACE only (pairing page,
  claim endpoint, frame websocket; see PhoneSurfaceApp). HTTPS because
  phone browsers only allow camera access in a secure context. The
  certificate is a locally generated self-signed cert — the phone shows
  a one-time warning; accepting it stays on your LAN.

Pass --no-https to disable the LAN listener entirely (desktop-only use).
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import subprocess
from pathlib import Path

import uvicorn

from safety_monitor.app import PhoneSurfaceApp, create_app
from safety_monitor.config import DEFAULT_DATA_DIR
from safety_monitor.pairing import lan_ip

logger = logging.getLogger(__name__)


def ensure_tls_cert(data_dir: Path) -> tuple[Path, Path] | None:
    """Create (once) and return a local self-signed cert/key pair."""
    tls_dir = data_dir / "tls"
    cert, key = tls_dir / "cert.pem", tls_dir / "key.pem"
    if cert.is_file() and key.is_file():
        return cert, key
    tls_dir.mkdir(parents=True, exist_ok=True)
    try:
        subprocess.run(
            [
                "openssl", "req", "-x509",
                "-newkey", "ec", "-pkeyopt", "ec_paramgen_curve:prime256v1",
                "-keyout", str(key), "-out", str(cert),
                "-days", "825", "-nodes",
                "-subj", "/CN=Safety Monitor Hub",
                "-addext",
                f"subjectAltName=DNS:localhost,IP:127.0.0.1,IP:{lan_ip()}",
            ],
            check=True,
            capture_output=True,
        )
        os.chmod(key, 0o600)
        return cert, key
    except Exception as exc:  # openssl missing/failed: run without LAN listener
        logger.error("could not create TLS certificate (%s) — phone pairing "
                     "over the LAN is disabled", exc)
        return None


def main() -> None:
    parser = argparse.ArgumentParser(description="Safety Monitor backend")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--https-port", type=int, default=8766)
    parser.add_argument("--no-https", action="store_true",
                        help="disable the LAN phone-camera listener")
    parser.add_argument("--data-dir", default=None)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)
    app = create_app(args.data_dir)

    servers = [
        uvicorn.Server(
            uvicorn.Config(app, host=args.host, port=args.port, log_level="info")
        )
    ]

    if not args.no_https:
        data_dir = Path(args.data_dir) if args.data_dir else DEFAULT_DATA_DIR
        tls = ensure_tls_cert(data_dir)
        if tls:
            cert, key = tls
            app.state.phone_base_url = f"https://{lan_ip()}:{args.https_port}"
            servers.append(
                uvicorn.Server(
                    uvicorn.Config(
                        PhoneSurfaceApp(app),
                        host="0.0.0.0",
                        port=args.https_port,
                        ssl_certfile=str(cert),
                        ssl_keyfile=str(key),
                        log_level="info",
                    )
                )
            )
            logger.info("phone pairing listener on %s", app.state.phone_base_url)

    async def serve_all() -> None:
        await asyncio.gather(*(s.serve() for s in servers))

    asyncio.run(serve_all())


if __name__ == "__main__":
    main()
