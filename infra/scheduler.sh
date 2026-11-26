#!/usr/bin/env bash
# Cloud Scheduler: hourly forecast/risk/plan cycle with a Google-signed OIDC token (verified in code).
# Free tier covers 3 jobs per billing account.
set -euo pipefail
: "${PROJECT_ID:?}"
REGION="${REGION:-asia-south1}"
URL=$(gcloud run services describe raktsetu-api --project "$PROJECT_ID" --region "$REGION" --format='value(status.url)')
SA="scheduler-sa@$PROJECT_ID.iam.gserviceaccount.com"
gcloud run services add-iam-policy-binding raktsetu-api --region "$REGION" --member="serviceAccount:$SA" --role=roles/run.invoker >/dev/null
for job in "run-cycle|0 * * * *|/internal/jobs/run-cycle" "world-tick|30 * * * *|/internal/jobs/world-tick?hours=1"; do
  IFS='|' read -r NAME CRON PATH_ <<<"$job"
  gcloud scheduler jobs delete "$NAME" --location="$REGION" --quiet 2>/dev/null || true
  gcloud scheduler jobs create http "$NAME" --location="$REGION" --schedule="$CRON" --time-zone="Asia/Kolkata" \
    --http-method=POST --uri="$URL$PATH_" --attempt-deadline=900s \
    --oidc-service-account-email="$SA" --oidc-token-audience="$URL"
done
echo "Scheduled run-cycle (hourly) and world-tick (demo world, hourly) against $URL"
