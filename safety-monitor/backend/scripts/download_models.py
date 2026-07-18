#!/usr/bin/env python3
"""Download the real vision models for ai_provider "local".

Both are official Google MediaPipe models (Apache-2.0), fetched over HTTPS
from Google's model host and verified against pinned SHA-256 checksums —
a checksum mismatch aborts the install rather than running an unexpected
model in a safety product. This is a one-time download; inference itself
is fully local and offline.

Usage:
    python scripts/download_models.py [--dest DIR]

Default destination: <data_dir>/models (data_dir honours
SAFETY_MONITOR_DATA_DIR, else ~/.safety-monitor).
"""

from __future__ import annotations

import argparse
import hashlib
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from safety_monitor.config import DEFAULT_DATA_DIR  # noqa: E402

BASE = "https://storage.googleapis.com/mediapipe-models"

MODELS = {
    "efficientdet_lite0.tflite": {
        "url": f"{BASE}/object_detector/efficientdet_lite0/float32/latest/efficientdet_lite0.tflite",
        "sha256": "40338edf5ec70d43e318b0a716a84d4564cd1802759a7a07170c7e43796dbf58",
        "purpose": "person detection (EfficientDet-Lite0)",
    },
    "pose_landmarker_lite.task": {
        "url": f"{BASE}/pose_landmarker/pose_landmarker_lite/float16/latest/pose_landmarker_lite.task",
        "sha256": "59929e1d1ee95287735ddd833b19cf4ac46d29bc7afddbbf6753c459690d574a",
        "purpose": "33-keypoint pose for posture/fall analysis",
    },
}


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dest",
        type=Path,
        default=DEFAULT_DATA_DIR / "models",
        help="directory to place the model files in",
    )
    args = parser.parse_args()
    args.dest.mkdir(parents=True, exist_ok=True)

    for name, spec in MODELS.items():
        target = args.dest / name
        if target.is_file() and sha256_of(target) == spec["sha256"]:
            print(f"ok       {name} — already present and verified")
            continue

        print(f"fetching {name} — {spec['purpose']}")
        tmp = target.with_suffix(target.suffix + ".part")
        urllib.request.urlretrieve(spec["url"], tmp)  # noqa: S310 - pinned https URL

        actual = sha256_of(tmp)
        if actual != spec["sha256"]:
            tmp.unlink(missing_ok=True)
            print(
                f"ERROR: checksum mismatch for {name}\n"
                f"  expected {spec['sha256']}\n"
                f"  got      {actual}\n"
                "Refusing to install an unverified model. If Google has "
                "published a newer 'latest', review it and update the pin.",
                file=sys.stderr,
            )
            return 1

        tmp.replace(target)
        print(f"verified {name} — sha256 ok -> {target}")

    print(f"\nModels ready in {args.dest}. Set ai_provider to \"local\" in the app.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
