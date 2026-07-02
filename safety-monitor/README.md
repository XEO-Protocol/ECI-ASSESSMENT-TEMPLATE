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
- **Modular AI provider interface** — the MVP ships with a mock provider;
  real local vision models plug into one small interface.
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
│   │   ├── vision.py         # VisionProvider interface + MockVisionProvider
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
