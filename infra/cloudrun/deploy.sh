#!/usr/bin/env bash
# Despliegue de S.O.F.I.A. en Cloud Run (DEL-02). Idempotente: re-correrlo actualiza los servicios.
#
#   infra/cloudrun/deploy.sh            # todo: APIs, registry, cuentas de servicio, secretos, imágenes, servicios
#   infra/cloudrun/deploy.sh services   # solo re-despliega con las imágenes ya construidas
#   infra/cloudrun/deploy.sh release    # imágenes + servicios, sin tocar APIs, IAM ni secretos (CD desde develop)
#
# Requisitos: gcloud autenticado con permisos de Owner/Editor en el proyecto (`release` basta con sofia-deployer,
# ver setup-github-deploy.sh).
# Secretos: se leen de .env (LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY; DATABASE_URL_CLOUD y ADMIN_API_KEY opcionales) y se suben a
# Secret Manager; nunca se imprimen ni se pasan como variables de entorno en texto plano (CON-03).
set -euo pipefail

PROJECT="${GCP_PROJECT:-sofia-factored-hackathon}"
REGION="${GCP_REGION:-us-central1}"
REPO="sofia"
VERTEX_LOCATION="${VERTEX_LOCATION:-global}"
# min-instances=1 solo en la ventana con jueces (DEL-02): MIN_INSTANCES=1 infra/cloudrun/deploy.sh services
MIN_INSTANCES="${MIN_INSTANCES:-0}"

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
TAG="$(git -C "$ROOT" rev-parse --short HEAD)"
IMG="${REGION}-docker.pkg.dev/${PROJECT}/${REPO}"
GC=(gcloud --project "$PROJECT" --quiet)

log() { printf '\n\033[1m▸ %s\033[0m\n' "$*"; }

env_value() { # lee una variable de .env sin exportar el archivo entero
  [ -f "$ROOT/.env" ] || return 0
  { grep -E "^$1=" "$ROOT/.env" || true; } | tail -1 | cut -d= -f2- | sed -e 's/^"//' -e 's/"$//'
}

LANGFUSE_HOST_CLOUD="${LANGFUSE_HOST_CLOUD:-$(env_value LANGFUSE_HOST)}"
LANGFUSE_HOST_CLOUD="${LANGFUSE_HOST_CLOUD:-https://us.cloud.langfuse.com}"
# El frontend hornea este id en el link /project/<id>/traces. Local queda en sofia-local.
LANGFUSE_PROJECT_ID="${LANGFUSE_PROJECT_ID:-$(env_value LANGFUSE_PROJECT_ID)}"
LANGFUSE_PROJECT_ID="${LANGFUSE_PROJECT_ID:-sofia-local}"

ensure_platform() {
  log "APIs"
  "${GC[@]}" services enable run.googleapis.com artifactregistry.googleapis.com cloudbuild.googleapis.com \
    secretmanager.googleapis.com aiplatform.googleapis.com

  log "Artifact Registry ($REPO)"
  "${GC[@]}" artifacts repositories describe "$REPO" --location "$REGION" >/dev/null 2>&1 ||
    "${GC[@]}" artifacts repositories create "$REPO" --location "$REGION" --repository-format docker \
      --description "Imágenes de S.O.F.I.A."

  log "Cuentas de servicio"
  for sa in sofia-agent sofia-runtime sofia-build; do
    "${GC[@]}" iam service-accounts describe "$sa@$PROJECT.iam.gserviceaccount.com" >/dev/null 2>&1 ||
      "${GC[@]}" iam service-accounts create "$sa" --display-name "S.O.F.I.A. $sa"
  done
  # El agente llama a Gemini por Vertex AI (créditos de GCP) y lee sus secretos; el resto no necesita roles.
  "${GC[@]}" projects add-iam-policy-binding "$PROJECT" \
    --member "serviceAccount:sofia-agent@$PROJECT.iam.gserviceaccount.com" --role roles/aiplatform.user \
    --condition None >/dev/null
  # Cloud Build corre con su propia cuenta: la default de Compute no tiene permisos en proyectos nuevos.
  "${GC[@]}" projects add-iam-policy-binding "$PROJECT" \
    --member "serviceAccount:sofia-build@$PROJECT.iam.gserviceaccount.com" --role roles/cloudbuild.builds.builder \
    --condition None >/dev/null
}

