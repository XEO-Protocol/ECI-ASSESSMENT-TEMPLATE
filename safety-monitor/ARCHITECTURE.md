# Architecture

```
┌─────────────────────────────┐        ┌──────────────────────────────────────┐
│  Desktop app (Electron)     │        │  Backend (Python FastAPI, 127.0.0.1) │
│  React + TypeScript         │        │                                      │
│                             │  HTTP  │  CameraWorker (per camera)           │
│  Live view  ◄───────────────┼────────┼──  MJPEG stream                      │
│  Timeline   ◄───────────────┼──WS────┼──  event broadcast                   │
│  Zone editor ───────────────┼────────┼─►  settings / zones / privacy API    │
│  Notifications (Electron)   │        │                                      │
└─────────────────────────────┘        │  read frame                          │
                                       │    └─► apply privacy masks           │
┌─────────────────────────────┐        │          └─► motion (frame diff)     │
│  External agent (optional)  │        │                └─► VisionProvider    │
│                             │◄─POST──┼─ webhook (event + frame URLs)        │
│  inspect frames ────────────┼──GET──►│                      └─► RuleEngine  │
│  post assessment ───────────┼──POST─►│                            └─► SQLite│
└─────────────────────────────┘        │                              + JPEGs │
                                       └──────────────────────────────────────┘
```

## Pipeline (per camera, every `capture_interval_seconds`)

1. **Capture** — `CameraSource.read()` returns an RGB numpy frame.
   Sources: `WebcamSource` (OpenCV, optional) and `SyntheticSource`
   (built-in demo scene, no hardware needed).
2. **Privacy masking** — mask zones are blacked out immediately. Nothing
   downstream (motion, AI, storage, streaming, agents) ever sees masked
   pixels. Pausing stops frame reads entirely.
3. **Motion detection** — grayscale, downsample, absolute frame
   difference, threshold, coarse region localization (`motion.py`).
4. **Vision analysis** — the configured `VisionProvider` returns a
   `FrameAnalysis` (list of labeled detections with confidence, bbox and
   attributes such as `pose: lying`).
5. **Rule engine** — stateful per-camera rules turn motion + detections
   into `Event`s with severity, confidence, hedged message, and per-type
   cooldowns (`rules.py`).
6. **Storage** — events go to SQLite; a snapshot plus a small clip (the
   last N analysis frames) are saved as JPEGs — only if recording is
   enabled (`store.py`).
7. **Fan-out** — the event is pushed to the desktop app over WebSocket
   (notifications, timeline) and dispatched to agent hooks.

## Extension point 1: real vision models

`vision.py` defines the whole contract:

```python
class VisionProvider(ABC):
    async def analyze(self, frame: np.ndarray, context: AnalysisContext) -> FrameAnalysis: ...
```

To add a real model:

1. Implement `VisionProvider` (e.g. `YoloProvider`, ONNX pose estimator, or
   a local multimodal LLM that returns structured detections).
2. Register it in `create_provider()`.
3. Set `ai_provider` in settings.

The rule engine consumes detection labels, not providers, so no rule
changes are needed as long as your provider emits the conventional labels:
`person` (attributes `pose`: `standing|lying`, `transition`: `sudden`),
`stove_on`, `smoke`, `flame`, `door_open`. New labels + new rules are
added in `rules.py`.

The MVP's `MockVisionProvider` simulates detections (motion-correlated
person detection plus an optional scripted demo cycle) and labels its
output as mock in `FrameAnalysis.notes`.

## Extension point 2: external agent integration

Defined in `agent_hook.py`. Two transports, one contract:

**Push (webhook).** `POST /api/agent/webhooks {name, url}` — every event is
then POSTed to `url` as:

```json
{
  "event": { "id": "…", "type": "possible_fall", "message": "…", ... },
  "snapshot_url": "http://127.0.0.1:8765/api/events/<id>/snapshot.jpg",
  "frames_url": "http://127.0.0.1:8765/api/events/<id>/frames",
  "assessment_url": "http://127.0.0.1:8765/api/agent/assessments",
  "guidelines": "… use hedged language, never claim certainty …"
}
```

The webhook may return an assessment inline (HTTP 200 with an
`AgentAssessment` JSON body), or fetch the frame URLs and submit later.

**Pull (polling).** `GET /api/agent/pending` lists events with no
assessment yet; the agent inspects `snapshot_url`/`frames_url` and posts:

```json
POST /api/agent/assessments
{
  "event_id": "…",
  "agent_name": "claude-monitor",
  "summary": "The person appears to be moving again; risk may be low.",
  "risk_level": "low",
  "recommended_action": "No action appears necessary.",
  "requires_user_confirmation": true
}
```

Assessments are stored with the event and pushed live to the timeline.

**In-process hooks.** For a local agent living inside the backend process,
subclass `AgentHook` and call `gateway.register_hook(...)` — same payload,
no HTTP.

### Safety rules for agents

- Assessments are **advisory only**. The system never executes an agent's
  recommendation automatically.
- Emergency-style actions go through `POST /api/actions/emergency`, which
  returns **HTTP 428 unless `confirmed: true`** — and the UI only sets that
  after the user explicitly approves a confirmation dialog.
- The payload's `guidelines` field instructs agents to use hedged language
  ("possible", "appears", "may be") and never claim certainty.

## Local-first storage

```
~/.safety-monitor/            (override with SAFETY_MONITOR_DATA_DIR)
├── settings.json             runtime settings, cameras, zones
├── events.db                 SQLite event log
├── snapshots/<event>.jpg     one snapshot per event
└── clips/<event>/NNNN.jpg    short frame sequence around the event
```

`DELETE /api/history` (Settings → "Delete all history") wipes the database
rows and all media files.

## Known MVP simplifications

- "Clips" are short JPEG sequences at the analysis rate, not encoded video.
- The mock provider's detections are simulated; fall/stove/smoke logic is
  exercised end-to-end but not backed by a real model yet.
- The emergency action records/broadcasts the confirmed action; wiring it
  to a real contact channel (SMS/call/app) is a later phase.
- Single-process backend; multiple cameras run as async workers within it.
