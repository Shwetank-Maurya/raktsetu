#!/usr/bin/env bash
# One-time Google Cloud setup for Option B. Idempotent-ish; re-running is safe.
# Usage: PROJECT_ID=my-proj NEON_POOLED_URL=... NEON_DIRECT_URL=... ./infra/setup_gcp.sh
set -euo pipefail
: "${PROJECT_ID:?}" ; : "${NEON_POOLED_URL:?}" ; : "${NEON_DIRECT_URL:?}"
REGION="${REGION:-asia-south1}"
gcloud config set project "$PROJECT_ID"
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com \
  secretmanager.googleapis.com cloudscheduler.googleapis.com aiplatform.googleapis.com routes.googleapis.com \
  maps-backend.googleapis.com firestore.googleapis.com fcm.googleapis.com calendar-json.googleapis.com \
  bigquery.googleapis.com firebase.googleapis.com identitytoolkit.googleapis.com

put() { printf '%s' "$2" | gcloud secrets create "$1" --data-file=- 2>/dev/null || printf '%s' "$2" | gcloud secrets versions add "$1" --data-file=-; }
put DATABASE_URL "$NEON_POOLED_URL"
put DATABASE_URL_DIRECT "$NEON_DIRECT_URL"
put MAPS_SERVER_KEY "${MAPS_SERVER_KEY:-none}"
put GOOGLE_CALENDAR_API_KEY "${GOOGLE_CALENDAR_API_KEY:-none}"
put DEMO_AUTH_SECRET "$(openssl rand -hex 32)"

PN=$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')
RUN_SA="$PN-compute@developer.gserviceaccount.com"
for role in roles/aiplatform.user roles/secretmanager.secretAccessor roles/datastore.user roles/firebasecloudmessaging.admin roles/bigquery.dataEditor roles/bigquery.jobUser; do
  gcloud projects add-iam-policy-binding "$PROJECT_ID" --member="serviceAccount:$RUN_SA" --role="$role" --condition=None >/dev/null
done
gcloud firestore databases create --location="$REGION" 2>/dev/null || true
gcloud iam service-accounts create scheduler-sa --display-name="RaktSetu scheduler" 2>/dev/null || true
echo "Done. Next: ./infra/deploy.sh all  then  ./infra/scheduler.sh"
