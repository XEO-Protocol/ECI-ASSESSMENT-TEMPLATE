# Safety Monitor

A **local-first, privacy-first desktop AI safety monitor**. It watches a room
through a local camera, detects possible safety events (a possible fall, a
person lying still, a stove that may have been left on, smoke/flame-like
anomalies, and more), keeps everything on your own computer, and exposes a
clean hook so an external AI agent can review events and give a second
opinion.

Built for scenarios like keeping an eye on an elderly parent while you're
away — the monitor flags things that *may* need your attention; it never
claims certainty and never acts without your confirmation.

## Highlights

- **Local-first.** Events, snapshots and clips live in `~/.safety-monitor`
  (SQLite + JPEG files). No cloud upload, no account, no telemetry.
- **Live preview** of each camera in the desktop app (MJPEG stream).
- **Motion detection** via frame differencing, with adjustable sensitivity.
- **Rule engine** for eight safety event types (see below), all rate-limited
  and phrased with hedged language ("possible", "appears", "may be").
- **Event timeline** with snapshots, day grouping, filters and review state.
- **Desktop notifications** for warnings and alerts.
- **Privacy controls:** pause camera, mask zones (blacked out *before*
  analysis or storage), recording on/off, delete all history.
- **Real on-device vision** — ships with two providers: `mock` (simulated
  detections for demos) and `local` (REAL person detection + 33-keypoint
  pose via MediaPipe, fully offline on CPU). If a real model fails to
  load, analysis turns visibly OFF — the app never substitutes simulated
  detections for a broken real provider.
- **Agent hook interface** — an external agent can receive events, inspect
  the frames around them, and return an assessment that shows up in the
  timeline. Emergency-style actions always require explicit user
  confirmation in the app.

## Safety event types

| Event | Trigger (simplified) |
| --- | --- |
| Person detected | A person appears after absence |
| Possible fall | Upright → lying transition, sudden |
| Person lying still | Lying with no motion beyond a configurable duration |
| Stove possibly unattended | Stove appears on with nobody around for a while |
| Smoke/flame-like anomaly | Smoke- or flame-like detection (immediate alert) |
| Door left open | Door appears open beyond a configurable duration |
| Restricted zone entry | Person appears inside a user-drawn zone |
| Unusual motion at night | Motion during configured night hours |

All event messages are deliberately non-certain — the system flags things
for a human (or an agent) to review; it does not diagnose.

## Quick start

Backend (Python 3.11+):

```bash
cd backend
pip install -r requirements.txt
python run.py            # serves http://127.0.0.1:8765
```

Desktop app (Node 20+):

```bash
cd desktop
npm install
npm run dev              # vite + electron; auto-starts the backend if it isn't running
```

Out of the box the app runs with a **synthetic demo camera** and the **mock
AI provider in demo-cycle mode**, so you'll see the full pipeline — live
preview, motion, person/fall/stove/smoke/door events, notifications,
timeline — without any camera hardware. To use a real webcam:

```bash
pip install opencv-python
```

then switch the camera's source to "Webcam" in Settings.

**Pair a phone or tablet by QR code (recommended, no app install):** in
the desktop app go to Settings → Cameras → **"Add phone or tablet…"**.
Scan the QR code with the device, accept the one-time certificate
warning (the link is your own hub; a locally generated self-signed cert
makes the camera page HTTPS, which phone browsers require for camera
access), name the camera, tap **Start camera**. The device streams JPEG
frames over an authenticated WebSocket to the hub — LAN only, no cloud,
no account. Pairing tokens are single-use and expire after 10 minutes;
each device gets its own 256-bit stream key, revoked by removing the
camera. The LAN-facing HTTPS listener exposes *only* the phone surface
(pairing page, claim endpoint, frame socket) — the full API stays
loopback-only. Keep the device plugged in with auto-lock off; if it
stops sending, the live view shows "no signal" rather than a stale
frame. Re-open `https://<hub-ip>:8766/phone-camera` on the device to
resume a previous pairing.

**Phone / tablet / IP camera (MJPEG over the LAN):** any device that can
serve its camera as an MJPEG HTTP stream works as a camera source — an
iPad or phone running an "IP camera" app, an ESP32-cam, or a Linux box
sharing a USB camera. In Settings set the camera source to "Network
camera (MJPEG)" and paste the stream URL (credentials in the URL are
honoured: `http://user:pass@192.168.x.x:port/video`). The source is
bounded by design: http/https only, connect/read timeouts, capped
buffers, oversized/corrupt frames dropped, and a stalled stream shows
"no signal" rather than a stale frame. Example one-liner to serve a USB
camera from a Linux box (PS3 Eye included — the kernel supports it):

```bash
# on the Linux box with the camera plugged in
sudo apt install ustreamer && ustreamer --host 0.0.0.0 --port 8080
# then use http://<that-box>:8080/stream as the camera URL
```

To use **real vision detection** instead of the mock (person presence,
posture and fall analysis from actual models, all on-device):

```bash
cd backend
pip install -r requirements-vision.txt   # MediaPipe runtime
python scripts/download_models.py        # one-time, checksum-verified
```

then set the vision provider to "Real" in Settings → AI analysis.
(Linux servers also need GL libs: `apt install libgles2 libegl1`.
Posture is classified from torso keypoint geometry — upright vs lying —
and a sudden upright→lying transition drives the possible-fall rule.)

Run the backend tests:

```bash
cd backend
pip install -r requirements-dev.txt
python -m pytest tests
```

## Repository layout

```
safety-monitor/
├── backend/                  # Python FastAPI: capture, analysis, rules, storage, agent API
│   ├── safety_monitor/
│   │   ├── camera_sources.py # webcam (OpenCV, optional) + synthetic demo source
│   │   ├── motion.py         # frame-differencing motion detection (numpy)
│   │   ├── vision.py         # VisionProvider interface + mock/unavailable
│   │   ├── vision_local.py   # REAL MediaPipe person+pose provider
│   │   ├── rules.py          # rule engine → hedged safety events
│   │   ├── store.py          # SQLite events + local snapshots/clips
│   │   ├── agent_hook.py     # agent hook interface (webhook push + polling pull)
│   │   ├── manager.py        # per-camera pipeline loop, privacy masking, MJPEG
│   │   └── app.py            # FastAPI routes + WebSocket
│   └── tests/
└── desktop/                  # Electron + React + TypeScript UI
    ├── electron/             # main process + preload (notifications, backend autostart)
    └── src/                  # renderer: live view, timeline, zone editor, settings
```

See [ARCHITECTURE.md](./ARCHITECTURE.md) for the pipeline, the extension
points for real vision models, and the agent integration contract.

Project direction and handoff docs:

- [MASTER_PLAN.md](./MASTER_PLAN.md) — everything done and everything
  planned, through the full Trinity system (cameras · desktop · phone app
  with agent reports).
- [BUILD_STATUS.md](./BUILD_STATUS.md) — verified build state, exact
  build/run/test commands, code tour, pitfalls, and the task queue for any
  successor builder.

## Privacy & safety posture

- **No cloud by default.** The backend binds to `127.0.0.1`. The only way
  data leaves the machine is if *you* register an agent webhook.
- **Mask zones are enforced at the source.** Masked pixels are blacked out
  before motion detection, AI analysis, storage or streaming.
- **Pause is real.** While paused, frames are not read from the camera at
  all.
- **Nothing is certain.** Every safety event and agent guideline uses
  hedged language; the UI shows confidence as approximate.
- **You stay in charge.** Emergency-style actions require an explicit
  confirmation dialog; the backend rejects unconfirmed requests
  (HTTP 428).
