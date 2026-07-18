# Sentinel — "calm instrument" design system

The visual language of the desktop app. Direction chosen by the owner
(2026-07-18) from a rendered mockup; supersedes the earlier teal
"night watch" theme. The design is markup + CSS level — nothing depends
on how data reaches the components, so it ports to the sandboxed IPC
renderer unchanged.

## Concept spine

**A quiet instrument keeping watch.** Cream paper panel, ink linework,
mono readouts, hedged language built into the chrome. The app should
feel like a precision instrument that reassures — never a surveillance
terminal, never a SaaS dashboard.

**Signature:** the Live headline is a real reading — derived from
unreviewed warning/alert events, in hedged words:
*"All quiet, nothing needs you."* / *"Something may need you."* (the
only place terracotta type appears at display size).

## Tokens (`src/styles.css`)

Two explicit faces of one instrument. Day is home; night is the same
panel with its lamp on (warm ink, not cool slate). OS preference
default, persisted toggle via `html[data-theme]` (`src/theme.ts`).

| Role | Day (cream) | Night (warm ink) | Rule |
|---|---|---|---|
| Ground `--bg` | `#ece7db` | `#171510` | warm always; never `#000`, never cool grey |
| Surfaces | `#f4f0e5`→`#dcd5c1` | `#1e1b14`→`#302a1f` | flat fills, hairline borders, no blur/gradients |
| Hairline `--border` | `#c8c1ac` | `#3a3426` | 1px structure everywhere |
| Ink `--text` | `#26231a` | `#e9e4d5` | |
| **Accent** `--accent` | olive `#4e5b3f` | lightened olive `#8fa075` | THE one interactive accent |
| Alert `--alert` | terracotta `#b65c3d` | `#d0765a` | **reserved**: alerts + destructive only |
| Warn `--warn` | mustard `#a8891f` | `#d1b13c` | paused, warnings |
| OK `--ok` | `#55703f` | `#84b06a` | live dot, reviewed, link ok |
| Simulated `--sim` | violet `#6a58c7` | `#a99aec` | **owned by SIMULATED** — the one off-palette hue, so fake feeds can never pass as real |

Status hues are instrument readings, never decoration; the accent is
never used for status.

## Type

- **Display** (`--disp`, system stack): headings only, 650 weight,
  tight tracking.
- **Data** (`--mono`, ui-monospace stack): everything the instrument
  says — nav, chips, timestamps, buttons, eyebrows, meters — uppercase
  micro-labels at 0.1–0.18em tracking (`.microcaps`), tabular numerals.
  Mono is the voice of the machine; display is the voice of the app.

## Materials

Radii: cards 10px, controls 6px, **chips 3px** (square-ish deck
labels), pills/dots full. Dot-grid ground texture
(`radial-gradient` 14px) on panel surfaces. Shadows: one soft drop for
the camera frame (the hero object), an inset "deck-button lip" on
primary/danger buttons that flattens with `translateY(1px)` on press,
and a small hard-offset on the emergency outline button. No
glassmorphism, no backdrop blur, no gradients-as-brand.

## Status vocabulary (must survive any restyle)

- Camera frame wears **viewfinder corner brackets**; chips live inside
  the glass: `● LIVE` (pulsing), `SIMULATED` (violet, plus persistent
  `.sim-watermark`), `PAUSED`; bottom data strip shows real readings
  only (clock, FPS, mask count, `AI REAL · ON-DEVICE` / `AI MOCK` /
  `AI OFF` from `/api/health`).
- Timeline = logbook: marker squares (ink / mustard / terracotta) not
  icons, mono event types, `~NN%` confidence with meter.
- Privacy switches are retro **ON/OFF pills**; nav rows carry square
  tick markers; sidebar footer reads `● LINK OK` / `RELINKING…`.
- Backend down = full-screen boot card: no cached or simulated data
  shown in its place, ever.
- No emoji anywhere in the UI; the brand mark is the **bitmap watching
  eye** (`PixelEyeIcon`), pupil in accent.

## Copy rules

Hedged, always, for anything the cameras claim ("appears", "may have",
"possible", `~` before percentages, "nothing here is a certainty").
Controls name outcomes ("Save zones", "Yes, take action"). Privacy
promises stated where the control lives. Warm and human in the chrome,
never SaaS.

## Verification

Rendered in Chromium against a real backend: both faces × live /
timeline / zones / settings / pairing / emergency dialog. Re-verify
the same way after any port (IPC renderer, phone page changes).
