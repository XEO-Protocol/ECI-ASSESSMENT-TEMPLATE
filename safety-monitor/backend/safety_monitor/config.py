"""Configuration and local-first data directory handling.

All data (settings, event database, snapshots, clips) lives under a single
local directory. Nothing is uploaded anywhere by default.
"""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path

from .models import CameraSettings, Settings

DEFAULT_DATA_DIR = Path(
    os.environ.get("SAFETY_MONITOR_DATA_DIR", Path.home() / ".safety-monitor")
)


class ConfigStore:
    """Loads and persists runtime settings as JSON in the data directory."""

    def __init__(self, data_dir: Path | None = None):
        self.data_dir = Path(data_dir or DEFAULT_DATA_DIR)
        self.snapshots_dir = self.data_dir / "snapshots"
        self.clips_dir = self.data_dir / "clips"
        self.settings_path = self.data_dir / "settings.json"
        self._lock = threading.Lock()
        self._ensure_dirs()
        self.settings = self._load()

    def _ensure_dirs(self) -> None:
        for d in (self.data_dir, self.snapshots_dir, self.clips_dir):
            d.mkdir(parents=True, exist_ok=True)

    def _load(self) -> Settings:
        if self.settings_path.exists():
            try:
                data = json.loads(self.settings_path.read_text())
                return Settings.model_validate(data)
            except Exception:
                # Corrupt settings should not brick the app; fall back to defaults.
                pass
        settings = Settings(cameras=[self._default_camera()])
        self._write(settings)
        return settings

    @staticmethod
    def _default_camera() -> CameraSettings:
        # Synthetic source by default so the app works out of the box even
        # without a physical camera or OpenCV; switch to "webcam" in settings.
        return CameraSettings(name="Demo camera", source_type="synthetic")

    def _write(self, settings: Settings) -> None:
        tmp = self.settings_path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(settings.model_dump(mode="json"), indent=2))
        tmp.replace(self.settings_path)

    def save(self) -> None:
        with self._lock:
            self._write(self.settings)

    def update(self, new_settings: Settings) -> Settings:
        with self._lock:
            self.settings = new_settings
            self._write(new_settings)
        return self.settings
