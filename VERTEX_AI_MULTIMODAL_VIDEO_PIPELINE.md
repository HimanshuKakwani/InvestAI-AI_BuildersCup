# Vertex AI Native Multimodal Video Ingestion & Resilient Caching Architecture

## 1. Executive Summary & Root Cause Analysis

### The Cloud Run Issue (Diagnosed)
During local testing, extracting financial securities from YouTube videos worked because the legacy scraper `youtube_transcript_api` connected from residential IP addresses. However, when deployed to **Google Cloud Run**, YouTube actively rate-limits and blocks data center IP blocks from scraping raw transcripts. Because transcripts were blocked, the Gemini audit prompt lacked the spoken dialogue and correctly rejected the input as non-financial advice.

### The Solution: Option 4 with Alternative 1 Fallback
To provide an institutional-grade, demo-ready solution for the AI Builders Cup judges, we implemented:
1. **Primary Engine (Option 4):** Google Cloud **Vertex AI Native Multimodal Video Ingestion**. Gemini directly ingests and listens to the public YouTube video stream (`video/mp4`) via Google's internal network without relying on third-party scrapers or downloading raw video files.
2. **Automated Fallback (Alternative 1):** If Vertex AI encounters quota exhaustion, stream access restrictions, or network timeouts, the system automatically falls back to **Alternative 1: Managed Transcript API (SupaData / Local Scraper)** and thumbnail analysis.
3. **Multi-Tier Video Caching:** Every analyzed video is cached persistently across three tiers:
   - **Tier 1:** High-speed in-memory LRU cache (`BoundedReportCache`).
   - **Tier 2:** Persistent Google Cloud Firestore collection (`investpi_video_cache`).
   - **Tier 3:** Local disk filesystem cache (`data/video_cache/{video_id}.json`).
4. **Enforced 5-Second Loading Delay on Cache Hits:** When serving pre-audited results from cache, the backend intentionally waits **5.0 seconds** to allow the frontend investigation loading animation and crime-scene visual effects to play seamlessly for judges.

---

## 2. Architecture & Data Flow

```
                      [ User Input: YouTube URL ]
                                  │
                                  ▼
               ┌─────────────────────────────────────┐
               │  Multi-Tier Video Cache Check       │
               │  (L1 Memory -> L2 Firestore -> L3)  │
               └──────────────────┬──────────────────┘
                                  │
                 ┌────────────────┴────────────────┐
          [ Cache HIT ]                     [ Cache MISS ]
                 │                                 │
     Enforce 5.0s UX Delay                         ▼
    ("Investigating Claim...")       ┌───────────────────────────────┐
                 │                   │  Option 4: Vertex AI Direct   │
                 │                   │  Multimodal Video Ingestion   │
                 │                   │  (Part.from_uri video stream) │
                 │                   └─────────────┬─────────────────┘
                 │                                 │
                 │                    ┌────────────┴───────────┐
                 │              [ Success ]                [ Error / 403 ]
                 │                    │                        │
                 │                    │            ┌───────────▼───────────┐
                 │                    │            │ Alternative 1:        │
                 │                    │            │ Managed Transcript API│
                 │                    │            │ (SupaData / Local)    │
                 │                    │            └───────────┬───────────┘
                 │                    │                        │
                 │                    └────────────┬───────────┘
                 │                                 ▼
                 │                   ┌───────────────────────────────┐
                 │                   │ Multi-Stock Securities Audit  │
                 │                   │ (9 Regulatory & Market Params)│
                 │                   └─────────────┬─────────────────┘
                 │                                 │
                 │                                 ▼
                 │                   ┌───────────────────────────────┐
                 │                   │ Save Result to Database Cache │
                 │                   │ (L1 Memory, L2 DB, L3 Disk)   │
                 │                   └─────────────┬─────────────────┘
                 │                                 │
                 └────────────────► ◄──────────────┘
                                    │
                                    ▼
                         [ Final Audit Verdict ]
```

---

## 3. Implementation Details

### A. Configuration ([app/config.py](file:///c:/Users/Himanshu%20Kakwani/Desktop/Himanshu%20Kakwani/AI%20Builders%20Cup/app/config.py))
New configuration toggles and environment variables:
- `USE_VERTEX_AI`: Boolean flag (`true` on GCP Cloud Run; `false` locally to use Google AI Studio API key).
- `VERTEX_PROJECT_ID`: GCP project ID (defaults to `GCP_PROJECT` or `GOOGLE_CLOUD_PROJECT`).
- `VERTEX_LOCATION`: Vertex AI compute region (e.g. `us-central1`, `asia-south1`).
- `SUPADATA_API_KEY`: Optional API key for Alternative 1 managed transcript scraping.
- `FIREBASE_VIDEO_CACHE_COLLECTION`: Firestore collection name (`investpi_video_cache`).
- `VIDEO_CACHE_DELAY_SEC`: Enforced delay duration (`5.0` seconds) when serving cached video reports.

### B. Storage & Persistent Caching ([app/data/storage.py](file:///c:/Users/Himanshu%20Kakwani/Desktop/Himanshu%20Kakwani/AI%20Builders%20Cup/app/data/storage.py))
Implemented `save_video_cache(video_id, data)` and `get_video_cache(video_id)`:
1. **L1 In-Memory:** Fast lookup in `BoundedReportCache`.
2. **L2 Firestore:** Documents stored under `investpi_video_cache/{video_id}` with timestamp and complete audit payload.
3. **L3 Local File:** Saved as JSON under `data/video_cache/{video_id}.json`.

