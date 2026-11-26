# Deployment

One Docker image (`backend/Dockerfile`) and one static build (`frontend/dist`) serve both options.
Pick **B** if a billing card is available (full Google stack, shorter cold starts), else **A**.

## Common: Neon + Firebase (both free, no card)
1. Neon: create project (region near Mumbai/Singapore). Copy the **pooled** URL (host contains `-pooler`)
   and the **direct** URL. PostGIS is not required.
2. Firebase console: create project; enable Authentication (Email/Password + Google), Firestore, Hosting;
   register a web app and copy its config into `frontend/.env` (`VITE_FIREBASE_*`).
3. Migrate + seed from your machine: `DATABASE_URL_DIRECT=<direct> DATABASE_URL=<direct> make migrate seed replay`.
4. Gemini: AI Studio key (`GEMINI_API_KEY`) for A; Vertex AI via ADC for B.
5. Optional: Calendar API key (public holidays), BigQuery sandbox dataset `raktsetu` + Looker Studio report on `risk_snapshots`.
6. Demo users with role claims: `FIREBASE_PROJECT_ID=... GOOGLE_APPLICATION_CREDENTIALS=sa.json python -m scripts.set_claims`.

## Option B - full Google (Cloud Run + Firebase Hosting)
```bash
export PROJECT_ID=... REGION=asia-south1
NEON_POOLED_URL=... NEON_DIRECT_URL=... MAPS_SERVER_KEY=... GOOGLE_CALENDAR_API_KEY=... ./infra/setup_gcp.sh
./infra/deploy.sh all          # Cloud Run (min 1 instance, 2 vCPU/2 GiB) + Hosting with /api/** rewrite
./infra/scheduler.sh           # hourly run-cycle + world-tick via OIDC
cd backend && python -m scripts.smoke https://$PROJECT_ID.web.app
```
Maps: two keys - browser key (HTTP-referrer restricted, Maps JavaScript API) -> `VITE_MAPS_BROWSER_KEY`
(+ a Map ID for Advanced Markers in `VITE_MAPS_MAP_ID`); server key (Routes API only) -> Secret Manager.
Set a billing budget alert. CI/CD: connect `infra/cloudbuild.yaml` as a Cloud Build trigger, or use
GitHub Actions. Rollback: `./infra/deploy.sh rollback <revision>`.

## Option A - no card (Render + Firebase Hosting Spark)
1. Render: New Blueprint from `infra/render.yaml` (or a Docker web service, root `backend`). Set
   `DATABASE_URL` (pooled), `DATABASE_URL_DIRECT`, `GEMINI_API_KEY`, `FIREBASE_PROJECT_ID`,
   `CORS_ORIGINS=https://<project>.web.app`.
2. Frontend: `VITE_API_BASE=https://<render-app>.onrender.com npm run build`; then
   `cd infra && firebase deploy --only hosting,firestore:rules` (remove the `/api/**` rewrite in
   `firebase.json` for this option - Hosting on Spark cannot proxy to Render).
3. Scheduler: GitHub repo variable `API_URL` + secret `INTERNAL_TOKEN` (same as Render's) enables `.github/workflows/cycle.yml`.
4. Firestore/FCM from Render need a service-account JSON (`GOOGLE_APPLICATION_CREDENTIALS`) - optional; polling works without.
Render free instances sleep after inactivity: run the smoke script before demoing.
