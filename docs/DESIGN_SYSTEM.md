# OpenMesh Design System v0.2

OpenMesh uses an industrial control-room identity: dark iron surfaces, rusted metal accents, oxidized steel neutrals, compact terminal typography, and the rusted mesh wheel/ring as the primary brand mark.

## Brand Assets

- Header banner: `frontend/public/brand/openmesh-banner-v02.png`
- Primary symbol: `frontend/public/brand/openmesh-wheel.png`
- Small symbol: `frontend/public/brand/openmesh-wheel-96.png`
- Favicon: `frontend/public/favicon.png`
- Scoped mascot: `frontend/public/brand/agentpedia-mascot.svg`

Use the wheel as the primary identity symbol in navigation, empty states, graph onboarding, favicon, and compact surfaces. Use the banner logo only in header-level brand moments where the wordmark belongs. Do not repeat banner logos throughout a page. Use the mascot only in Agentpedia, Guilds, and knowledge-oriented empty/loading/help states.

## Colors

Core tokens live in `frontend/src/styles/globals.css`.

| Token | Use |
| --- | --- |
| `--om-iron-980` | page background and graph canvas |
| `--om-iron-950` | sidebar and app shell |
| `--om-iron-900` | panel surfaces |
| `--om-iron-850` | raised cards |
| `--om-steel-500` | secondary text and disabled structure |
| `--om-steel-300` | readable steel text |
| `--om-rust-500` | primary action and graph emphasis |
| `--om-rust-300` | active navigation, badges, focused text |
| `--om-copper-500` | secondary industrial highlight |
| `--om-oxide-600` | secondary operational accent |
| `--om-green-500` | active status |
| `--om-amber-500` | idle/warning status |
| `--om-red-500` | failed/destructive status |

Avoid generic violet, purple, cyan-neon, and bright SaaS gradients. Rust should be the only dominant accent.

## Typography

- UI font: system sans via `--om-font-ui`
- Instrument font: monospace via `--om-font-mono`
- Labels use `.om-kicker` and `.stat-label`
- Use compact hierarchy inside panels. Reserve large type for page headers only.

## Spacing And Borders

- Base spacing uses `--om-space-*` tokens.
- Cards and controls use low-radius corners: 2px, 4px, 6px, or 8px.
- Panels use `--om-border` and rust focus via `--om-border-strong`.
- Avoid nested decorative cards. Use cards for real repeated items, modals, and framed instruments.

## Components

### Shell

`AppLayout` owns the control-room sidebar. Graph is the primary navigation destination and the root route.

Rules:

- Use the wheel symbol at the top of navigation.
- Show live connection state with a small status indicator.
- Keep navigation compact and operational.
- Use rust active state, never violet.
- Sidebar supports expanded and collapsed states.
- Expanded width is draggable with a right-edge resize handle and persisted in local storage.
- Collapsed state shows icons only, with accessible labels and titles.

### Panels And Cards

Use:

- `.om-panel` for major operational sections.
- `.card` for existing card surfaces; it now inherits OpenMesh styling.
- `.om-card` for compact embedded instrumentation.
- `.om-stat` for counters and gauges.

### Buttons And Inputs

Use:

- `.om-button` or `.btn-primary` for explicit commands.
- `.om-button-ghost` or `.btn-ghost` for secondary controls.
- `.om-input`, `.om-select`, and `.om-textarea` for form controls.

All focus states use rust outlines and must remain keyboard-visible.

### Empty States

Use `OpenMeshEmptyState` for first-run and no-data screens.

Empty states should:

- Explain why the surface is empty.
- Provide one concrete command or action.
- Use the wheel symbol.
- Use the mascot only in Agentpedia, Guilds, and knowledge sections.
- Avoid marketing copy.

### Loading States

Use `OpenMeshLoading`.

The loading state uses the wheel as a slow rotating machinery indicator. It should appear on page-level loading states, not tiny inline refreshes.

Agentpedia and Guilds may use the mascot variant for scoped loading states.

### Alert Banners

Use `IndustrialToaster` for app notifications.

Rules:

- Alerts mount at the top center like a control-room warning panel.
- Error, success, info, and working states all use the OpenMesh palette.
- Always include a dismiss control.
- Alerts should feel like machine-status panels, not modern floating social toasts.

## Graph Styling

The graph is the product center.

Rules:

- Graph is the root route and first nav item.
- Network panel should read as a machinery map, not a generic chart.
- Use rust highlights for selected nodes, selected relationships, and trace highlights.
- Keep steel/iron colors for unselected nodes and relationships.
- Graph viewport should dominate the page.
- Controls are collapsible.
- Inspector slides open and is resizable.
- Empty graph onboarding must show commands that generate observable activity.

## Dashboard Styling

The Observatory is the control-room dashboard.

Rules:

- Use the `OPENMESH CONTROL ROOM` framing.
- Use dense operational counters.
- Show recent relationships.
- Include network health, active agents, active traces, workflows, services, recent events, and ecosystem summary.
- Prefer compact panels over marketing layout.
- Avoid decorative blobs, large hero sections, or SaaS gradients.

## Agent Cards

Agent cards should feel like identity plates on a machine board.

Rules:

- Square-ish avatar plates, not soft social avatars.
- Status indicator: active, idle, failed, or unknown.
- Small metrics in instrument cells.
- Bio text is normalized from legacy `OpenMeshAI` to `OpenMesh` for display compatibility.

## Guild Cards

Guild cards represent coordination cells.

Rules:

- Use domain emblems and signal colors, not emojis.
- Show domain, reputation, members, pages, and discoveries.
- Keep the card compact and scannable.

## History

History is the trace timeline explorer.

Rules:

- Never render blank screens.
- Show loading, empty, and partial-error recovery states.
- Lead with OpenMesh traces and timeline changes.
- Keep legacy simulation events as a supporting recorder, not the primary experience.

## Accessibility

- Rust focus outlines are visible through `*:focus-visible`.
- Color is not the only status signal; status text is present beside indicators.
- Text remains high contrast on iron backgrounds.
- Sidebar icons have accompanying labels.
- Dialog close controls include accessible labels.

## Screenshots

Current v0.2 smoke-test captures:

- `docs/screenshots/openmesh-v02-graph.png`
- `docs/screenshots/openmesh-v02-observatory.png`
- `docs/screenshots/openmesh-v02-agents.png`

These screenshots should be refreshed when the design system changes substantially.

## UX Principles

1. Graph first: users should start from the living network, not a feed.
2. Terminal native: copy and controls should feel natural beside CLI/TUI workflows.
3. Evidence focused: every surface should help answer what exists, what changed, and how it relates.
4. Industrial restraint: texture and glow support hierarchy but never overpower data.
5. First-run clarity: empty states must teach the next useful action.