ensure_secret() { # ensure_secret <nombre> <variable de .env> [cuenta que lo lee, sofia-agent por defecto]
  local name="$1" sa="${3:-sofia-agent}" value
  value="$(env_value "$2")"
  if [ -z "$value" ]; then
    echo "  $name: $2 vacío en .env, se omite"
    return 0
  fi
  "${GC[@]}" secrets describe "$name" >/dev/null 2>&1 || "${GC[@]}" secrets create "$name" --replication-policy automatic
  # Solo agrega versión si cambió el valor
  if [ "$("${GC[@]}" secrets versions access latest --secret "$name" 2>/dev/null || true)" != "$value" ]; then
    printf '%s' "$value" | "${GC[@]}" secrets versions add "$name" --data-file - >/dev/null
    echo "  $name: nueva versión"
  else
    echo "  $name: sin cambios"
  fi
  "${GC[@]}" secrets add-iam-policy-binding "$name" \
    --member "serviceAccount:$sa@$PROJECT.iam.gserviceaccount.com" \
    --role roles/secretmanager.secretAccessor >/dev/null
}

secret_exists() { "${GC[@]}" secrets describe "$1" >/dev/null 2>&1; }

build() { # build backend|frontend [agent_url]
  log "Cloud Build: $1 ($TAG)"
  local ret=0
  "${GC[@]}" beta builds submit "$ROOT" --config "$ROOT/infra/cloudrun/cloudbuild.yaml" --region "$REGION" \
    --service-account "projects/$PROJECT/serviceAccounts/sofia-build@$PROJECT.iam.gserviceaccount.com" \
    --substitutions "_REGION=$REGION,_REPO=$REPO,_TAG=$TAG,_TARGETS=$1,_AGENT_URL=${2:-},_LANGFUSE_URL=${3:-},_LANGFUSE_PROJECT_ID=$LANGFUSE_PROJECT_ID" || ret=$?
  if [ "$ret" -ne 0 ]; then
    log "Cloud Build fallo ($ret). Obteniendo logs del build:"
    local last_build
    last_build="$("${GC[@]}" builds list --region "$REGION" --limit 1 --format 'value(id)' 2>/dev/null || true)"
    if [ -n "$last_build" ]; then
      "${GC[@]}" builds log "$last_build" --region "$REGION" || true
    fi
    return "$ret"
  fi
}

url_of() { "${GC[@]}" run services describe "$1" --region "$REGION" --format 'value(status.url)' 2>/dev/null || true; }

deploy_python() { # deploy_python <servicio> <imagen> <módulo:app> <cuenta> [flags extra...]
  local name="$1" image="$2" app="$3" sa="$4"
  shift 4
  log "Cloud Run: $name"
  "${GC[@]}" run deploy "$name" --region "$REGION" --image "$IMG/$image:$TAG" \
    --service-account "$sa@$PROJECT.iam.gserviceaccount.com" \
    --command uvicorn --args "$app,--host,0.0.0.0,--port,8080,--proxy-headers" \
    --allow-unauthenticated --min-instances "$MIN_INSTANCES" --cpu 1 --memory 1Gi "$@"
}

