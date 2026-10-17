# InvestPI Cloud Deployment & Google Cloud $300 Free Trial Guide

This guide details the exact step-by-step roadmap to deploy **InvestPI** to Google Cloud Run with **Google Cloud Secret Manager** for zero-exposure API key protection, along with a comprehensive cost breakdown explaining how your **$300 / 90-Day Google Cloud Free Trial** will be consumed and how to obtain your live application URL.

> [!TIP]
> **Related Architecture Documents**:
> - **[DEPLOYMENT_READINESS_AUDIT.md](file:///Users/chawadesharvari17gmail.com/Desktop/projects/InvestAI-AI_BuildersCup/DEPLOYMENT_READINESS_AUDIT.md)**: Production code audit with recommended code fixes before deploying.
> - **[COST_OPTIMIZATION_ANALYSIS.md](file:///Users/chawadesharvari17gmail.com/Desktop/projects/InvestAI-AI_BuildersCup/COST_OPTIMIZATION_ANALYSIS.md)**: Strategies for in-memory token/secret caching, image downsampling, and Cloud Run scaling caps.

---

## 1. How the $300 Free Trial Credit Is Consumed (Cost Breakdown)

If you deploy InvestPI today, **you will consume almost none of your $300 credit**. Under typical hackathon, testing, and demo conditions, the total cost over 90 days will be **less than $1.00 to $2.00**, leaving 99%+ of your credits completely intact.

### Why It Costs Virtually $0:

```
+-----------------------------------------------------------------------------------------------+
| Component              | Free Tier Allowance (Every Month)             | Expected Cost        |
+-----------------------------------------------------------------------------------------------+
| Cloud Run (Compute)    | 2,000,000 requests/month                      | $0.00 (Scales to 0)  |
|                        | 360,000 GB-seconds memory                     |                      |
|                        | 180,000 vCPU-seconds                          |                      |
| Secret Manager         | 6 active secret versions free                 | $0.00 (1 secret used)|
|                        | 10,000 access operations/month free           |                      |
| Firebase / Firestore   | 1 GiB storage, 50k reads/day, 20k writes/day   | $0.00 (Spark Tier)   |
| Cloud Build (Deploy)   | 120 build-minutes per day                     | $0.00 (~2 min/build) |
| Artifact Registry      | 0.5 GB storage per month                      | ~$0.02 - $0.05/month |
| Gemini API (AI Studio) | 15 Requests/Min, 1,500 Requests/Day           | $0.00 (Zero-cost tier)|
| Network Egress         | 1 GB outbound data to North America           | $0.00                |
+-----------------------------------------------------------------------------------------------+
```

### Detailed Factor Breakdown:

1. **Cloud Run Scales to Zero (No Idle Billing)**:
   - Traditional servers (like Compute Engine or standard VMs) charge by the hour simply for being turned on, even with zero visitors.
   - Cloud Run is **serverless**: when nobody is using the site, container instances shut down to **zero (0)**. You pay **$0.00** for idle time.
   - When a user visits, Cloud Run spins up an instance in ~1–2 seconds, processes the request, and spins back down.
   - Cloud Run's monthly Always-Free allowance includes **2 million requests**, **360,000 GB-seconds of RAM**, and **180,000 vCPU-seconds**. At 1 GB RAM, that equals 100 hours of continuous active request processing per month for free.

2. **Secret Manager (Enterprise Security at $0 Cost)**:
   - Secret Manager stores sensitive credentials (like `GEMINI_API_KEY`) encrypted at rest with Google-managed encryption keys.
   - Google gives **6 active secret versions free every month** and **10,000 free access calls**. InvestPI uses exactly 1 secret (`GEMINI_API_KEY`), meaning your Secret Manager cost is **$0.00**.

3. **Firebase / Firestore (Multi-Instance Persistent Storage at $0 Cost)**:
   - Cloud Run instances scale down to 0 when idle and scale out to multiple containers under concurrent traffic.
   - By integrating **Firebase Firestore** as an L2 persistence layer behind an in-memory L1 cache, audit reports and PDF downloads persist permanently across container restarts and can be retrieved by any Cloud Run instance.
   - The Firebase Spark Plan gives **1 GiB storage, 50,000 document reads/day, and 20,000 document writes/day for $0.00/month**. Under demo and hackathon usage, 100% of Firestore usage falls completely within the Always-Free tier.

4. **Cloud Build (Container Building)**:
   - When you execute `gcloud run deploy --source .`, Google Cloud Build compiles your container image.
   - Google gives **120 free build-minutes every day**. Building InvestPI takes ~90 seconds. You could redeploy 50+ times in a single day without paying anything.

5. **Google AI Studio (Gemini 2.5 / 1.5 Flash API)**:
   - By obtaining your API key from [aistudio.google.com](https://aistudio.google.com), all LLM forensic calls run under the **Developer Free Tier** (15 RPM / 1,500 requests/day).
   - This API tier is completely free and **does not deduct a single cent** from your $300 GCP credit.

6. **Container Storage (Artifact Registry)**:
   - Each build saves a Docker image in Artifact Registry.
   - The first 0.5 GB per month is free; beyond that, storage costs ~$0.10 per GB per month. Even storing 2–3 image revisions will cost only pennies (~$0.05).

### Google Cloud Safety Guarantee:
- Google Cloud **never automatically charges your credit/debit card** when the $300 credit is exhausted or when the 90 days expire.
- If credits expire or are depleted, services simply pause until you explicitly click **Upgrade to a paid account** in the Google Cloud Console.

---

## 2. Prerequisites & Current Account Status

### Initial CLI Setup (if starting on a fresh machine):

**macOS:**
```bash
# Install Google Cloud SDK via Homebrew
brew install --cask google-cloud-sdk

# Authenticate with your Google Cloud account
gcloud auth login
```

**Windows:**
```powershell
# Install Google Cloud SDK via Windows Package Manager (PowerShell / Command Prompt)
winget install Google.CloudSDK

# Or download the official installer:
# https://dl.google.com/dl/cloudsdk/channels/rapid/GoogleCloudSDKInstaller.exe

# Open a NEW PowerShell window and authenticate
gcloud auth login
```

### Audited state of your environment:
- **Authenticated Account**: `himanshukakwani14@gmail.com`
- **Active Billing Account ID**: `014373-1D99E4-9DAB78` (`My Billing Account`)
- **Codebase State**: Flask web app with ReportLab PDF generator, Swagger UI (`/apidocs/`), and 9-parameter engine is ready.
- **Created Deployment Files**:
  - `requirements.txt` (Pinned dependencies + Gunicorn)
  - `Dockerfile` (Python 3.11-slim + font rendering + Gunicorn WSGI)
  - `.dockerignore` (Ignores tests, local caches, git)

---

## 3. How You Will Get Your Application URL

Once deployed, Google Cloud Run automatically assigns a globally unique, high-availability HTTPS URL with an automated SSL/TLS certificate.

### 1. Terminal Output at Deployment Finish:
When your deployment finishes, the terminal automatically prints the live URL:
```text
Building using Buildpacks and deploying container to Cloud Run service [investpi-service] in project [your-project-id] region [us-central1]
✓ Deploying... Done.
✓ Creating Revision...
✓ Routing traffic...
✓ Setting IAM Policy...
Done.
Service [investpi-service] revision [investpi-service-00001-abc] has been deployed and is serving 100 percent of traffic.
Service URL: https://investpi-service-432906686909.us-central1.run.app
```

### 2. Retrieve URL Anytime via CLI:
If you close your terminal or forget the URL, run this command anytime:
```bash
gcloud run services describe investpi-service --region us-central1 --format='value(status.url)'
```

### 3. Google Cloud Web Console:
You can also view and click the URL directly in your browser:
Navigate to [https://console.cloud.google.com/run](https://console.cloud.google.com/run) and click on `investpi-service`.

### 4. Custom Domain (Optional):
If you have a custom domain name (e.g. `audit.investpi.org`), Cloud Run allows one-click domain mapping with free automatic SSL certificates:
```bash
gcloud beta run domain-mappings create --service investpi-service --domain audit.investpi.org --region us-central1
```

---

## 4. Phase 1: GCP Project & Infrastructure Setup

Run these commands in your local terminal:

### Step 1.1: Create Dedicated Project
```bash
# Generate a unique project ID
export PROJECT_ID="investpi-builderscup-$(date +%s | tail -c 5)"

# Create project
gcloud projects create $PROJECT_ID --name="InvestPI Core"
```

### Step 1.2: Link to Your Free Trial Billing Account
```bash
# Link the project to your active billing account
gcloud billing projects link $PROJECT_ID --billing-account="014373-1D99E4-9DAB78"
```

### Step 1.3: Set Default Project and Region
Lock region to `us-central1` for permanent Free Tier compute:
```bash
gcloud config set project $PROJECT_ID
gcloud config set run/region us-central1
```

### Step 1.4: Enable Required Google Cloud Services
Enable Cloud Run, Cloud Build, Artifact Registry, Secret Manager, and Cloud Firestore:
```bash
gcloud services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com \
  secretmanager.googleapis.com \
  firestore.googleapis.com
```

### Step 1.5: Initialize Firebase Firestore Database (Native Mode)
Create your Firestore database in `us-central1` (eligible for the permanent Spark Free Tier):
```bash
gcloud firestore databases create --location=us-central1 --type=firestore-native
```

---

## 5. Phase 2: Secret Manager & IAM Configuration

Store your Gemini API Key securely so it is never exposed in git, build logs, or container layers, and grant Cloud Run permissions to both Secret Manager and Firestore.

### Step 2.1: Create the Secret
```bash
gcloud secrets create GEMINI_API_KEY --replication-policy="automatic"
```

### Step 2.2: Add Your Gemini API Key
Replace `AIzaSy...` with your actual key from Google AI Studio:
```bash
echo -n "AIzaSyYOUR_ACTUAL_API_KEY_HERE" | gcloud secrets versions add GEMINI_API_KEY --data-file=-
```

### Step 2.3: Grant Cloud Run Access to Secret Manager
Cloud Run runs under the default Compute Engine service account. Grant it permission to read the secret:
```bash
# Fetch your numeric Project Number
export PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format='value(projectNumber)')

# Grant the secretAccessor role
gcloud secrets add-iam-policy-binding GEMINI_API_KEY \
    --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
    --role="roles/secretmanager.secretAccessor"
```

### Step 2.4: Grant Cloud Run Access to Firebase Firestore
Grant the service account permission to read and write audit records to Firestore using Application Default Credentials (ADC), requiring zero JSON key files:
```bash
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
    --role="roles/datastore.user"
```

---

## 6. Phase 3: Deploy to Cloud Run with Secret Manager & Firebase

Run this single command from your project root (`InvestAI-AI_BuildersCup`):

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

### How Secret Manager & Firebase Work with the Code:
- **Secret Manager**: Cloud Run fetches `GEMINI_API_KEY` directly from Secret Manager at container startup and injects it into `os.environ["GEMINI_API_KEY"]`. Zero secret exposure in code or git.
- **Firebase Firestore**: InvestPI connects to Firestore using Google Cloud Application Default Credentials automatically. Audit reports, extracted claims, and scores are stored in the collection `investpi_reports`.
- **Hybrid Storage**: Fast requests read from the in-memory L1 cache (`BoundedReportCache`). If an instance restarts or scales down to zero, reports are transparently retrieved from Firestore, ensuring users can always download their PDF reports even days later.
- **Result**: Zero secret exposure, fully persistent cross-instance storage, 100% within the free tier.

---

## 7. What You Get Once Deployed

Once deployed, you can access all features through your Cloud Run URL (`https://<service-url>`):

1. **Interactive Web Dashboard**: `https://<service-url>/`
   - Form for YouTube URLs, screenshot uploads, and direct text claims.
   - Real-time audit scoring with traffic-light verdicts (Green, Caution, High Risk).
2. **Interactive Swagger/OpenAPI Docs**: `https://<service-url>/apidocs/`
   - Test endpoints interactively directly from the browser (protected against Mixed Content via `ProxyFix`).
3. **System Health Check**: `https://<service-url>/healthz`
   - Verifies container runtime, demo mode status, and Firebase Firestore connectivity (`"firebase_connected": true`).
4. **Persistent Instant Forensic PDF Downloads**: `https://<service-url>/api/report/<report_id>.pdf`
   - Generates multi-page institutional-grade forensic audit reports retrieved from memory or Firebase Firestore.

---


## 8. Operational & Cost Management FAQ

- **Q: How do I verify the live URL from the command line?**
  ```bash
  gcloud run services describe investpi-service --region us-central1 --format='value(status.url)'
  ```
- **Q: How do I view live application logs in real-time?**
  ```bash
  gcloud run services logs tail investpi-service --region us-central1
  ```
- **Q: How do I update the API key in the future without redeploying code?**
  Simply add a new version to the secret:
  ```bash
  echo -n "NEW_API_KEY" | gcloud secrets versions add GEMINI_API_KEY --data-file=-
  ```
  Cloud Run automatically picks up the latest version on next container startup.
- **Q: How do I stop or delete the service if I want to turn it off?**
  ```bash
  gcloud run services delete investpi-service --region us-central1 --quiet
  ```