### C. Gemini Client & Fallback Engine ([app/gemini/client.py](file:///c:/Users/Himanshu%20Kakwani/Desktop/Himanshu%20Kakwani/AI%20Builders%20Cup/app/gemini/client.py))
- **`GeminiAuditor._init_client()`:** Initializes the unified `google-genai` SDK with `vertexai=True` (using Google Application Default Credentials or Cloud Run service account) or falls back to Developer API Key (`Config.GEMINI_API_KEY`).
- **`analyze_youtube_claim()`:**
  - Passes `types.Part.from_uri(file_uri=youtube_url, mime_type="video/mp4")` to `gemini-3.1-flash-lite` or `gemini-3.8-flash`.
  - Gemini directly processes audio tracks and visual frames, identifying tickers, targets, and quotes.
  - If Vertex AI times out or encounters a permission/regional error, the method automatically catches the exception, logs `[VERTEX_AI_FALLBACK]`, and executes **Alternative 1** via `fetch_youtube_transcript()`.

### D. Orchestration & UX Preservation ([app/engine/orchestrator.py](file:///c:/Users/Himanshu%20Kakwani/Desktop/Himanshu%20Kakwani/AI%20Builders%20Cup/app/engine/orchestrator.py))
- When `run_investigation(modality="youtube_url", ...)` is called:
  - Video ID is extracted from the URL.
  - Storage is queried via `reports_cache.get_video_cache(video_id)`.
  - **On Cache Hit:** Logs `[VIDEO_CACHE_HIT]`, sleeps for `5.0` seconds, marks `"from_cache": True`, and immediately returns the stored audit.
  - **On Cache Miss:** Executes full forensic audit, saves the final result to the database cache via `reports_cache.save_video_cache(video_id, final_result)`, and logs `[VIDEO_CACHE_SAVED]`.

---

## 4. Verification & Live Test Logs

### Live Native Video Extraction (Zee Business Short `DivTA2Lz08s`)
Tested with `gemini-3.1-flash-lite` in 4.9 seconds:
```
[INFO] [VERTEX_AI_VIDEO] Ingesting video stream via model 'gemini-3.1-flash-lite'...
[INFO] [VERTEX_AI_VIDEO] Model 'gemini-3.1-flash-lite' successfully analyzed video multimodal stream!
[INFO] [GEMINI_CLAIM] Extracted 4 multi-stock claim(s): ['ADANIENT.NS', 'TRENT.NS', 'HINDZINC.NS', 'VEDL.NS']
```

### Two-Stage Cache Hit & Delay Verification
```
[INFO] [AUDIT_START] Modality: youtube_url | Payload: https://www.youtube.com/shorts/DivTA2Lz08s
[INFO] [AUDIT_FINISHED] Total stocks audited: 4 | Primary: ADANIENT.NS -> Report: rep_9e4f4a4c (CAUTION)
[INFO] [VIDEO_CACHE_SAVED] Persisted video audit for 'DivTA2Lz08s' to local disk cache.
First call duration: 17.12 s | from_cache: False

[INFO] [AUDIT_START] Modality: youtube_url | Payload: https://www.youtube.com/shorts/DivTA2Lz08s
[INFO] [VIDEO_CACHE_HIT] Retrieved video audit for 'DivTA2Lz08s' from L1 memory cache.
[INFO] [VIDEO_CACHE_HIT] Found cached audit for video 'DivTA2Lz08s'. Enforcing 5.0s loading delay for UI investigation animation...
Second call duration: 5.0 s | from_cache: True
```

### Pytest Verification
```
tests/test_agent.py::test_guardrail_blocks_out_of_scope_questions PASSED [ 20%]
tests/test_agent.py::test_in_scope_questions_allowed PASSED              [ 40%]
tests/test_agent.py::test_subagents_direct_execution PASSED              [ 60%]
tests/test_api_chat_and_subagent_endpoints PASSED                       [ 80%]
tests/test_quarterly_report_summarizer_and_swot PASSED                  [100%]
============================= 5 passed in 15.43s ==============================
```

---

## 5. What Is Needed From Your End (Cloud Run Deployment)

When you deploy this code to Google Cloud Run, please verify the following:

1. **Enable Vertex AI API on GCP:**
   - In Google Cloud Console, navigate to **APIs & Services** > **Library**.
   - Search for **Vertex AI API** (`aiplatform.googleapis.com`) and click **Enable**.
2. **Cloud Run Service Account Permissions:**
   - Ensure the service account running your Cloud Run service has the **Vertex AI User** role (`roles/aiplatform.user`) and **Cloud Datastore User** role (for Firestore access).
3. **Environment Variables on Cloud Run:**
   - `USE_VERTEX_AI`: `true`
   - `VERTEX_PROJECT_ID`: Your GCP Project ID (e.g. `investpi-451200` or whatever your project is named).
   - `VERTEX_LOCATION`: `us-central1` (recommended for general multimodal availability).
   - `GEMINI_API_KEY`: Keep your existing Gemini Developer key as a backup.
   - `SUPADATA_API_KEY`: *(Optional)* If you sign up for SupaData's free tier, add the key here as an extra transcript fallback.

> [!NOTE]
> **No Git Commits Made:** As per your explicit instructions, all modifications are strictly local. No git commits or pushes have been performed.
