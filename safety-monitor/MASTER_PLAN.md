# Safety Monitor — Master Plan

**The Trinity system: Cameras · Desktop · Phone.**
A privacy-first, local-first home safety monitor: cameras feed a desktop hub
where an AI agent watches for possible safety events (falls, stove left on,
smoke, night wandering); the owner views cameras and receives the agent's
reports on their phone. An original, privacy-respecting alternative to
Alfred Camera-style cloud products.

| | |
|---|---|
| Repository | `XEO-Protocol/ECI-ASSESSMENT-TEMPLATE` |
| App root | `safety-monitor/` |
| Working branch | `claude/desktop-safety-monitor-app-grhqsv` |
| PR | [#1 — Add Safety Monitor: local-first desktop AI safety monitoring MVP](https://github.com/XEO-Protocol/ECI-ASSESSMENT-TEMPLATE/pull/1) |
| Plan author | Fable 5 (Claude), 2026-07 |
| Companion doc | [BUILD_STATUS.md](./BUILD_STATUS.md) — verified state + how to build/continue |

---

## 0. How to use this document

This plan is written to survive a change of builder. If a different model or
developer (Opus 4.8, Codex 5.5, a human) picks the project up:

1. Read **§2 Invariants** first — they are non-negotiable and test-enforced.
2. Read [BUILD_STATUS.md](./BUILD_STATUS.md) to learn what already exists,
   how it was verified, and the sharp edges.
3. Work phases respecting the **dependency column in §4** (it is the single
   source of truth for ordering; where dependencies allow a choice, prefer
   the lower-numbered phase). Each phase (§5→§13) lists scope, file-level
   plan, and acceptance criteria. A phase is done only when its acceptance
   criteria pass and the quality bar in BUILD_STATUS.md §2 is met.
4. One phase ≈ one PR, titled `Phase N: <name>`. Large phases may split
   into sub-phase PRs titled `Phase Na/Nb/Nc: <name>` (the §8 task board in
   BUILD_STATUS maps tasks to sub-phases); each sub-phase PR must satisfy
   the acceptance bullets it owns, with the remainder tracked on the board.
   Never fold multiple phases into one PR.
5. When a decision here conflicts with something you'd prefer: if it's an
   invariant, follow the plan; otherwise record the deviation and reason in
   BUILD_STATUS.md's decision log and proceed.

## 1. Vision

A user sets up one or more cameras in a relative's home (e.g. an elderly
parent living alone). A desktop app on a machine in that home runs the
monitoring pipeline locally: motion detection, vision analysis, and a rule
engine that flags *possible* safety events. An AI agent — configured on the
desktop (model + harness) — reviews events, inspects frames, and writes
short hedged assessments. The user, anywhere, opens the phone app to:

- see live views of all cameras,
- read the event timeline and the agent's reports,
- receive push alerts for warnings/alerts,
- confirm or dismiss any emergency-style escalation.

**Trinity roles**

| Node | Role |
|---|---|
| Cameras | Frame sources: webcams, network MJPEG cameras (IP cams, phone-as-camera, PS Eye bridge), synthetic demo |
| Desktop | The hub. Runs the full pipeline + storage + agent harness. The only component that sees raw frames by default. Owner configures cameras, zones, rules, privacy, and the agent (model + harness) here |
| Phone | Remote eyes. Views cameras, timeline, agent reports; receives notifications; confirms emergency actions. Never required for the system to function |

The system **assists** a human carer. It never diagnoses, never acts
autonomously on emergencies, and never claims certainty.

## 2. Non-negotiable invariants

These hold in every phase. Several are enforced by tests today; keep those
tests passing and extend them to new surfaces.

1. **Local-first.** Full functionality without any cloud service or account.
   Data (events, snapshots, clips, settings) lives on the owner's hardware.
2. **No cloud upload by default.** Remote access is opt-in, owner-configured,
   and end-to-end within the owner's own network/tunnel wherever possible.
