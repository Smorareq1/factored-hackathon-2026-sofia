#!/usr/bin/env bash
# Permite que GitHub Actions despliegue en Cloud Run sin llaves JSON (CON-03): Workload Identity Federation.
# Se corre una sola vez, con una cuenta Owner del proyecto. Idempotente.
#
#   infra/cloudrun/setup-github-deploy.sh
#
# Crea la cuenta sofia-deployer con lo mínimo para `deploy.sh release` y un pool OIDC que solo acepta
# tokens de este repo emitidos para la rama develop (.github/workflows/deploy.yml).
set -euo pipefail

PROJECT="${GCP_PROJECT:-sofia-factored-hackathon}"
GITHUB_REPO="${GITHUB_REPO:-Smorareq1/factored-hackathon-2026-sofia}"
DEPLOY_REF="${DEPLOY_REF:-refs/heads/develop}"
POOL="github"
PROVIDER="github-oidc"
SA="sofia-deployer@$PROJECT.iam.gserviceaccount.com"
GC=(gcloud --project "$PROJECT" --quiet)

log() { printf '\n\033[1m▸ %s\033[0m\n' "$*"; }

NUMBER="$("${GC[@]}" projects describe "$PROJECT" --format 'value(projectNumber)')"

log "APIs"
"${GC[@]}" services enable iamcredentials.googleapis.com sts.googleapis.com

log "Cuenta de servicio sofia-deployer"
"${GC[@]}" iam service-accounts describe "$SA" >/dev/null 2>&1 ||
  "${GC[@]}" iam service-accounts create sofia-deployer --display-name "S.O.F.I.A. deploy desde GitHub Actions"

# deploy.sh release: envía builds, despliega servicios, consulta secretos (sin leer su valor) y sigue los logs.
for role in roles/cloudbuild.builds.editor roles/run.admin roles/secretmanager.viewer \
  roles/storage.admin roles/logging.viewer roles/serviceusage.serviceUsageConsumer; do
  "${GC[@]}" projects add-iam-policy-binding "$PROJECT" --member "serviceAccount:$SA" --role "$role" \
    --condition None >/dev/null
  echo "  $role"
done
# Actúa como las cuentas con las que corren el build y los servicios.
for target in sofia-build sofia-agent sofia-runtime; do
  "${GC[@]}" iam service-accounts add-iam-policy-binding "$target@$PROJECT.iam.gserviceaccount.com" \
    --member "serviceAccount:$SA" --role roles/iam.serviceAccountUser >/dev/null
  echo "  serviceAccountUser en $target"
done

# Cloud Run valida que quien despliega pueda leer la imagen del registry.
"${GC[@]}" artifacts repositories add-iam-policy-binding sofia --location "${GCP_REGION:-us-central1}" \
  --member "serviceAccount:$SA" --role roles/artifactregistry.reader >/dev/null
echo "  artifactregistry.reader en sofia"

log "Workload Identity Pool ($POOL / $PROVIDER)"
"${GC[@]}" iam workload-identity-pools describe "$POOL" --location global >/dev/null 2>&1 ||
  "${GC[@]}" iam workload-identity-pools create "$POOL" --location global --display-name "GitHub Actions"
CONDITION="assertion.repository == '$GITHUB_REPO' && assertion.ref == '$DEPLOY_REF'"
if "${GC[@]}" iam workload-identity-pools providers describe "$PROVIDER" --location global \
  --workload-identity-pool "$POOL" >/dev/null 2>&1; then
  "${GC[@]}" iam workload-identity-pools providers update-oidc "$PROVIDER" --location global \
    --workload-identity-pool "$POOL" --attribute-condition "$CONDITION" >/dev/null
else
  "${GC[@]}" iam workload-identity-pools providers create-oidc "$PROVIDER" --location global \
    --workload-identity-pool "$POOL" --display-name "GitHub OIDC" \
    --issuer-uri https://token.actions.githubusercontent.com \
    --attribute-mapping "google.subject=assertion.sub,attribute.repository=assertion.repository,attribute.ref=assertion.ref" \
    --attribute-condition "$CONDITION"
fi

"${GC[@]}" iam service-accounts add-iam-policy-binding "$SA" --role roles/iam.workloadIdentityUser \
  --member "principalSet://iam.googleapis.com/projects/$NUMBER/locations/global/workloadIdentityPools/$POOL/attribute.repository/$GITHUB_REPO" \
  >/dev/null

log "Listo. Valores para .github/workflows/deploy.yml (no son secretos):"
echo "  workload_identity_provider: projects/$NUMBER/locations/global/workloadIdentityPools/$POOL/providers/$PROVIDER"
echo "  service_account:            $SA"
