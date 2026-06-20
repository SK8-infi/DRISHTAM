#!/usr/bin/env bash
# ────────────────────────────────────────────────────────────────
# DRISHTAM — Deploy to Google Cloud Run
# Deploys both the FastAPI backend and Next.js dashboard.
# ────────────────────────────────────────────────────────────────
set -euo pipefail

# ── Configuration ──────────────────────────────────────────────
PROJECT_ID="${GCP_PROJECT_ID:-$(gcloud config get-value project 2>/dev/null)}"
REGION="${GCP_REGION:-asia-south1}"  # Mumbai — closest to Bengaluru
API_SERVICE="drishtam-api"
DASHBOARD_SERVICE="drishtam-dashboard"

echo "╔════════════════════════════════════════════════════════════╗"
echo "║           DRISHTAM — Cloud Run Deployment                ║"
echo "╠════════════════════════════════════════════════════════════╣"
echo "║  Project:   $PROJECT_ID"
echo "║  Region:    $REGION"
echo "║  Backend:   $API_SERVICE"
echo "║  Frontend:  $DASHBOARD_SERVICE"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

# ── Step 1: Deploy Backend API ─────────────────────────────────
echo "▶ [1/3] Building and deploying backend API..."

gcloud run deploy "$API_SERVICE" \
  --source . \
  --project "$PROJECT_ID" \
  --region "$REGION" \
  --platform managed \
  --allow-unauthenticated \
  --dockerfile Dockerfile.api \
  --memory 4Gi \
  --cpu 2 \
  --timeout 300 \
  --concurrency 80 \
  --min-instances 0 \
  --max-instances 3 \
  --cpu-boost \
  --set-env-vars "DRISHTAM_ENV=production,DRISHTAM_ALLOWED_ORIGINS=*,DRISHTAM_RATE_LIMIT=300" \
  --quiet

# Get the backend URL
API_URL=$(gcloud run services describe "$API_SERVICE" \
  --project "$PROJECT_ID" \
  --region "$REGION" \
  --format "value(status.url)")

echo "✅ Backend deployed: $API_URL"
echo ""

# ── Step 2: Deploy Frontend Dashboard ──────────────────────────
echo "▶ [2/3] Building and deploying frontend dashboard..."

cd dashboard

gcloud run deploy "$DASHBOARD_SERVICE" \
  --source . \
  --project "$PROJECT_ID" \
  --region "$REGION" \
  --platform managed \
  --allow-unauthenticated \
  --memory 512Mi \
  --cpu 1 \
  --timeout 60 \
  --concurrency 200 \
  --min-instances 0 \
  --max-instances 3 \
  --cpu-boost \
  --build-arg "NEXT_PUBLIC_API_URL=$API_URL" \
  --set-env-vars "NODE_ENV=production,NEXT_PUBLIC_API_URL=$API_URL" \
  --quiet

cd ..

DASHBOARD_URL=$(gcloud run services describe "$DASHBOARD_SERVICE" \
  --project "$PROJECT_ID" \
  --region "$REGION" \
  --format "value(status.url)")

echo "✅ Dashboard deployed: $DASHBOARD_URL"
echo ""

# ── Step 3: Update CORS on backend ────────────────────────────
echo "▶ [3/3] Updating backend CORS to allow dashboard origin..."

gcloud run services update "$API_SERVICE" \
  --project "$PROJECT_ID" \
  --region "$REGION" \
  --update-env-vars "DRISHTAM_ALLOWED_ORIGINS=$DASHBOARD_URL,http://localhost:3000" \
  --quiet

echo ""
echo "╔════════════════════════════════════════════════════════════╗"
echo "║                  ✅ Deployment Complete!                  ║"
echo "╠════════════════════════════════════════════════════════════╣"
echo "║  Dashboard:  $DASHBOARD_URL"
echo "║  API:        $API_URL"
echo "║  Health:     $API_URL/health"
echo "╚════════════════════════════════════════════════════════════╝"