3. **No telemetry.**
4. **Hedged language only** for safety events and agent output: "possible",
   "appears", "may be". Enforced by `tests/test_rules.py::test_all_safety_messages_use_hedged_language`.
5. **Explicit user confirmation before emergency-style actions.** The API
   returns HTTP 428 without `confirmed: true`; only a UI confirmation dialog
   sets it. Agents are advisory only.
6. **Privacy controls are real controls.** Pause stops frame reads; mask
   zones are blacked out *before* analysis/storage/streaming; recording
   off means no media written; delete history wipes DB + media.
7. **No face recognition, identity recognition, biometric tracking.**
8. **No production safety claims.** This is an assistive monitor, not a
   medical/alarm system; docs and UI copy must say so.
9. **Generic abstractions over device coupling.** New camera types enter
   via `CameraSource`; new models via `VisionProvider`; new agents via the
   agent gateway. No device-specific code in the core pipeline.

## 3. Target architecture (end state)

```
   CAMERAS                         DESKTOP (hub)                          PHONE
┌────────────┐      ┌────────────────────────────────────────┐    ┌──────────────────┐
│ Webcam     │──────►  FastAPI backend (127.0.0.1)           │    │ React Native app │
│ IP cam /   │ MJPEG│   capture → mask → motion → vision     │    │  camera grid     │
│ phone cam  │──────►   → rules → SQLite+JPEG → WS fan-out   │◄───┤  timeline        │
│ PS Eye     │      │        │            ▲                  │ LAN│  agent reports   │
│ bridge*    │      │        ▼            │                  │ or │  push alerts     │
│ Synthetic  │      │   Agent harness (owner-configured      │VPN │  confirm dialogs │
└────────────┘      │   model+harness) — watchdog reports    │    └──────────────────┘
                    │        ▲                               │
                    │  Electron+React UI: live, timeline,    │
                    │  zones, settings, AGENT SETUP,         │
                    │  PAIRING (QR)                          │
                    └────────────────────────────────────────┘
* external experimental tool, never in-process
```

Remote access tiers (phone→desktop), strongest-privacy first:
- **Tier 0 — same LAN**: direct HTTPS/WSS to the hub with a pairing token.
- **Tier 1 — owner-run tunnel** (recommended remote path): Tailscale/WireGuard
  mesh; the hub is reachable at a private address only the owner's devices hold.
