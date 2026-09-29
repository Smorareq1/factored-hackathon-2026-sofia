# syntax=docker/dockerfile:1
# Imagen del frontend Next.js (AG).
# Contexto de build: frontend/
#   docker build -f containers/frontend.Dockerfile --target runtime frontend
#
# Targets:
#   dev     -> `next dev` con hot reload vía `compose watch`
#   runtime -> Cloud Run: salida `standalone` de Next, usuario no root, puerto 8080

ARG NODE_IMAGE=node:22-bookworm-slim

FROM ${NODE_IMAGE} AS deps
WORKDIR /app
ENV NEXT_TELEMETRY_DISABLED=1
COPY package.json package-lock.json ./
RUN --mount=type=cache,target=/root/.npm npm ci

FROM deps AS dev
COPY . .
EXPOSE 3000
CMD ["npm", "run", "dev", "--", "--hostname", "0.0.0.0", "--port", "3000"]

FROM deps AS build
# NEXT_PUBLIC_* se incrustan en el bundle al compilar: se pasan como build args
ARG NEXT_PUBLIC_AGENT_URL
ARG NEXT_PUBLIC_LANGFUSE_URL
ENV NEXT_PUBLIC_AGENT_URL=${NEXT_PUBLIC_AGENT_URL} \
    NEXT_PUBLIC_LANGFUSE_URL=${NEXT_PUBLIC_LANGFUSE_URL}
COPY . .
RUN npm run build

FROM ${NODE_IMAGE} AS runtime
WORKDIR /app
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    HOSTNAME=0.0.0.0 \
    PORT=8080
COPY --from=build --chown=node:node /app/public ./public
COPY --from=build --chown=node:node /app/.next/standalone ./
COPY --from=build --chown=node:node /app/.next/static ./.next/static
USER node
EXPOSE 8080
CMD ["node", "server.js"]
