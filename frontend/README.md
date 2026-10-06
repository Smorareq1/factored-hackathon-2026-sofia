# frontend/ — owner: AG

Next.js 16 (App Router) + TypeScript + Tailwind v4. No UI, icon or chart libraries: everything comes from our own design system (Sofía DS). The interface text the customer and the human agent see is in Spanish and Portuguese.

| Route | Screen |
| --- | --- |
| `/` | Demo login with simulated OTP (REQ-11) |
| `/chat` | ES/PT customer chat + glass box with the events of each agent layer (REQ-19). Sofía / Baseline selector (§8.7) when the agent has an LLM |
| `/console` | Human agent console: queue board, list and §9.4 card (no transcript, REQ-05) + feedback on the card (LEARN → score on the trace). The card also shows the contract's extra fields: `schema_version`, `customer_claim`, `system_version` and `created_at` |
| `/design` | Sofía DS live: tokens, shapes, icons, atoms, molecules, charts, organisms and motion |

## Sofía DS (atomic design)

Visual direction: **solid colors and geometric shapes**, with the discipline of product pages (large headlines with tight
letter spacing, flat color fields, pill buttons). No gradients, no glass/blur, no diffuse shadows or pastels: areas are
separated by color. Identities: **cobalt = Sofía**, **sun yellow = person** (human agent, baseline, LEARN), **ink = customer**.

```
app/globals.css            tokens (color, shapes, motion) + "night" theme (glass box, login panel, card)
components/
├── atoms/                 Icon (+ icon-set: 52 custom icons), Shape (10 shapes), Button, IconButton, Badge,
│                          StatusDot, Meter, Avatar, Flag, SofiaMark, Spinner, Card, Input…
├── molecules/             figures (FigureFrieze, CustomerFigure, FigureCluster), LayerTile, OtpInput, SmsToast, Stepper,
│   │                      Segmented, CustomerTile, CandidateOption,
│   │                      TransactionTicket, CaseReceipt, LayerTrack, PolicyLadder, FactRow, JsonView…
│   └── charts/            Sparkline, ColumnChart, BarList, SplitBar, RingGauge (custom SVG)
├── organisms/             ChatThread, Composer, GlassBox, TurnWaterfall, AuthPanel, QueueOverview,
│                          HandoffQueue, HandoffSheet, FeedbackForm (LEARN)
├── templates/             AuthShell, WorkspaceShell, AppHeader
└── screens/               login, chat, console, design (state + API calls)
```

Rules:

- Components use **semantic tokens** (`bg-surface`, `text-ink-2`, `border-line`, `bg-brand-soft`…), never loose hex values. The `data-theme="night"` theme only changes the tokens.
- Icons: 24 px grid, 1.75 stroke, `currentColor`. A new one is added in `atoms/icon-set.tsx`.
- Shapes (`atoms/shape.tsx`): 100 × 100 grid, `--fig-*` colors. They are decorative (`aria-hidden`) and never carry meaning on their own.
- Glass box: each layer has its shape (`LAYER_SHAPE`: purpose = circle, sense = ring, interpret = triangle, decide = diamond, act = square, govern = arc, learn = leaf) over its state color (cobalt ok, sun warning, red error, white running). The same shape lights up in the chat while Sofía thinks. Text on state fills uses the `on-*` tokens (white in light, ink in night).
- Charts: series `--series-1` (cobalt) and `--series-2` (raspberry) have ≥ 3:1 contrast against the surface in both themes and stay distinguishable with color blindness (blue vs pink). Text is always ink, never the series color.
- Motion: `ease-out-soft` / `ease-spring`, `animate-*` defined in `globals.css` (headlines rising from a mask, pieces turning a quarter at a time, square ↔ circle). Everything respects `prefers-reduced-motion`.
- Each level only imports from lower levels (atoms ← molecules ← organisms ← templates ← screens).

## Running

With Docker, from the root: `docker compose -f containers/local/compose.yaml --env-file .env up -d --build frontend` (http://localhost:3000). The image has the code baked in: after changing code, rebuild it (or use `compose watch`).

Without Docker: `cp .env.example .env.local && npm install && npm run dev`.

The "view trace" link builds `{NEXT_PUBLIC_LANGFUSE_URL}/project/{NEXT_PUBLIC_LANGFUSE_PROJECT_ID}/traces/{trace_id}`.
Locally the project is `sofia-local`. In the cloud the real id must be baked in (`LANGFUSE_PROJECT_ID` in `.env`; `deploy.sh` passes it to the build). Without `NEXT_PUBLIC_LANGFUSE_URL` the link is not shown.

Checks: `npx tsc --noEmit && npx eslint . && npx next build`.

> Next 16 has breaking changes: read `AGENTS.md` before writing code.
