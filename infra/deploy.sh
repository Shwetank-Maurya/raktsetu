#!/usr/bin/env bash
# Option B (full Google stack): Cloud Run API + Firebase Hosting SPA. Requires a billing-enabled project.
# Usage: PROJECT_ID=my-proj REGION=asia-south1 ./infra/deploy.sh [api|web|all|rollback REVISION]
set -euo pipefail
: "${PROJECT_ID:?set PROJECT_ID}"
REGION="${REGION:-asia-south1}"
SERVICE=raktsetu-api
cd "$(dirname "$0")/.."

api() {
  gcloud run deploy "$SERVICE" --project "$PROJECT_ID" --region "$REGION" --source ./backend \
    --allow-unauthenticated --min-instances=1 --max-instances=4 --memory=2Gi --cpu=2 --timeout=900 \
    --set-secrets=DATABASE_URL=DATABASE_URL:latest,DATABASE_URL_DIRECT=DATABASE_URL_DIRECT:latest,MAPS_SERVER_KEY=MAPS_SERVER_KEY:latest,DEMO_AUTH_SECRET=DEMO_AUTH_SECRET:latest,GOOGLE_CALENDAR_API_KEY=GOOGLE_CALENDAR_API_KEY:latest \
    --set-env-vars="ENV=prod,RUN_MIGRATIONS=true,GOOGLE_GENAI_USE_VERTEXAI=true,GOOGLE_CLOUD_PROJECT=$PROJECT_ID,GOOGLE_CLOUD_LOCATION=global,GEMINI_MODEL=gemini-3.7-flash,GEMINI_MODEL_LITE=gemini-3.5-flash-lite,FIREBASE_PROJECT_ID=$PROJECT_ID,FIRESTORE_ENABLED=true,FCM_ENABLED=true,BIGQUERY_DATASET=raktsetu,SCHEDULER_SA_EMAIL=scheduler-sa@$PROJECT_ID.iam.gserviceaccount.com"
  URL=$(gcloud run services describe "$SERVICE" --project "$PROJECT_ID" --region "$REGION" --format='value(status.url)')
  gcloud run services update "$SERVICE" --project "$PROJECT_ID" --region "$REGION" --update-env-vars="INTERNAL_AUDIENCE=$URL" >/dev/null
  echo "API: $URL"
}

web() {
  (cd frontend && npm ci && npm run build)
  (cd infra && firebase deploy --only hosting,firestore:rules --project "$PROJECT_ID")
}

case "${1:-all}" in
  api) api ;;
  web) web ;;
  all) api; web ;;
  rollback) gcloud run services update-traffic "$SERVICE" --project "$PROJECT_ID" --region "$REGION" --to-revisions="${2:?revision}=100" ;;
  *) echo "usage: $0 [api|web|all|rollback REVISION]"; exit 1 ;;
esac
