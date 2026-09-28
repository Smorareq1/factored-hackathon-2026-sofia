# frontend/ — dueño: AG

Next.js (App Router) + TypeScript + Tailwind. Pantallas previstas:

- `/`: login demo con OTP simulado (REQ-11)
- `/chat`: chat del cliente ES/PT + panel "caja de cristal" con los eventos de cada capa del agente
- `/console`: consola del agente humano: cola de handoffs, ficha §9.4 y feedback

## Correr

Con Docker, desde la raíz: `make up` (o `make dev` para hot reload). Queda en http://localhost:3000.

Sin Docker: `cp .env.example .env.local && npm install && npm run dev`.

> Next 16 trae cambios que rompen compatibilidad: ver `AGENTS.md` antes de escribir código.
