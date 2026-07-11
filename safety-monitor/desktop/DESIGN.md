# Safety Monitor — frontend design system

The visual language of the desktop app, and the contract for porting it
onto future renderer architectures (e.g. the sandboxed IPC renderer in the
Codex phase-0.5 work). The design is deliberately **markup + CSS level** —
nothing here depends on how data reaches the components.

## Concept

*A night watch.* Calm vigilance over someone you love — never alarmist,
honest about uncertainty. The UI's job is glanceable state: "is everything
okay?" answered by color and form before any text is read.

## Tokens (`src/styles.css`)

All colors/radii live as CSS custom properties on `:root`. Dark is the
home theme; light is first-class. Theme resolution: OS preference via
`prefers-color-scheme`, overridden both directions by
`html[data-theme="dark|light"]` (persisted choice, `src/theme.ts`).
**Style components only through tokens** — never hard-code a hex in a
component rule.

| Role | Dark | Light | Rule |
|---|---|---|---|
| Ground `--bg` | `#0c1113` | `#eff2f2` | teal-biased slate, never pure grey |
| Surfaces `--surface`→`-3` | `#12191c`→`#1f2b31` | `#fff`→`#e8eeee` | elevation = lighter (dark) / darker (light) |
| Accent `--accent` | `#4cc2b4` | `#158578` | sea-glass teal — **interactive things only** |
| OK `--ok` | `#7ac07e` | `#3e8f45` | status dots, live chip, risk-low |
| Warning `--warn` | `#d9a92f` | `#a97d10` | paused, warnings |
| Alert `--alert` | `#e0574f` | `#c9423a` | **reserved for alerts + destructive actions** |
| Simulated `--sim` | `#9a8cf0` | `#6a58c7` | owned exclusively by simulated/mock states |

Semantic colors are separate from the accent and never used decoratively.
`--sim` (violet) exists so a fake feed can never be mistaken for a real
one — that supports the product's truthful-runtime invariant.

## Type

Native system stack (`system-ui, -apple-system, 'Segoe UI', …`) — a
deliberate choice: a desktop utility should feel like the OS it guards
from. Base 13.5px/1.5. Hierarchy by weight (650 headings, 550 controls)
and micro-caps labels (`.microcaps`: 10px/700/0.09em tracking) — not by
large sizes. All timestamps and figures use `tabular-nums`.

## Status vocabulary (the core of the design)

| State | Form |
|---|---|
| Live feed | `.chip-live` green chip with pulsing dot |
| Simulated feed | `.chip-sim` violet chip **plus** persistent `.sim-watermark` on the frame — both must survive any redesign |
| Paused | `.chip-paused` amber chip + full-frame overlay ("No frames are being read while paused") |
| Backend down | full-screen `.boot`: "Backend unavailable — reconnecting…" — never show cached/mock content in its place |
| Event severity | 3px left rail on the card (`.sev-rail`) + stroke icon: info circle / warning triangle / alert octagon |
| Confidence | small meter + `~NN%` — always approximate, tooltip says "never a certainty" |
| Agent assessment | nested quiet card with agent icon + risk chip |
| Connection | sidebar footer dot: green steady = connected, amber pulsing = reconnecting |

## Components

Buttons: `.btn` (neutral), `.btn-primary` (accent, one per view max),
`.btn-danger` / `.btn-danger-outline` (destructive/emergency only),
`.btn-ghost` (row actions). Segmented controls: `.seg`. Switches:
`.switch(.on|.warn-on)` inside `.switch-row`. Chips: `.chip-*`,
`.risk-chip.risk-*`. Cards: `.card`, `.danger-card`. Dialog:
`.dialog-backdrop` + `.dialog` with icon slot — used for every
destructive or emergency confirmation (pairs with the backend's HTTP 428
gate). Icons: `src/icons.tsx`, 24-grid stroke SVG, 1.8px stroke — no
emoji, no icon fonts.

## Copy rules (words are design material)

- Safety statements are hedged, always: "appears", "possible", "may be".
- Controls say what happens: "Save zones", "Delete everything",
  "Yes, take action".
- Privacy promises are stated where the control lives ("Everything stays
  on this computer.").
- Simulated is labeled *simulated*, everywhere it appears.

## Porting notes (for the IPC/sandboxed renderer)

- Components consume data via props/hooks only; swap the transport
  (fetch/WS → IPC bridge) without touching markup or CSS.
- `streamUrl()`/`eventSnapshotUrl()` become custom-scheme URLs — the
  `<img>` elements don't care.
- Keep `.sim-watermark`, the paused overlay, and the backend-down screen
  intact — they implement product invariants, not decoration.
- Verified with rendered Chromium screenshots (dark+light, all four
  views + dialog) against a real backend; re-verify the same way after
  porting.
