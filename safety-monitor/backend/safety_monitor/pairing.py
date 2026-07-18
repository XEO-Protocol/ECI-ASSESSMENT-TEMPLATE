"""Phone/tablet pairing: one-time tokens that onboard a device as a camera.

Flow (all local, no cloud, no account):
1. Desktop asks POST /api/pairing/start -> a single-use token valid for
   PAIRING_TTL seconds, plus the LAN URL the phone should open.
2. Desktop shows that URL as a QR code (GET /api/pairing/{token}/qr.png).
3. The phone scans it, opens the camera page, and claims the token
   (POST /api/pairing/claim) with a chosen camera name.
4. Claiming consumes the token, creates a camera with source_type
   "phone" and a fresh per-device secret (device_key), and returns both
   to the phone. The phone then streams JPEG frames over
   /ws/phone/{camera_id}, authenticated with that key.

Security model (MVP, LAN-scoped): the token is 128-bit, single-use and
short-lived; the device_key is 256-bit and checked on every stream
connection. Keys live only in the local settings.json. The broader
auth hardening (bearer tokens for all APIs) lands with the security
phase of the roadmap.
"""

from __future__ import annotations

import secrets
import socket
import threading
import time
from dataclasses import dataclass, field

PAIRING_TTL = 600.0  # seconds a pairing token stays valid


def lan_ip() -> str:
    """Best-effort LAN address of this machine (no traffic is sent)."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("10.255.255.255", 1))
            return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"


@dataclass
class PairingToken:
    token: str
    created_at: float = field(default_factory=time.monotonic)
    claimed_camera_id: str | None = None

    def expired(self, now: float | None = None) -> bool:
        return ((now or time.monotonic()) - self.created_at) > PAIRING_TTL


class PairingManager:
    """In-memory registry of pending pairing tokens (single-use)."""

    def __init__(self) -> None:
        self._tokens: dict[str, PairingToken] = {}
        self._lock = threading.Lock()

    def start(self) -> PairingToken:
        token = PairingToken(token=secrets.token_urlsafe(16))
        with self._lock:
            self._prune()
            self._tokens[token.token] = token
        return token

    def get(self, token: str) -> PairingToken | None:
        with self._lock:
            entry = self._tokens.get(token)
            if entry is None or entry.expired():
                return None
            return entry

    def claim(self, token: str, camera_id: str) -> bool:
        """Consume a token for a newly created camera. False if invalid,
        expired, or already claimed."""
        with self._lock:
            entry = self._tokens.get(token)
            if entry is None or entry.expired() or entry.claimed_camera_id:
                return False
            entry.claimed_camera_id = camera_id
            return True

    def status(self, token: str) -> dict:
        with self._lock:
            entry = self._tokens.get(token)
            if entry is None or (entry.expired() and not entry.claimed_camera_id):
                return {"status": "expired"}
            if entry.claimed_camera_id:
                return {"status": "claimed", "camera_id": entry.claimed_camera_id}
            return {"status": "pending"}

    def _prune(self) -> None:
        now = time.monotonic()
        dead = [
            k
            for k, v in self._tokens.items()
            if v.expired(now) and not v.claimed_camera_id
        ]
        for k in dead:
            del self._tokens[k]


def new_device_key() -> str:
    return secrets.token_hex(32)  # 256-bit per-device stream secret
