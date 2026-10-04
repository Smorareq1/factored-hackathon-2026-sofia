# frontend/ — dueño: AG

Next.js 16 (App Router) + TypeScript + Tailwind v4. Sin librerías de UI ni de iconos ni de gráficas: todo es del sistema de diseño propio (Sofía DS).

| Ruta | Pantalla |
| --- | --- |
| `/` | Login demo con OTP simulado (REQ-11) |
| `/chat` | Chat del cliente ES/PT + caja de cristal con los eventos de cada capa del agente (REQ-19). Selector Sofía / Baseline (§8.7) si el agente tiene LLM |
| `/console` | Consola del agente humano: tablero de la cola, lista y ficha §9.4 (sin transcript, REQ-05) + feedback de la ficha (LEARN → score en la traza). La ficha muestra también los campos extra del contrato: `schema_version`, `customer_claim`, `system_version` y `created_at` |
| `/design` | Sofía DS en vivo: tokens, formas, iconos, átomos, moléculas, gráficas, organismos y movimiento |

## Sofía DS (diseño atómico)

Dirección visual: **colores sólidos y figuras geométricas**, con la disciplina de las páginas de producto (titulares grandes con
interletra cerrada, planos de color, botones píldora). Sin degradados, sin vidrio/blur, sin sombras difusas ni pasteles: los planos
se separan por color. Identidades: **cobalto = Sofía**, **amarillo sol = persona** (agente humano, baseline, LEARN), **tinta = cliente**.

```
app/globals.css            tokens (color, figuras, movimiento) + tema "night" (caja de cristal, panel de ingreso, ficha)
components/
├── atoms/                 Icon (+ icon-set: 52 iconos propios), Shape (10 figuras), Button, IconButton, Badge,
│                          StatusDot, Meter, Avatar, Flag, SofiaMark, Spinner, Card, Input…
├── molecules/             figures (FigureFrieze, CustomerFigure, FigureCluster), LayerTile, OtpInput, SmsToast, Stepper,
│   │                      Segmented, CustomerTile, CandidateOption,
│   │                      TransactionTicket, CaseReceipt, LayerTrack, PolicyLadder, FactRow, JsonView…
│   └── charts/            Sparkline, ColumnChart, BarList, SplitBar, RingGauge (SVG propio)
├── organisms/             ChatThread, Composer, GlassBox, TurnWaterfall, AuthPanel, QueueOverview,
│                          HandoffQueue, HandoffSheet, FeedbackForm (LEARN)
├── templates/             AuthShell, WorkspaceShell, AppHeader
└── screens/               login, chat, console, design (estado + llamadas a la API)
```

Reglas:

- Los componentes usan **tokens semánticos** (`bg-surface`, `text-ink-2`, `border-line`, `bg-brand-soft`…), nunca hex sueltos. El tema `data-theme="night"` cambia solo los tokens.
- Iconos: grilla de 24 px, trazo 1.75, `currentColor`. Uno nuevo se agrega en `atoms/icon-set.tsx`.
- Figuras (`atoms/shape.tsx`): grilla de 100 × 100, colores `--fig-*`. Son decorativas (`aria-hidden`), nunca llevan significado solas.
- Caja de cristal: cada capa tiene su figura (`LAYER_SHAPE`: meta = círculo, percepción = anillo, interpretación = triángulo, decisión = rombo, acción = cuadrado, guarda = arco, aprendizaje = hoja) sobre el color de su estado (cobalto ok, sol advertencia, rojo error, blanco corriendo). La misma figura se enciende en el chat mientras Sofía piensa. El texto sobre rellenos de estado usa los tokens `on-*` (blanco en claro, tinta en noche).
- Gráficas: las series `--series-1` (cobalto) y `--series-2` (frambuesa) tienen contraste ≥ 3:1 contra la superficie en ambos temas y se distinguen con daltonismo (azul frente a rosa). El texto va siempre en tinta, nunca del color de la serie.
- Movimiento: `ease-out-soft` / `ease-spring`, `animate-*` definidos en `globals.css` (titulares que suben desde una máscara, piezas que giran de a un cuarto de vuelta, cuadrado ↔ círculo). Todo respeta `prefers-reduced-motion`.
- Cada nivel importa solo de niveles inferiores (átomos ← moléculas ← organismos ← plantillas ← pantallas).

## Correr

Con Docker, desde la raíz: `docker compose -f containers/local/compose.yaml --env-file .env up -d --build frontend` (http://localhost:3000). La imagen trae el código horneado: después de cambiar código hay que reconstruirla (o usar `compose watch`).

Sin Docker: `cp .env.example .env.local && npm install && npm run dev`.

El enlace "ver traza" arma `{NEXT_PUBLIC_LANGFUSE_URL}/project/{NEXT_PUBLIC_LANGFUSE_PROJECT_ID}/traces/{trace_id}`.
En local el proyecto es `sofia-local`. En cloud hay que hornear el id real (`LANGFUSE_PROJECT_ID` en `.env`; `deploy.sh` lo pasa al build). Sin `NEXT_PUBLIC_LANGFUSE_URL` el enlace no se muestra.

Chequeos: `npx tsc --noEmit && npx eslint . && npx next build`.

> Next 16 trae cambios que rompen compatibilidad: ver `AGENTS.md` antes de escribir código.
