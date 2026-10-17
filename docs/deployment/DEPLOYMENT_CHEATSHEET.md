# InvestPI Cloud Run Operations Cheat Sheet

Quick reference for managing the deployment of **`investpi-service`** on Google Cloud Run.

---

## 0. First-Time Setup (Prerequisites)

If setting up on a new machine or starting from scratch:

### For macOS:
```bash
# 1. Install Google Cloud SDK via Homebrew
brew install --cask google-cloud-sdk

# 2. Log in with your Google account
gcloud auth login

# 3. Set your active project and region
gcloud config set project investpi-builderscup-0000
gcloud config set run/region us-central1
```

### For Windows:
```powershell
# 1. Install Google Cloud SDK via Windows Package Manager (PowerShell / Command Prompt)
winget install Google.CloudSDK

# Alternatively, download the official installer:
# https://dl.google.com/dl/cloudsdk/channels/rapid/GoogleCloudSDKInstaller.exe

# 2. Open a NEW PowerShell window and log in
gcloud auth login

# 3. Set your active project and region
gcloud config set project investpi-builderscup-0000
gcloud config set run/region us-central1
```

---

## 1. Trigger a New Build (After Code Changes)

Whenever you make updates to your Python files, frontend, or dependencies, deploy using the full production command:

```bash
export PROJECT_ID="investpi-builderscup-0000"
export REGION="us-central1"
export SERVICE_NAME="investpi-service"

gcloud run deploy $SERVICE_NAME \
  --source . \
  --region=$REGION \
  --platform managed \
  --allow-unauthenticated \
  --memory 1Gi \
  --cpu 1 \
  --timeout 300 \
  --set-env-vars="GCP_PROJECT_ID=${PROJECT_ID},GEMINI_MODEL=gemini-3.1-flash-lite,DEMO_MODE=0,PUBSUB_TOPIC_LEADS=investpi-leads-inbound,PUBSUB_TOPIC_AUDITS=investpi-audits-completed,PUBSUB_TOPIC_SYNC=investpi-market-sync,USE_FIREBASE=1,FIREBASE_PROJECT_ID=${PROJECT_ID},FIREBASE_COLLECTION=investpi_reports" \
  --set-secrets="GEMINI_API_KEY=GEMINI_API_KEY:latest"
```

> **What this does:** Cloud Build packages your latest code into a fresh container image, mounts the `GEMINI_API_KEY` from Secret Manager, connects Firestore and Pub/Sub topics, deploys a new revision, and routes 100% of traffic to it with zero downtime.

---

## 2. Stop the Deployment (Stop the App on Server)

To stop serving traffic and completely remove the running service:

```bash
gcloud run services delete investpi-service --region us-central1 --quiet
```

> **Important:** This **does NOT delete your GCP project**. Your Firestore database, Pub/Sub topics, secrets in Secret Manager, IAM permissions, and billing remain 100% intact and safe.

---

## 3. Check Live Environment Variables & Secrets in Cloud Run

To verify the active environment variables and secrets configured on the running service without opening the browser:

```bash
gcloud run services describe investpi-service \
  --region us-central1 \
  --format="yaml(spec.template.spec.containers[0].env)"
```

---

## 4. Start / Redeploy the App Again

To bring the app back online after stopping it, run:

```bash
export PROJECT_ID="investpi-builderscup-0000"
export REGION="us-central1"
export SERVICE_NAME="investpi-service"

gcloud run deploy $SERVICE_NAME \
  --source . \
  --region=$REGION \
  --platform managed \
  --allow-unauthenticated \
  --memory 1Gi \
  --cpu 1 \
  --timeout 300 \
  --set-env-vars="GCP_PROJECT_ID=${PROJECT_ID},GEMINI_MODEL=gemini-3.1-flash-lite,DEMO_MODE=0,PUBSUB_TOPIC_LEADS=investpi-leads-inbound,PUBSUB_TOPIC_AUDITS=investpi-audits-completed,PUBSUB_TOPIC_SYNC=investpi-market-sync,USE_FIREBASE=1,FIREBASE_PROJECT_ID=${PROJECT_ID},FIREBASE_COLLECTION=investpi_reports" \
  --set-secrets="GEMINI_API_KEY=GEMINI_API_KEY:latest"
```

---

## 5. How to Add a New Secret in the Future

### Step A: Create the secret with its value
```bash
echo -n "YOUR_SECRET_VALUE" | gcloud secrets create NEW_SECRET_NAME --data-file=-
```

### Step B: Grant Cloud Run permission to read it
```bash
export PROJECT_NUMBER=$(gcloud projects describe $(gcloud config get-value project) --format='value(projectNumber)')

gcloud secrets add-iam-policy-binding NEW_SECRET_NAME \
  --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"
```

### Step C: Attach the secret to your Cloud Run service
```bash
gcloud run services update investpi-service \
  --region us-central1 \
  --update-secrets="NEW_SECRET_NAME=NEW_SECRET_NAME:latest"
```

---

## 6. Pub/Sub Setup & Push Subscriptions (If Recreating)

If Pub/Sub topics or push subscriptions ever need to be recreated from scratch:

```bash
export PROJECT_ID="investpi-builderscup-0000"
export REGION="us-central1"
export SERVICE_ACCOUNT="investpi-pubsub-invoker@${PROJECT_ID}.iam.gserviceaccount.com"
export CLOUD_RUN_URL=$(gcloud run services describe investpi-service --region=$REGION --format='value(status.url)')

# 1. Create Topics
gcloud pubsub topics create investpi-leads-inbound
gcloud pubsub topics create investpi-audits-completed
gcloud pubsub topics create investpi-market-sync
gcloud pubsub topics create investpi-leads-dlq

# 2. Dead-Letter Queue Subscription
gcloud pubsub subscriptions create investpi-leads-dlq-sub --topic=investpi-leads-dlq

# 3. Worker Push Subscription (Audits)
gcloud pubsub subscriptions create investpi-worker-sub \
  --topic=investpi-leads-inbound \
  --push-endpoint="${CLOUD_RUN_URL}/api/pubsub/push" \
  --push-auth-service-account="${SERVICE_ACCOUNT}" \
  --ack-deadline=300 \
  --dead-letter-topic=investpi-leads-dlq \
  --max-delivery-attempts=5

# 4. Market-Close Sync Push Subscription
gcloud pubsub subscriptions create investpi-sync-sub \
  --topic=investpi-market-sync \
  --push-endpoint="${CLOUD_RUN_URL}/api/pubsub/push" \
  --push-auth-service-account="${SERVICE_ACCOUNT}" \
  --ack-deadline=300
```