deploy_services() {
  deploy_python router router sofia_ml.serve:app sofia-runtime --max-instances 3 \
    --set-env-vars "SOFIA_ENV=cloud"
  # bank-api guarda sesiones, OTP y disputas en memoria: una sola instancia para que todas las llamadas vean el mismo
  # estado. Sin el secreto admin-api-key, /admin/* y /session/test responden 403 en la nube (require_admin_or_local).
  local bank_secrets=()
  secret_exists admin-api-key && bank_secrets=(--set-secrets "ADMIN_API_KEY=admin-api-key:latest")
  deploy_python bank-api bank-api sofia_services.main:app sofia-runtime --max-instances 1 \
    --set-env-vars "SOFIA_ENV=cloud" ${bank_secrets[@]+"${bank_secrets[@]}"}
  local router_url bank_url frontend_url secrets=() env
  router_url="$(url_of router)"
  bank_url="$(url_of bank-api)"
  frontend_url="$(url_of frontend)"

  # El agente usa el bank-api desplegado; AGENT_BANK_API_URL=fake vuelve al banco en proceso.
  local agent_bank="${AGENT_BANK_API_URL:-${bank_url:-fake}}"
  env="SOFIA_ENV=cloud,BANK_API_URL=$agent_bank,ROUTER_URL=$router_url"
  env+=",GEMINI_BACKEND=vertex,GOOGLE_CLOUD_PROJECT=$PROJECT,GOOGLE_CLOUD_LOCATION=$VERTEX_LOCATION"
  env+=",SOFIA_LLM_MODE=auto,CORS_ORIGINS=${frontend_url:-http://localhost:3000}"
  [ -n "$(env_value GEMINI_MODEL)" ] && env+=",GEMINI_MODEL=$(env_value GEMINI_MODEL)"
  if secret_exists langfuse-secret-key; then
    env+=",LANGFUSE_HOST=$LANGFUSE_HOST_CLOUD"
    secrets+=("LANGFUSE_PUBLIC_KEY=langfuse-public-key:latest" "LANGFUSE_SECRET_KEY=langfuse-secret-key:latest")
  fi
  secret_exists database-url && secrets+=("DATABASE_URL=database-url:latest")
  local secret_flag=()
  [ ${#secrets[@]} -gt 0 ] && secret_flag=(--set-secrets "$(IFS=,; echo "${secrets[*]}")")

  # Sin DATABASE_URL las conversaciones viven en memoria: una sola instancia para no perder hilos entre requests.
  local max=1
  secret_exists database-url && max=3
  deploy_python agent agent sofia_agent.api.main:app sofia-agent --max-instances "$max" --timeout 300 \
    --set-env-vars "$env" ${secret_flag[@]+"${secret_flag[@]}"}
  echo "  agente → BANK_API_URL=$agent_bank"
}

deploy_frontend() {
  local agent_url
  agent_url="$(url_of agent)"
  build frontend "$agent_url" "$( secret_exists langfuse-secret-key && echo "$LANGFUSE_HOST_CLOUD" )"
  log "Cloud Run: frontend"
  "${GC[@]}" run deploy frontend --region "$REGION" --image "$IMG/frontend:$TAG" \
    --service-account "sofia-runtime@$PROJECT.iam.gserviceaccount.com" \
    --allow-unauthenticated --min-instances "$MIN_INSTANCES" --max-instances 3 --cpu 1 --memory 512Mi --port 8080
  # El agente acepta CORS solo desde la URL real del frontend
  "${GC[@]}" run services update agent --region "$REGION" \
    --update-env-vars "CORS_ORIGINS=$(url_of frontend)" >/dev/null
}

main() {
  case "${1:-all}" in
    all)
      ensure_platform
      log "Secret Manager"
      ensure_secret langfuse-public-key LANGFUSE_PUBLIC_KEY
      ensure_secret langfuse-secret-key LANGFUSE_SECRET_KEY
      ensure_secret database-url DATABASE_URL_CLOUD
      ensure_secret admin-api-key ADMIN_API_KEY sofia-runtime
      build backend
      deploy_services
      deploy_frontend
      ;;
    release)
      build backend
      deploy_services
      deploy_frontend
      ;;
    services)
      deploy_services
      deploy_frontend
      ;;
    *)
      echo "uso: $0 [all|release|services]" >&2
      exit 2
      ;;
  esac
  log "Listo"
  for s in frontend agent router bank-api; do printf '  %-9s %s\n' "$s" "$(url_of "$s")"; done
}

main "$@"
