#!/usr/bin/env bash
set -euo pipefail

# Run in Google Cloud Shell after choosing the billing-enabled project.
# Required: PROJECT_ID
# Optional: ZONE, VM_NAME, REPOSITORY, MACHINE_TYPE

: "${PROJECT_ID:?Set PROJECT_ID to the billing-enabled Google Cloud project ID}"
ZONE="${ZONE:-asia-northeast1-b}"
VM_NAME="${VM_NAME:-aiif-note-draft}"
REPOSITORY="${REPOSITORY:-trendhub-ab/ai-intelligence-factory}"
MACHINE_TYPE="${MACHINE_TYPE:-e2-medium}"
POOL_ID="${POOL_ID:-github-actions}"
PROVIDER_ID="${PROVIDER_ID:-aiif-note}"
CONTROLLER_SA_ID="${CONTROLLER_SA_ID:-github-note-draft}"
CONTROLLER_SA="${CONTROLLER_SA_ID}@${PROJECT_ID}.iam.gserviceaccount.com"

printf 'Configuring Run190 cloud controller in project %s\n' "$PROJECT_ID"
gcloud config set project "$PROJECT_ID" >/dev/null

gcloud services enable \
  compute.googleapis.com \
  iamcredentials.googleapis.com \
  sts.googleapis.com \
  --project "$PROJECT_ID"

PROJECT_NUMBER="$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')"

if ! gcloud iam service-accounts describe "$CONTROLLER_SA" --project "$PROJECT_ID" >/dev/null 2>&1; then
  gcloud iam service-accounts create "$CONTROLLER_SA_ID" \
    --project "$PROJECT_ID" \
    --display-name="AIIF note draft VM controller"
fi

# Compute Instance Admin is used only by the GitHub-controller service account. The WIF
# trust below is restricted to this one repository. It can be replaced later by a custom
# start/stop-only role after the first production validation.
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${CONTROLLER_SA}" \
  --role="roles/compute.instanceAdmin.v1" \
  --condition=None >/dev/null

if ! gcloud iam workload-identity-pools describe "$POOL_ID" \
  --project "$PROJECT_ID" --location=global >/dev/null 2>&1; then
  gcloud iam workload-identity-pools create "$POOL_ID" \
    --project "$PROJECT_ID" \
    --location=global \
    --display-name="GitHub Actions"
fi

if ! gcloud iam workload-identity-pools providers describe "$PROVIDER_ID" \
  --project "$PROJECT_ID" --location=global --workload-identity-pool="$POOL_ID" >/dev/null 2>&1; then
  gcloud iam workload-identity-pools providers create-oidc "$PROVIDER_ID" \
    --project "$PROJECT_ID" \
    --location=global \
    --workload-identity-pool="$POOL_ID" \
    --display-name="AIIF note draft GitHub" \
    --issuer-uri="https://token.actions.githubusercontent.com" \
    --attribute-mapping="google.subject=assertion.sub,attribute.repository=assertion.repository,attribute.ref=assertion.ref" \
    --attribute-condition="assertion.repository=='${REPOSITORY}'"
fi

WIF_MEMBER="principalSet://iam.googleapis.com/projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${POOL_ID}/attribute.repository/${REPOSITORY}"
gcloud iam service-accounts add-iam-policy-binding "$CONTROLLER_SA" \
  --project "$PROJECT_ID" \
  --role="roles/iam.workloadIdentityUser" \
  --member="$WIF_MEMBER" >/dev/null

STARTUP_SCRIPT="$(mktemp)"
cat >"$STARTUP_SCRIPT" <<'EOF'
#!/usr/bin/env bash
# Cost failsafe: every boot schedules a clean shutdown even if GitHub cleanup never runs.
shutdown -c >/dev/null 2>&1 || true
shutdown -h +35 'AIIF note draft VM failsafe shutdown' >/dev/null 2>&1 || true
EOF

if ! gcloud compute instances describe "$VM_NAME" --project "$PROJECT_ID" --zone "$ZONE" >/dev/null 2>&1; then
  gcloud compute instances create "$VM_NAME" \
    --project "$PROJECT_ID" \
    --zone "$ZONE" \
    --machine-type="$MACHINE_TYPE" \
    --image-family=ubuntu-2404-lts-amd64 \
    --image-project=ubuntu-os-cloud \
    --boot-disk-size=30GB \
    --boot-disk-type=pd-balanced \
    --no-service-account \
    --no-scopes \
    --metadata=enable-oslogin=TRUE \
    --metadata-from-file=startup-script="$STARTUP_SCRIPT"
else
  gcloud compute instances add-metadata "$VM_NAME" \
    --project "$PROJECT_ID" \
    --zone "$ZONE" \
    --metadata=enable-oslogin=TRUE \
    --metadata-from-file=startup-script="$STARTUP_SCRIPT"
fi
rm -f "$STARTUP_SCRIPT"

WIF_PROVIDER="projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${POOL_ID}/providers/${PROVIDER_ID}"

cat <<EOF

Run190 Google Cloud controller is ready.

Add these GitHub Repository Variables (Settings -> Secrets and variables -> Actions -> Variables):
GCP_PROJECT_ID=${PROJECT_ID}
GCP_NOTE_VM_ZONE=${ZONE}
GCP_NOTE_VM_NAME=${VM_NAME}
GCP_WORKLOAD_IDENTITY_PROVIDER=${WIF_PROVIDER}
GCP_SERVICE_ACCOUNT=${CONTROLLER_SA}

Next: start the VM once and run infra/gcp/run190_bootstrap_runner.sh inside it with a
fresh GitHub self-hosted runner registration token. The VM will auto-stop after 35 minutes.
EOF
