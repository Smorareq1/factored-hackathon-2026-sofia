# syntax=docker/dockerfile:1
# Imagen compartida para todos los paquetes Python del workspace de uv
# (contracts, data, ml, services, agent, eval, analysis).
#
# Contexto de build: raíz del repo (el workspace necesita uv.lock y contracts/).
#   docker build -f containers/python.Dockerfile --build-arg PACKAGE=sofia-agent --target runtime .
#
# Targets:
#   dev     -> compose local: instalación editable + deps de dev (pytest, ruff); el código se sincroniza con `compose watch`
#   runtime -> Cloud Run: solo el venv, sin uv, sin código fuente suelto, usuario no root
# El comando lo define quien corre la imagen (compose.yaml / servicio de Cloud Run).

ARG UV_IMAGE=ghcr.io/astral-sh/uv:python3.12-bookworm-slim
ARG RUNTIME_IMAGE=python:3.12-slim-bookworm

FROM ${UV_IMAGE} AS base
ARG PACKAGE
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"
WORKDIR /app
COPY . .

FROM base AS dev
ARG PACKAGE
RUN --mount=type=cache,target=/root/.cache/uv \
    test -n "${PACKAGE}" || (echo "Falta --build-arg PACKAGE" && exit 1) && \
    uv sync --frozen --package "${PACKAGE}"

FROM base AS build
ARG PACKAGE
RUN --mount=type=cache,target=/root/.cache/uv \
    test -n "${PACKAGE}" || (echo "Falta --build-arg PACKAGE" && exit 1) && \
    uv sync --frozen --no-dev --no-editable --package "${PACKAGE}"

# La imagen de uv deriva de python:3.12-slim-bookworm: el intérprete vive en la misma ruta y el venv sigue siendo válido.
FROM ${RUNTIME_IMAGE} AS runtime
ENV PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"
RUN useradd --create-home --uid 10001 app
COPY --from=build /opt/venv /opt/venv
USER app
WORKDIR /home/app
