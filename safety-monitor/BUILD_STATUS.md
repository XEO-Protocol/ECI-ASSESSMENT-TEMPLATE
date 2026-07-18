# Safety Monitor — Build Status & Continuation Guide

Companion to [MASTER_PLAN.md](./MASTER_PLAN.md). That document says *what*
to build and in what order; this one records *what exists, how it was
verified, and how to continue without losing quality*.

**Audience:** any successor builder — Opus 4.8, Codex 5.5, another Fable
session, or a human developer. Assume no memory of prior sessions; this
file plus the code is the whole handoff.

## 1. Snapshot

| | |
|---|---|
| Date | 2026-07 (Phase 0 complete) |
| Branch | `claude/desktop-safety-monitor-app-grhqsv` |
| PR | [#1](https://github.com/XEO-Protocol/ECI-ASSESSMENT-TEMPLATE/pull/1) (open, draft) |
| Phase 0 commit | `ee41237` "Add Safety Monitor: local-first desktop AI safety monitoring MVP" |
| Backend tests | **29 passed** (`python -m pytest tests -q` in `backend/`) |
| Desktop checks | strict `tsc --noEmit` (renderer + electron) and `vite build` pass |
| Not yet verified | Electron window launch (sandbox had no display), real webcam capture (no camera hardware), packaged builds |

## 2. Successor-model briefing — the quality bar

Phase 0 was built to a specific standard. Meet it or the handoff fails:

1. **Tests first-class.** Every rule, privacy behavior, and API contract
   change ships with a pytest (backend) or is covered by strict TS
   (desktop). The suite must stay green: run it before *and* after your
   change. Current count is 29 — it should only go up.
2. **Invariants are test-enforced, not aspirational.** If you add an event
   type, `test_all_safety_messages_use_hedged_language` must cover it. If
   you add an action endpoint with side effects beyond the hub, it needs a
   confirmation-gate test like `test_emergency_action_requires_confirmation`.
3. **Optional heavy deps.** `opencv-python` is optional (webcam only);
   numpy+Pillow are the only imaging deps in core. Anything heavy (ONNX,
   torch) goes in a separate requirements file with graceful fallback.
   The whole pipeline must keep running with zero hardware via
   `SyntheticSource`.
4. **Hedged copy everywhere.** Never write UI/event/agent text that claims
   certainty about a safety situation. Words to use: "possible", "appears",
   "may be". This is a product decision, not a style preference.
5. **One phase per PR**, titled `Phase N: <name>` (see MASTER_PLAN §4).
   Update this file's §8 status board and §9 decision log in the same PR.
6. **Match existing idiom.** Backend: dataclass/pydantic models, small
   modules, docstrings state privacy-relevant behavior. Frontend: function
   components, hooks, plain CSS in `styles.css`, no UI library.

## 3. What exists today (file map)

```
safety-monitor/
├── README.md                 quick start, feature list, privacy posture
├── ARCHITECTURE.md           pipeline diagram, extension points, agent contract
├── MASTER_PLAN.md            roadmap (Trinity: cameras/desktop/phone)
├── BUILD_STATUS.md           this file
├── backend/
│   ├── requirements.txt          fastapi, uvicorn, numpy, pillow, httpx, pydantic
│   ├── requirements-dev.txt      + pytest
│   ├── run.py                    entry point (--host/--port/--data-dir)
│   ├── examples/example_agent.py runnable polling agent (agent contract demo)
│   ├── safety_monitor/
│   │   ├── __init__.py       package marker; __version__ (imported by app.py)
│   │   ├── models.py         pydantic models: EventType(9), Severity, Zone,
│   │   │                     Detection, FrameAnalysis, MotionResult, Event,
│   │   │                     AgentAssessment, CameraSettings, Settings
│   │   ├── config.py         ConfigStore: data dir (~/.safety-monitor or
│   │   │                     $SAFETY_MONITOR_DATA_DIR), settings.json (atomic write)
│   │   ├── camera_sources.py CameraSource ABC; WebcamSource (cv2, optional);
│   │   │                     SyntheticSource (640x480 room scene; 26s cycle:
│   │   │                     ~20s movement + 6s freeze, lies down every 3rd freeze)
│   │   ├── motion.py         MotionDetector: gray→downsample→absdiff→threshold;
│   │   │                     sensitivity 0..1 maps to pixel+ratio thresholds; 8×8 regions
│   │   ├── vision.py         VisionProvider ABC; AnalysisContext; MockVisionProvider
│   │   │                     (demo script: person@10s, sudden-lying@35s, lying 41–211s,
│   │   │                     stove@215s, smoke@260s, door@275s, period 430s);
│   │   │                     create_provider() factory ← ADD REAL MODELS HERE
│   │   ├── rules.py          RuleEngine.evaluate(camera, motion, analysis, settings,
│   │   │                     now?, local_hour?) → [Event]; per-camera CameraRuleState;
│   │   │                     COOLDOWNS dict; MIN_CONFIDENCE=0.5; FALL_WINDOW=15s
│   │   ├── store.py          EventStore: sqlite (WAL) + snapshots/<id>.jpg +
│   │   │                     clips/<id>/NNNN.jpg; delete_all() wipes rows+media
│   │   ├── agent_hook.py     AgentHook ABC; LoggingAgentHook; WebhookAgentHook;
│   │   │                     AgentGateway (dispatch, pending-queue cap 200,
│   │   │                     payload_for() builds snapshot/frames/assessment URLs
│   │   │                     + hedging guidelines) ← AGENT EXTENSION POINT
│   │   ├── manager.py        CameraWorker (async loop @8fps preview, analysis every
│   │   │                     capture_interval_seconds; ring buffer 8 frames for clips;
│   │   │                     apply_masks() FIRST; paused → placeholder, no reads);
│   │   │                     CameraManager (start/stop/apply_settings restarts changed
│   │   │                     workers); mjpeg_stream() generator
│   │   └── app.py            create_app(data_dir) → FastAPI; WebSocketHub; CORS for
│   │                         localhost+file://; all routes (see §6); lifespan starts/stops manager
│   └── tests/
│       ├── test_motion.py    4 tests: first-frame, static, moving block, sensitivity
│       ├── test_rules.py     15 tests incl. cooldowns + hedged-language sweep
│       └── test_api.py       10 tests: health, settings roundtrip, snapshot JPEG,
│                             pause/recording, events+ack, delete history,
│                             428 emergency gate, agent assessment flow, webhooks, zones
└── desktop/
    ├── package.json          scripts: dev / build / typecheck / start (see §5)
    ├── package-lock.json     committed lockfile
    ├── index.html            Vite entry (loaded from dist/ by electron main in prod)
    ├── vite.config.ts        base './' so prod build works from file://
    ├── tsconfig.json (renderer, strict) + tsconfig.electron.json (CJS → dist-electron/)
    ├── electron/main.ts      window, backend autostart (spawns python3 run.py if
    │                         health check fails; SAFETY_MONITOR_NO_AUTOSTART=1 to skip),
    │                         IPC: notify, backend-url
    ├── electron/preload.ts   contextBridge → window.electronAPI {notify, backendUrl}
    └── src/
        ├── main.tsx          React entry; mounts <App/>, imports styles.css
        ├── styles.css        all styling (plain CSS, dark theme, no UI library)
        ├── types.ts          mirrors backend models  ← keep in sync with models.py
        ├── api.ts            REST client, BASE_URL http://127.0.0.1:8765, streamUrl/wsUrl
        ├── hooks/useEvents.ts WS subscribe + reconnect(2s) + keepalive(20s) + notifications
        ├── App.tsx           tabs (live/timeline/zones/settings), sidebar privacy controls,
        │                     backend-wait screen, unacked badge
        └── components/       LivePreview, EventTimeline, ZoneEditor, SettingsPanel, ConfirmDialog
```

## 4. Verification ledger (what was actually verified, and how)

| Claim | How verified | Reproduce |
|---|---|---|
| 29 backend tests pass | pytest run in CI-less sandbox | `cd backend && pip install -r requirements-dev.txt && python -m pytest tests -q` |
| Server boots, streams MJPEG | live run: `/api/health` ok; 3s of `/api/cameras/<id>/stream` yielded ~314 KB multipart JPEG | `python run.py` then `curl -m 3 http://127.0.0.1:8765/api/cameras/<id>/stream --output s.bin` |
| Pipeline produces events end-to-end | after ~16s runtime, `/api/events` contained `person_detected` + `motion` with snapshot+clip paths on disk | same run; `curl http://127.0.0.1:8765/api/events` |
| Hedged language enforced | `test_all_safety_messages_use_hedged_language` fails on any non-hedged rule message | included in pytest run |
| 428 without confirmation | `test_emergency_action_requires_confirmation` | included in pytest run |
| Renderer strict TS + prod build | `npm run build` (tsc --noEmit && vite build && tsc -p tsconfig.electron.json) | `cd desktop && npm install && npm run build` |
| Electron window opens | **NOT verified** (headless sandbox; binary skipped via `ELECTRON_SKIP_BINARY_DOWNLOAD=1`) | first `npm run dev` on a real machine |
| Real webcam capture | **NOT verified** (no camera; cv2 not installed) | `pip install opencv-python`, switch source to webcam in Settings |

## 5. Build & run

Prereqs: Python 3.11+, Node 20+ (22 used in development). No camera needed.

```bash
# Backend
cd safety-monitor/backend
pip install -r requirements-dev.txt      # dev; runtime-only: requirements.txt
python -m pytest tests -q               # expect: 29 passed
python run.py                            # http://127.0.0.1:8765  (data → ~/.safety-monitor)

# Desktop (second terminal)
cd safety-monitor/desktop
npm install
npm run dev                              # vite (5173) + electron; autostarts backend if down
# checks only (no display needed):
npm run typecheck && npm run build
```

Useful env vars: `SAFETY_MONITOR_DATA_DIR` (backend data dir),
`SAFETY_MONITOR_BACKEND_URL`, `SAFETY_MONITOR_PYTHON`,
`SAFETY_MONITOR_NO_AUTOSTART` (electron main), `VITE_DEV_SERVER_URL`
(set by the dev script). Sandbox/CI note: `ELECTRON_SKIP_BINARY_DOWNLOAD=1
npm install` if the Electron binary can't download; typecheck/build still work.

Demo behavior out of the box: default camera is `synthetic`; mock provider
has `mock_demo_cycle: true`, so within ~7 minutes you'll see person →
possible fall → lying still → smoke → door events flow through timeline +
notifications. Stove, restricted-zone and night-motion events do **not**
fire from the demo cycle (see §7 pitfall 11) — they're covered by unit
tests and fire in real configurations. Turn off in Settings → "Demo cycle".

## 6. API quick reference

Base `http://127.0.0.1:8765`. All JSON unless noted.

```
GET  /api/health                          status + per-camera {error}
GET/PUT /api/settings                     full Settings model (PUT restarts changed workers)
GET/POST /api/cameras · DELETE /api/cameras/{id}
GET  /api/cameras/{id}/stream             MJPEG (multipart/x-mixed-replace)
GET  /api/cameras/{id}/snapshot.jpg
PUT  /api/cameras/{id}/zones              {mask_zones?, restricted_zones?}
POST /api/privacy/pause                   {paused}
POST /api/privacy/recording               {enabled}
DELETE /api/history                       wipes events + media
GET  /api/events?camera_id&type&since&limit&offset
GET  /api/events/{id} · POST /api/events/{id}/ack
GET  /api/events/{id}/snapshot.jpg · /frames · /frames/{name}
POST/GET/DELETE /api/agent/webhooks[/name]
GET  /api/agent/pending                   events awaiting assessment (payload incl. guidelines)
POST /api/agent/assessments               AgentAssessment
POST /api/actions/emergency               428 unless confirmed:true
WS   /ws/events                           {kind: event|assessment|history_deleted|emergency_action}
```

## 7. Pitfalls & sharp edges (read before editing)

1. **Mask order is sacred.** `apply_masks()` runs before preview encoding,
   ring buffer, motion, vision, storage (`manager.py::CameraWorker._run`).
   Any new frame consumer must sit *after* masking. Same for pause.
2. **Worker restart semantics.** `CameraManager.apply_settings(previous)`
   diffs camera configs by value; a changed camera's worker is stopped and
   restarted, and its rule state reset. Pass a *deep copy* of previous
   cameras when mutating in place (see `put_zones` in `app.py`).
3. **Rule engine is time-injectable.** `evaluate(..., now=, local_hour=)`
   exists so tests never sleep. Keep new rules deterministic-testable the
   same way; never call `time.time()` inside a rule branch directly.
4. **Cooldowns can eat your test event.** `COOLDOWNS` in `rules.py` will
   suppress repeats; tests use fresh `RuleEngine()` instances or advance
   `now` beyond the cooldown.
5. **Failed camera open currently ends the worker loop** (no retry) — known
   gap, fixed by Phase 1's health/reconnect work. Don't build on the
   assumption that workers self-heal yet.
6. **`types.ts` mirrors `models.py` by hand.** Any model change must touch
   both (and `EVENT_TYPE_LABELS` for new event types).
7. **CORS**: `allow_origin_regex` admits localhost + file:// only. Remote
   access (Phase 5) must NOT widen this — it gets its own listener.
8. **Snapshot/frame routes guard path traversal** (`event_frame` resolves
   and checks parent). Keep that pattern for any new file-serving route.
9. **SQLite access is lock-guarded sync** (fine at MVP event rates).
   If event volume grows (Phase 3 real models), consider a write queue —
   don't quietly move to async sqlite without measuring.
10. **The mock's demo cycle is wall-clock based** (`DEMO_PERIOD=430s`);
    API tests that assert *no* events must use short runtimes or disable
    `mock_demo_cycle` via settings.
11. **Three event types never fire from the out-of-box demo**, by design
    of the rules rather than by bug: `stove_unattended` needs the stove
    detected continuously for `stove_unattended_seconds` (default 300s)
    with *nobody seen* — but the demo script's stove window is only 40s
    AND the synthetic figure's motion makes the mock emit a person almost
    continuously, so the no-person condition is never met;
    `restricted_zone_entry` needs user-drawn zones; `unusual_night_motion`
    needs the local clock inside night hours. All three are exercised by
    `test_rules.py` instead. Don't "fix" the demo by weakening the rules.

## 8. Task queue (status board)

Update this table in every PR. Full specs live in MASTER_PLAN.md.

| # | Task | Phase | Status |
|---|---|---|---|
| 1 | Desktop MVP (backend+UI+tests+docs) | 0 | ✅ done (PR #1) |
| 2 | MASTER_PLAN.md + BUILD_STATUS.md handoff docs | 0 | ✅ done |
| 3 | `MjpegSource` + `CameraSettings.url` + parser tests | 1 | ⬜ next |
| 4 | Source health (ok/stale/offline) + reconnect backoff + UI badge | 1 | ⬜ |
| 5 | PS Eye experimental preset + docs/SOURCES.md + docs/BOUNDARIES.md | 1 | ⬜ |
| 6 | Multi-camera grid UX + per-tile fps param | 2 | ⬜ |
| 7 | YOLO/pose local provider + provider settings UI | 3 | ⬜ |
| 8 | Managed agent runner + harness/model config UI + keychain storage | 4 | ⬜ |
| 9 | Watchdog digest reports | 4 | ⬜ |
| 10 | Remote listener + pairing (QR/token) + scope-limited remote API | 5 | ⬜ |
| 11 | Phone app 6a: pairing + camera grid | 6 | ⬜ |
| 12 | Phone app 6b: timeline + reports | 6 | ⬜ |
| 13 | Phone app 6c: alerts + privacy + emergency confirm | 6 | ⬜ |
| 14 | Packaging (electron-builder, signing; Expo builds) | 8 | ⬜ |
| 15 | Deferred: Sentinel memory/anomaly, phone-as-camera | 7 | ⬜ deferred |

**Definition of done for any task**: the MASTER_PLAN acceptance bullets
this task owns are met (Phase 1's bullets are tagged `[#3]`/`[#4]`/`[#5]`;
remaining phase bullets stay tracked here) · backend suite green (count
never decreases) · `npm run typecheck` + `npm run build` green · once
`mobile/` exists: mobile strict `tsc --noEmit` green and the E2E happy
path scripted (Maestro or a documented manual script recorded as a §4
ledger row) · invariants (MASTER_PLAN §2) intact with tests · every
affected section of this file updated (§3 file map, §5 commands, §6 API
reference, §7 pitfalls — remove/amend fixed ones — §8 board, §9 log) ·
one PR, titled `Phase N: <name>` or `Phase Na: <name>` for sub-phases.

**Acceptance items impossible in your build environment** (no display, no
camera, no OS keychain, missing OS): record them as NOT-verified rows in
§4 with exact reproduce steps and call them out in the PR description.
They don't block merge, but they must never be silently skipped.

## 9. Decision log

| Date | Decision | Why |
|---|---|---|
| 2026-06 | Synthetic camera as default source | Whole pipeline demo/test/CI without hardware; OpenCV optional |
| 2026-06 | Pure-numpy motion detection | Avoid hard OpenCV dependency in core |
| 2026-06 | Mock provider with scripted demo cycle | Exercises the person/fall/lying-still/smoke/door pipeline end-to-end before real models exist; every event type covered by unit tests in test_rules.py (see §7 pitfall 11) |
| 2026-06 | Hedged language enforced by test, not convention | Product-level safety requirement (never claim certainty) |
| 2026-06 | HTTP 428 for unconfirmed emergency actions | Machine-checkable "user confirmation required" gate |
| 2026-06 | Agent assessments advisory-only; gateway never acts | Safety boundary: humans confirm, agents advise |
| 2026-06 | Clips = JPEG sequences, not video encode | No ffmpeg dependency at MVP; revisit in Phase 3+ |
| 2026-07 | Legacy Sentinel work: INCORPORATE_SELECTIVELY (concepts, not code) | Stack mismatch (.mjs vs TS; different pipeline); re-validate everything; PS Eye stays external |
| 2026-07 | Trinity roadmap: desktop hub + RN/Expo phone app + tiered remote access (LAN/tailnet/minimal-relay) | Alfred-class UX without a mandatory vendor cloud |

*(Append here — never rewrite history in this table.)*

## 10. If you are picking this up cold

```bash
git clone https://github.com/XEO-Protocol/ECI-ASSESSMENT-TEMPLATE.git
cd ECI-ASSESSMENT-TEMPLATE
git checkout claude/desktop-safety-monitor-app-grhqsv   # or main once PR #1 merges
```

Branching rule while PR #1 is unmerged: branch your phase off
`claude/desktop-safety-monitor-app-grhqsv`, open the PR against that
branch, and retarget to `main` after PR #1 merges. Do **not** add phase
commits to PR #1 itself.

Then: run the backend tests (§5) to confirm a green baseline → read
`ARCHITECTURE.md` → skim the six backend modules in the §3 order (models →
config → sources → motion/vision → rules → manager/app) → take task #3
from §8. Keep PRs small, keep the language hedged, and keep everything
local-first.
