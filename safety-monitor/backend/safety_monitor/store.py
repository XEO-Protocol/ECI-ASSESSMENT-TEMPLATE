"""Local-first event storage: SQLite database + JPEG snapshots/clips on disk.

No cloud involved. `delete_all` implements the privacy control that wipes
the entire history, including media files.
"""

from __future__ import annotations

import json
import shutil
import sqlite3
import threading
from pathlib import Path

import numpy as np
from PIL import Image

from .models import AgentAssessment, Event, EventType, Severity

SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    id TEXT PRIMARY KEY,
    camera_id TEXT NOT NULL,
    type TEXT NOT NULL,
    severity TEXT NOT NULL,
    confidence REAL NOT NULL,
    message TEXT NOT NULL,
    created_at REAL NOT NULL,
    snapshot_path TEXT,
    clip_dir TEXT,
    acknowledged INTEGER NOT NULL DEFAULT 0,
    agent_assessment TEXT
);
CREATE INDEX IF NOT EXISTS idx_events_created ON events (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_events_camera ON events (camera_id);
"""


def save_jpeg(frame: np.ndarray, path: Path, quality: int = 85) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(frame).save(path, "JPEG", quality=quality)


class EventStore:
    def __init__(self, db_path: Path, snapshots_dir: Path, clips_dir: Path):
        self.db_path = db_path
        self.snapshots_dir = snapshots_dir
        self.clips_dir = clips_dir
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(SCHEMA)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.commit()

    # -- persistence -------------------------------------------------------

    def add(
        self,
        event: Event,
        snapshot: np.ndarray | None = None,
        clip_frames: list[np.ndarray] | None = None,
    ) -> Event:
        if snapshot is not None:
            path = self.snapshots_dir / f"{event.id}.jpg"
            save_jpeg(snapshot, path)
            event.snapshot_path = str(path)
        if clip_frames:
            clip_dir = self.clips_dir / event.id
            for i, frame in enumerate(clip_frames):
                save_jpeg(frame, clip_dir / f"{i:04d}.jpg")
            event.clip_dir = str(clip_dir)

        with self._lock:
            self._conn.execute(
                "INSERT INTO events (id, camera_id, type, severity, confidence,"
                " message, created_at, snapshot_path, clip_dir, acknowledged,"
                " agent_assessment) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (
                    event.id,
                    event.camera_id,
                    event.type.value,
                    event.severity.value,
                    event.confidence,
                    event.message,
                    event.created_at,
                    event.snapshot_path,
                    event.clip_dir,
                    int(event.acknowledged),
                    None,
                ),
            )
            self._conn.commit()
        return event

    def _row_to_event(self, row: sqlite3.Row) -> Event:
        assessment = None
        if row["agent_assessment"]:
            assessment = AgentAssessment.model_validate(
                json.loads(row["agent_assessment"])
            )
        return Event(
            id=row["id"],
            camera_id=row["camera_id"],
            type=EventType(row["type"]),
            severity=Severity(row["severity"]),
            confidence=row["confidence"],
            message=row["message"],
            created_at=row["created_at"],
            snapshot_path=row["snapshot_path"],
            clip_dir=row["clip_dir"],
            acknowledged=bool(row["acknowledged"]),
            agent_assessment=assessment,
        )

    # -- queries -----------------------------------------------------------

    def list(
        self,
        camera_id: str | None = None,
        event_type: str | None = None,
        since: float | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Event]:
        query = "SELECT * FROM events WHERE 1=1"
        params: list = []
        if camera_id:
            query += " AND camera_id = ?"
            params.append(camera_id)
        if event_type:
            query += " AND type = ?"
            params.append(event_type)
        if since is not None:
            query += " AND created_at >= ?"
            params.append(since)
        query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params += [limit, offset]
        with self._lock:
            rows = self._conn.execute(query, params).fetchall()
        return [self._row_to_event(r) for r in rows]

    def get(self, event_id: str) -> Event | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM events WHERE id = ?", (event_id,)
            ).fetchone()
        return self._row_to_event(row) if row else None

    # -- mutations ---------------------------------------------------------

    def acknowledge(self, event_id: str) -> bool:
        with self._lock:
            cur = self._conn.execute(
                "UPDATE events SET acknowledged = 1 WHERE id = ?", (event_id,)
            )
            self._conn.commit()
        return cur.rowcount > 0

    def set_assessment(self, event_id: str, assessment: AgentAssessment) -> bool:
        with self._lock:
            cur = self._conn.execute(
                "UPDATE events SET agent_assessment = ? WHERE id = ?",
                (json.dumps(assessment.model_dump(mode="json")), event_id),
            )
            self._conn.commit()
        return cur.rowcount > 0

    def delete_all(self) -> int:
        """Privacy control: wipe all events, snapshots and clips."""
        with self._lock:
            cur = self._conn.execute("DELETE FROM events")
            self._conn.commit()
        for directory in (self.snapshots_dir, self.clips_dir):
            if directory.exists():
                shutil.rmtree(directory)
            directory.mkdir(parents=True, exist_ok=True)
        return cur.rowcount

    def close(self) -> None:
        with self._lock:
            self._conn.close()
