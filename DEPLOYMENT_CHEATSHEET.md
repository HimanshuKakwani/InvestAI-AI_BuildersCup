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

Whenever you make updates to your Python files, frontend, or dependencies, run this command from the project root:

```bash
gcloud run deploy investpi-service --source . --region us-central1
```

> **What this does:** Cloud Build automatically packages your new code into a fresh container image, deploys a new revision, and routes 100% of traffic to it with zero downtime.

---

## 2. Stop the Deployment (Stop the App on Server)

To stop serving traffic and completely remove the running service:

```bash
gcloud run services delete investpi-service --region us-central1 --quiet
```

> **Important:** This **does NOT delete your GCP project**. Your Firestore database, secrets in Secret Manager, IAM permissions, and billing remain 100% intact and safe.

---

## 3. Start / Redeploy the App Again

To bring the app back online after stopping it, run the full deploy command:

```bash
gcloud run deploy investpi-service \
  --source . \
  --region us-central1 \
  --platform managed \
  --allow-unauthenticated \
  --memory 1Gi \
  --cpu 1 \
  --set-secrets="GEMINI_API_KEY=GEMINI_API_KEY:latest" \
  --set-env-vars="DEMO_MODE=0,FLASK_DEBUG=0,USE_FIREBASE=1,FIREBASE_COLLECTION=investpi_reports"
```

---

## 4. How to Add a New Secret in the Future

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