- **Tier 2 — notification relay (opt-in, off by default)**: mobile push (APNs/FCM)
  requires *some* relay; ship minimal-content encrypted notifications ("possible
  fall on Kitchen — open app") with media fetched over Tier 0/1 only. A
  self-hosted relay (e.g. ntfy) must be offered as the no-third-party option.

## 4. Phase map

| Phase | Name | Status | Depends on |
|---|---|---|---|
| 0 | Desktop MVP (this PR) | ✅ **DONE** — PR #1 | — |
| 1 | Camera sources & health (legacy Package A) | Planned | 0 |
| 2 | Multi-camera dashboard UX | Planned | 1 |
| 3 | Real local vision models | Planned | 0 |
| 4 | Agent harness & watchdog configuration | Planned | 0 (3 improves it) |
| 5 | Remote access & pairing | Planned | 1 |
| 6 | Phone app (Trinity complete) | Planned | 4, 5 |
| 7 | Advanced/deferred (Sentinel memory, phone-as-camera, remote lab) | Deferred | 6 |
| 8 | Packaging & distribution | Planned | any |

Phases 1–4 are desktop-only and independently shippable. 5–6 deliver the
phone leg. Detailed phase specs follow.

---

## 5. Phase 0 — Desktop MVP ✅ DONE (PR #1)

Everything below is implemented and pushed; per-item verification status
(including the three items that could *not* be verified in the build
sandbox: Electron window launch, real webcam capture, packaged builds) is
recorded honestly in BUILD_STATUS.md §4. Inventory only; see BUILD_STATUS.md
for the verification ledger and code tour.

**Backend** (`safety-monitor/backend/`, Python 3.11+, FastAPI):
- `camera_sources.py` — `CameraSource` ABC; `WebcamSource` (OpenCV, optional
  dependency); `SyntheticSource` (generated room scene with wandering /
  lying-down figure — zero-hardware demo).
- `motion.py` — frame-differencing motion detection, pure numpy; sensitivity
  0..1; coarse region localization.
- `vision.py` — `VisionProvider` interface + `MockVisionProvider` (motion-
  correlated person detection; scripted demo cycle firing person / possible-
  fall / lying-still / smoke / door events every ~7 minutes — stove,
  restricted-zone and night-motion need real config or longer windows and
  are covered by unit tests instead, see BUILD_STATUS §7 pitfall 11);
  `create_provider()` factory = model extension point.
- `rules.py` — stateful per-camera `RuleEngine`; 8 event types (person
  detected, possible fall, person lying still, stove unattended, smoke/flame
  anomaly, door left open, restricted zone entry, unusual night motion) +
  generic motion; per-type cooldowns; hedged messages.
- `store.py` — SQLite event log + JPEG snapshots and mini-clips under the
  data dir; `delete_all()` privacy wipe.
- `agent_hook.py` — `AgentHook` ABC, `WebhookAgentHook` (push),
  `AgentGateway` with pending-events pull API; hedging guidelines delivered
  in every payload; assessments advisory-only.
- `manager.py` — `CameraWorker` loop per camera (capture → mask → motion →
  vision → rules → store → WS → agents); privacy masking before anything
  else; MJPEG preview streaming; pause = no frame reads.
- `app.py` — REST API (settings, cameras, zones, events, privacy, agent,
  emergency w/ HTTP 428 confirmation gate) + `/ws/events` WebSocket.
- `config.py` — settings JSON + data dir (`~/.safety-monitor`, env-overridable).
- `tests/` — 29 tests: motion, every rule + cooldown + hedged-language
  enforcement, API incl. pause and the 428 gate.
- `examples/example_agent.py` — runnable polling agent demonstrating the
  agent contract.

**Desktop** (`safety-monitor/desktop/`, Electron + React + TS, Vite):
- Live MJPEG preview; event timeline (day grouping, filters, snapshots,
  acknowledge, agent assessments inline, emergency button behind
  `ConfirmDialog`); drag-to-draw zone editor (privacy masks + restricted
  zones); settings panel (interval, sensitivity, night hours, cameras,
  demo cycle, delete-history behind confirm); sidebar privacy controls
  (pause / recording toggle); desktop notifications via Electron; WS
  auto-reconnect; backend autostart from Electron main.

**Docs**: `README.md`, `ARCHITECTURE.md` (pipeline + both extension points).

## 6. Phase 1 — Camera sources & health

*Goal: from "one webcam" to "any local camera", with visible health.*
Incorporates the valuable parts of the legacy Sentinel / ai-safety-camera
work (see §14) as re-implementations, not code copies.

Scope:
1. **`MjpegSource`** in `camera_sources.py`: consumes MJPEG-over-HTTP
   streams (IP cameras, phone camera apps, the PS Eye bridge). httpx
   streaming + multipart boundary parsing + PIL decode. Settings changes
   (extend the existing fields in `models.py`, mirror in `types.ts`):
   `CameraSettings.url: Optional[str] = None`,
   `CameraSettings.allow_non_local: bool = False`, and `source_type`
   widened to `"webcam" | "synthetic" | "mjpeg"`. Validation: a `mjpeg`
   camera with a missing/malformed URL is **accepted at settings time but
   runs as `offline`** with the reason in its health status (settings
   writes stay non-blocking; the UI surfaces the health error). Allowed
   without `allow_non_local`: loopback (127/8, ::1), RFC1918 (10/8,
   172.16/12, 192.168/16), link-local (169.254/16, fe80::/10), IPv6 ULA
   (fc00::/7), and `.local` mDNS names; other hostnames are resolved at
   connect time and re-checked on every reconnect (mitigates DNS
   rebinding). The Settings-UI URL input ships with this task, not with
   the PS Eye preset. The stream parser is a pure incremental function so
   it can be tested on byte fixtures without a network.
2. **Source health**: `CameraWorker` tracks `last_frame_at`; derives
   `ok | stale | offline`; reconnects with capped exponential backoff
   (this also fixes the current behavior where a failed open ends the
   worker permanently). `/api/health` returns per-camera status; UI shows
   a status badge (sidebar + live view). A camera going offline emits an
   `info`-severity system event so it appears in the timeline.
3. **PS Eye preset**: in Settings, an "experimental" preset that fills
   `http://127.0.0.1:8791/pseye.mjpeg`. Docs explain the external bridge
   (owner-run, local-only). **No libusb/PS Eye capture code in this repo.**
4. **Docs**: `docs/SOURCES.md` (source abstraction, MJPEG how-to for IP
   cams/phones, PS Eye), `docs/BOUNDARIES.md` (adapted from legacy
   ARCHITECTURE_BOUNDARIES: what may never enter the core).

Acceptance criteria (owner task in brackets, per BUILD_STATUS §8):
- [#3] Fixture-driven parser tests in `tests/test_camera_sources.py`
  against byte fixtures in `tests/fixtures/` (well-formed, truncated,
  missing-boundary), plus one integration test against a tiny in-process
  HTTP server; non-local URL refused at connect time unless
  `allow_non_local`.
- [#3] Masks/pause/recording apply to MJPEG sources identically — three
  explicit assertions.
- [#4] Health-transition tests (ok→stale→offline→recovered); a
  misconfigured MJPEG camera degrades to `offline` without affecting other
  cameras.
- [all] Existing suite stays green (29+ tests).

Est. size: ~600 LOC + tests. | PRs: `Phase 1a/1b/1c: <name>` mapping to
tasks #3/#4/#5 on the BUILD_STATUS board (or one `Phase 1:` PR if small
enough to review).

## 7. Phase 2 — Multi-camera dashboard UX

*Goal: watch a whole home at a glance.*

Scope:
- `LivePreview` grid mode (1/2×2/3×3 auto-layout) with per-tile name,
  health badge, last-event chip; click-to-focus single view.
- Add/remove/rename cameras fully from Settings. Backend routes exist
  (`POST`/`DELETE /api/cameras`) but the Settings UI currently only edits
  existing cameras — build the add/remove UI on top of those routes, with
  per-camera enable and zone shortcuts.
- Timeline filter by camera.
- Keep MJPEG preview per tile but drop tile FPS when unfocused (backend
  already paces streaming; add `?fps=` query param to the stream route).

Acceptance: grid renders N synthetic cameras (manual check ok), stream
route honors fps param (test), strict TS passes. Est: ~400 LOC.

## 8. Phase 3 — Real local vision models

*Goal: replace mock detections with real ones, still fully local.*

Scope:
1. `YoloPersonProvider` (ONNX Runtime, e.g. yolov8n): `person` label +
   bbox. Optional extra: pose model (e.g. movenet / yolo-pose) → `pose:
   standing|lying` from keypoint geometry + `transition: sudden` from bbox
   aspect-ratio velocity. New optional dependency group
   `requirements-vision.txt`; provider registered in `create_provider()`.
2. Heuristic providers where models are weak, clearly separated:
   `stove_on`/`smoke`/`flame`/`door_open` stay **out of scope** for model
   claims in this phase — keep mock/off unless a credible local detector is
   wired; never fake confidence.
3. Provider selection + model file path in Settings UI; provider hot-swap
   on settings change (manager already restarts workers on settings change).
4. Graceful degradation: missing model file → provider falls back to mock
   with a visible warning in UI + `/api/health`.

Acceptance: pipeline runs at ≥1 analysis/2s on CPU for one camera; unit
tests with canned frames verify provider output mapping (person + pose);
fall rule fires end-to-end from a scripted lying-down frame sequence.
Est: ~700 LOC + model download instructions (no weights in repo).

## 9. Phase 4 — Agent harness & watchdog configuration

*Goal: the owner picks which AI agent watches, and how — on the desktop.*

This is the "desktop sets up the agent (model and agent harness)" leg of
the Trinity. Today the gateway supports in-process hooks, webhooks, and
polling. This phase adds owner-configurable managed harnesses.

Scope:
1. **`Settings.agent_harness: AgentHarnessConfig`** — governs only the new
   managed runner; the existing webhook registry
   (`/api/agent/webhooks`) and polling API stay exactly as they are and
   keep working alongside it. Fields: `mode: "none" | "managed"`
   (**default `"none"`** — no agent runs until the owner turns one on);
   for `managed`: `provider: "local-ollama" | "anthropic-api" |
   "custom-command"`, `model` (e.g. a local Ollama tag, or
   `claude-fable-5` / `claude-opus-4-8` / `claude-haiku-4-5`),
   `base_url: Optional[str]` (Ollama host / API override — also how tests
   point the runner at a stub), `max_frames_per_event` (default 4, ceiling
   8 = the clip ring-buffer size), `min_seconds_between_calls` (default 30,
   per camera), `monthly_token_budget: Optional[int]`. The API key is
   stored in the OS keychain via Electron `safeStorage`, **never** in
   settings.json, and is not readable via any API route.
2. **`ManagedAgentRunner`** (new module `safety_monitor/agent_runner.py`):
   consumes the gateway's pending queue; for each warning/alert event,
   sends event context + hedging guidelines (+ up to `max_frames_per_event`
   frames — see privacy rules below) to the configured provider; parses a
   structured `AgentAssessment`; enforces hedged output via a **shared
   `safety_monitor/hedging.py`** module exposing `is_hedged(text)` — the
   existing hedged-language test must be refactored to use the same module
   so the two can never drift. Non-hedged output: retry once, then drop
   (event stays assessment-less) with a logged warning. Token usage is
   read from provider responses and persisted in an `agent_usage` table
   keyed by `YYYY-MM` (local time); at budget cap the runner skips calls,
   emits one info-severity system event, and the UI shows used/cap.
3. **Privacy rules for the runner** (these extend invariant 2 and get
   tests): frames leave the hub **only** when a non-local provider is
   explicitly configured; when `recording_enabled` is off, events carry no
   media and the runner sends **text-only** context (no frames, even from
   memory); selecting `anthropic-api` (the only cloud egress in the whole
   system) requires an explicit acknowledgement in the UI under
   non-removable copy: *"Snapshots and clip frames for flagged events will
   be sent to <provider> for analysis."* `local-ollama` is the fully
   offline path and is listed first in the UI.
4. **`custom-command` contract**: event payload JSON on stdin →
   `AgentAssessment` JSON on stdout; N-second timeout (default 60);
   non-zero exit or invalid JSON = failed assessment; one concurrent
   invocation. Configurable **only** from the local desktop UI — never via
   any remote surface (Phase 5 already excludes settings remotely; keep it
   that way).
5. **Watchdog reports**: scheduled digests. New `Report` model
   (`id, period_start, period_end, generated_at, generator` (agent name or
   `"template"`), `body`, `event_counts`), stored in SQLite; routes
   `GET /api/reports`, `GET /api/reports/{id}`; WS kind `"report"`;
   settings `digest_schedule: "none" | "daily" | "weekly"` +
   `digest_hour` (local). Missed runs (hub off at the scheduled time)
   catch up on next boot. Surfaced in a new desktop "Reports" view (and
   pushed to phone in Phase 6). Digest generation must also work
   agent-less via a plain template so the feature degrades gracefully.
6. **Agent setup UI** (desktop Settings → "Agent"): provider/model pickers,
   key entry, "send test event" button, live status (last run, tokens
   used/cap), and the guidelines text — editable portion below the
   non-removable boilerplate, which lives as a named constant in the
   backend (single source of truth, currently `AGENT_GUIDELINES` in
   `agent_hook.py`) and is displayed read-only.
7. Extend `examples/` with a managed-harness config walkthrough.

Hard rules: assessments remain advisory; the runner never calls the
emergency endpoint; a dead/misconfigured agent never blocks the pipeline
(fan-out already async — keep it that way); API keys never leave the hub
except to the chosen model provider.

Acceptance: with a local HTTP LLM stub (`base_url` pointed at it) — event
→ runner → assessment stored + broadcast; certainty-language output gets
rejected, retried once, then dropped with a logged warning; budget cap
halts calls and emits the info event; no-frames-when-recording-off and
no-frames-for-local-provider verified by tests; keychain storage verified
manually per OS (record as NOT-verified ledger rows where the build
environment can't do it — see BUILD_STATUS §8).
Est: ~900 LOC. Split into `Phase 4a` (runner+config+privacy rules) /
`Phase 4b` (digests+UI) if needed.

## 10. Phase 5 — Remote access & pairing

*Goal: the hub becomes securely reachable by the owner's phone. No cloud.*

Scope:
1. **Remote listener**: optional second bind (default off) on
   `0.0.0.0:8766` with TLS (self-signed cert generated at first enable)
   and **mandatory bearer-token auth on every route** (the local 8765
   listener stays localhost-only for the desktop UI). Scope-limited API
   surface for remote: read events/streams/reports, privacy toggles,
   acknowledge, emergency-confirm — **not** settings/agent/keys.
2. **Pairing**: desktop shows a QR code (JSON payload: `{v, hosts[],
   port, cert_fp, code}`); phone exchanges the one-time code at
   `POST /api/pair` for a long-lived device token (revocable per device in
   the desktop UI). Deliverable: `docs/PAIRING.md` specifying the QR
   schema, the `/api/pair` request/response contract, WebSocket auth (token
   as query param over TLS — React Native WS header support is limited;
   document the tradeoff), and token format/lifetime/rotation.
3. **Tier 1 guidance**: first-class docs for Tailscale/WireGuard so the
   same pairing works away from home; hub advertises its tailnet address
   as a host candidate when detected.
4. **Rate limiting + audit log** for remote-auth failures (local log only).

Acceptance: token-less remote requests → 401 (test); pairing flow issues
and revokes tokens (test); cert pinning verified in integration test;
remote surface cannot modify agent config or read API keys (test).
Est: ~800 LOC. Security review checklist in PR description required.
Note for Phase 6: certificate pinning is not possible in Expo Go — plan on
an EAS/dev-client build from the start.

## 11. Phase 6 — Phone app (Trinity complete)

*Goal: an Alfred-class viewer, minus the cloud: all cameras on the phone,
agent reports and alerts pushed, emergency confirmation in your pocket.*

Stack: **React Native + Expo (TypeScript)** in `safety-monitor/mobile/`,
sharing types with the desktop via a new `safety-monitor/shared/` package
(move `desktop/src/types.ts` there; both apps import it). Wiring: npm
workspaces at `safety-monitor/` + `metro.config.js` `watchFolders` so Expo
can import outside its app root. Type-sync upgrade: the backend already
serves `/openapi.json`; generate the shared types from it with
`openapi-typescript` in a script both apps run in CI, replacing the
hand-mirroring convention (and rewrite BUILD_STATUS §7 pitfall 6 + the §3
file map in the same PR). Use an Expo **dev-client/EAS build**, not Expo
Go (cert pinning — see Phase 5); if EAS cloud builds conflict with the
owner's no-cloud stance, document the local `expo run:ios/android`
alternative.

Screens:
1. **Pairing** — QR scan → token exchange → stored in secure enclave/keystore.
2. **Camera grid** — all cameras, live MJPEG tiles (RN `Image` streaming or
   WebView fallback), health badges. Tap → full-screen live view.
3. **Timeline** — same event feed as desktop (REST + WS), snapshots, agent
   assessments, acknowledge.
4. **Reports** — the Phase 4 digests; pull-to-refresh + notification deep-link.
5. **Alerts** — push notifications for warning/alert events and digests:
   Tier 0/1 = WS while app alive + local notifications; Tier 2 (opt-in) =
   APNs/FCM or self-hosted ntfy relay carrying minimal ciphertext (event
   type + camera name only; media always fetched from the hub).
6. **Privacy remote control** — pause cameras, recording toggle (same
   confirmations as desktop).
7. **Emergency confirmation** — an alert's "Emergency action…" flows the
   same 428-gated confirm; phone confirmation is equivalent to desktop's.

Explicitly out of scope for 6: phone-as-camera (that's Phase 7), account
systems, any vendor cloud.

Acceptance: E2E happy path against a hub on LAN (scripted: pair → view →
receive WS alert → acknowledge → confirm emergency); token revocation cuts
access; app store packaging deferred to Phase 8. Est: the largest phase —
plan 3 PRs (6a pairing+grid, 6b timeline+reports, 6c alerts+privacy+emergency).

## 12. Phase 7 — Advanced / deferred

Only after the Trinity is stable, and each behind its own consent design:
- **Sentinel local memory + pattern anomaly detection** (legacy PK-34/35):
  daily-rhythm baselining ("kitchen usually active by 09:00") → "quiet
  morning" advisories. Behavioral profiling of a vulnerable person — needs
  explicit consent UX, on-device only, easy off-switch + wipe.
- **Smart watcher assessment** (PK-36): richer agent reasoning over event
  sequences; slots into the Phase 4 runner.
- **Phone/tablet-as-camera node** (PK-22): browser/RN page that pushes
  camera frames to the hub as an ingest source (becomes just another
  `CameraSource`).
- **Remote lab / Alfred comparison** (PK-37) as evaluation docs.

## 13. Phase 8 — Packaging & distribution

*Goal: installable artifacts a non-developer can run.*

Scope:
1. **Desktop**: `electron-builder` targets for macOS (dmg), Windows
   (nsis), Linux (AppImage/deb); code signing + notarization strategy
   documented per OS (owner supplies certificates; unsigned builds remain
   possible for personal use).
2. **Backend bundling**: decide venv-bootstrap (installer creates a venv
   and pip-installs pinned requirements) vs PyInstaller one-file. Start
   with venv-bootstrap — simpler to debug, keeps OpenCV optional; record
   the decision in BUILD_STATUS §9.
3. **Mobile**: EAS build profiles (or documented local
   `expo run:ios/android` for the no-cloud path); store submission is
   optional and out of scope until the owner asks.
4. **Versioning**: single version source (root `VERSION` file) stamped
   into backend `__version__`, desktop `package.json`, mobile
   `app.json`.

Acceptance: a fresh machine per OS can install and launch the desktop app
+ backend from artifacts alone (record as NOT-verified ledger rows where
the build environment can't test an OS); mobile produces an installable
build; version stamps agree. Est: ~300 LOC + CI config.

## 14. Legacy incorporation map (Sentinel / ai-safety-camera archive)

Archive: `/Volumes/maxone/LOCAL_PROJECT_ARCHIVE_2026-06-22_LATEST/…/SYSTEM_WORKSPACE/apps/ai-safety-camera/`
(owner's Mac; not accessible from CI/cloud sessions — copy files into the
repo under `legacy-reference/` if line-level reuse is ever needed).
Verdict from the incorporation assessment: **INCORPORATE_SELECTIVELY**.

| Legacy asset | Disposition | Lands in |
|---|---|---|
| Camera source abstraction (PK-18) | Already exists as `CameraSource` — extend only | Phase 1 |
| Local MJPEG source (PK-19, `mjpegSources.mjs`, `pipeline/sources.py`) | Re-implement in Python | Phase 1 |
| Source health (`sourceHealth.mjs` + tests) | Re-implement; port test intent | Phase 1 |
| PS Eye preset/readiness (PK-38) | Preset URL + docs only; bridge stays external | Phase 1 |
| PS Eye raw capture (`tools/pseye/*.cpp`, libusb) | **Do not port** into main runtime | — |
| Multi-camera dashboard (PK-20/28) | Adapt concepts to React UI | Phase 2 |
| Browser phone/tablet node (PK-22) | Defer; becomes ingest `CameraSource` | Phase 7 |
| Sentinel memory / anomaly / smart watcher (PK-34/35/36) | Defer behind consent design | Phase 7 |
| Tailscale-gated remote viewer (PK-39) | Concept adopted as Tier 1 remote access | Phase 5 |
| ARCHITECTURE_BOUNDARIES / OPERATOR_HANDOFF docs | Adapt | Phase 1 docs |
| Legacy `.mjs` desktop modules verbatim | Do not port (stack mismatch — concepts only) | — |

## 15. Risk register

| Risk | Impact | Mitigation |
|---|---|---|
| Real fall detection is hard; false negatives dangerous, false positives erode trust | High | Hedged language everywhere; "assistive, not alarm system" copy; tune on synthetic + staged clips; lying-still rule as belt-and-braces behind fall detection |
| Remote access opens attack surface | High | Default off; token auth on every remote route; scope-limited remote API; TLS + cert pinning; Tailscale as recommended path; audit log |
| Mobile push without cloud is awkward | Medium | Honest tiering (§3); self-hosted relay option; WS-while-open baseline |
| Agent API keys on disk | Medium | OS keychain via Electron safeStorage; never in settings.json; remote API cannot read them |
| OpenCV/model deps bloat or break installs | Medium | All heavy deps optional extras; synthetic source keeps everything testable without them |
| Elderly-consent/ethics missteps | High | Consent section in README; Phase 7 features gated on explicit consent UX; no identity recognition ever (invariant 7) |
| Legacy archive loss (single HDD copy) | Low/High | Copy `ai-safety-camera/` into `legacy-reference/` branch when possible |

## 16. Open questions for the owner

Each question carries a **default** so a successor is never blocked
waiting for an answer — build the default unless the owner overrides.

1. Phone platform priority — iOS first, Android first, or both?
   **Default: both via Expo simultaneously.**
2. Is a self-hosted notification relay (ntfy on the hub, reachable over
   the tailnet) acceptable as the *only* push path, avoiding APNs/FCM
   entirely at the cost of iOS background delivery reliability?
   **Default: Tier 0/1 (WS while app open + local notifications) ships
   first; Tier 2 lands behind a flag with self-hosted ntfy as the
   reference implementation; APNs/FCM only if the owner explicitly asks.**
3. Which managed-agent provider first? **Default: local Ollama first
   (fully offline, matches local-first posture); Anthropic API as the
   opt-in upgrade behind the Phase 4 disclosure/consent copy.**
4. Should Phase 1 land in PR #1 or as its own PR? **Default: merge PR #1
   as-is; Phase 1 is a new PR** (branching rule in BUILD_STATUS §10).
5. Legacy archive: can `apps/ai-safety-camera/` be pushed to a
   `legacy-reference/` branch so future sessions can do line-level
   comparison? **Default until then: treat legacy work as concepts only,
   per §14.**

## 17. Glossary

- **Hub** — the desktop machine running backend + Electron app.
- **Hedged language** — phrasing that never claims certainty ("appears", "possible", "may be").
- **Harness** — the mechanism that runs the watching agent — webhook push, polling pull, or the managed in-backend runner (which calls an API, a local Ollama, or a user-supplied command) — as opposed to the *model* it calls.
- **Tier 0/1/2** — remote-access levels: LAN / owner tunnel / minimal push relay.
- **PK-nn** — package numbers from the legacy Sentinel work.
- **Trinity** — cameras + desktop + phone acting as one system.
