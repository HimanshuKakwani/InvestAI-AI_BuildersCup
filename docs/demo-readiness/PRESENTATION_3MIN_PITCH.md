# InvestPI — 3-Minute Presentation & Demo Pitch Script
**Competition:** AI Builders Cup (Google Cloud & Generative AI Track)  
**Target Video Duration:** 3 Minutes (180 Seconds)  
**Scoring Alignment:** Impact (20%) · Google Tech Depth (30%) · Innovation (25%) · UX Polish (15%) · Pitch Delivery (10%)  

---

### [0:00 – 0:35] Act 1: The Problem & Core Doctrine *(Impact: 20%)*

Judges, every single day across JAPAC, millions of retail investors risk their hard-earned life savings on illegal, unregulated stock tips circulating on YouTube Shorts, Telegram VIP groups, and WhatsApp chats. Fraudulent "finfluencers" orchestrate pump-and-dump syndicates using fabricated screenshots, false urgency, and promises of guaranteed 200% returns. 

Regulators have institutional surveillance platforms like SEBI's *Sudarshan*, but everyday retail investors have had zero tools to defend themselves — until today.

Meet **InvestPI** — an autonomous securities forensic intelligence platform.

Our core doctrine is: **"Rate the Claim, Not the Stock."** We do not issue unlicensed personal buy or sell tips. Instead, we take any YouTube video, chat screenshot, forwarded text tip, or corporate PDF, and deterministically audit that specific claim against 5 years of empirical market books and official regulatory registries across India (SEBI), Singapore (MAS), and Australia (ASIC).

---

### [0:35 – 1:20] Act 2: Serverless Event Pipeline & Multimodal AI *(Google Tech Depth: 30%)*

To engineer this at production scale with sub-50ms ingestion, we built an event-driven serverless architecture on Google Cloud.

At the front door, **Google Cloud Run** serves our native, lightweight HTML5 single-page application with zero runtime Node overhead, auto-scaling from 0 to 1,000 container instances with zero idle cost. We integrated Werkzeug `ProxyFix` middleware to ensure trusted HTTPS header forwarding behind Google's edge load balancer.

Because parsing multi-minute video streams and trading charts is compute-intensive, we eliminated client-facing latency using **Google Cloud Pub/Sub**. When a tip is submitted, Cloud Run immediately registers the case in **Google Cloud Firestore** as `QUEUED`, publishes a `LeadSubmittedEvent` to `investpi-leads-inbound`, and returns an immediate `HTTP 202 Accepted` response in **under 50 milliseconds**.

Pub/Sub then dispatches the task to worker containers via an **OIDC-authenticated push subscription** (`investpi-worker-sub`) with a 300-second deadline. If five consecutive failures occur, Pub/Sub automatically isolates the payload into our **Dead-Letter Queue (`investpi-leads-dlq`)**.

Inside the worker, **Google Gemini 2.5 Flash** performs multimodal extraction: parsing YouTube audio and oEmbed metadata, performing Vision OCR on chat bubbles and price targets, and normalizing claims into structured JSON.

---

### [1:20 – 2:05] Act 3: 9-Parameter Forensic Math & BigQuery Vector RAG *(Innovation: 25%)*

Next is our core differentiator: **Zero Hallucination**. 

We do NOT allow generative AI to guess the investment risk. Instead, our deterministic Python math engine audits the claim across **9 empirical parameters**:
- **P1:** 5-year rolling return standard deviation ($z$-score).
- **P2 & P3:** Implied valuation P/E bands and trailing earnings momentum.
- **P4 & P5:** Institutional analyst consensus spread and promoter pledge dilution.
- **P6 & P7:** Regulatory debarment registries and exchange surveillance stages (ASM/GSM).
- **P8 & P9:** Official SEBI/MAS/ASIC advisor licensing and hype/urgency lexicon detection.

If any hard gate triggers — like guaranteed returns or an unlicensed tipster — the system instantly stamps the dossier as **High Risk**, capping the score at $\le 3.0 / 10$.

Now, look at our second hero capability: **Google BigQuery Vector Search RAG**. 
Users can select any equity from our marquee 10-stock universe — including Reliance, TCS, HDFC Bank, DBS Group, Singtel, and BHP. 
Under the hood, **Vertex AI `text-embedding-004`** generates 768-dimensional embeddings stored inside a partitioned BigQuery table (`quarterly_report_chunks`). Using native **`VECTOR_SEARCH` with a COSINE IVF index**, our dedicated `quarterly_report_agent` semantically retrieves balance-sheet disclosures in under 120ms — automatically generating 5 plain-English takeaways, segment-level operating margins, and an institutional **4-quadrant SWOT matrix** (Strengths, Weaknesses, Opportunities, Threats).

---

### [2:05 – 2:35] Act 4: Multi-Agent Coordination & Tamper-Evident Persistence *(UX Polish: 15%)*

Under the hood, our `SubAgentCoordinator` orchestrates **5 specialized micro-agents** in parallel:
1. `historic_price_agent` (5-Yr OHLCV & 50/200-day EMA)
2. `price_target_agent` (Institutional consensus spread)
3. `fundamentals_agent` (P/E, EPS, ROE, Debt-to-Equity)
4. `quarterly_report_agent` (BigQuery Vector RAG)
5. `explainer_agent` (Layman synthesis & disclaimers)

All case states and audit scores are sealed in **Google Cloud Firestore** (`investpi_cases`, `investpi_reports`, `investpi_prices`), enabling seamless multi-worker cache sharing. 

Clients monitor the investigation in real time via **Server-Sent Events (SSE)** (`GET /api/cases/:id/stream`), auto-transitioning the UI to the completed dossier and offering one-click download of a SHA-256 sealed **compliance PDF brief** generated via ReportLab.

---

### [2:35 – 3:00] Act 5: Guardrailed AI Assistant & Closing *(Delivery: 10%)*

Users can also interrogate their audit using our **Forensic Assistant Chat Drawer**. 
It is protected by **dual domain-boundary guardrails**: a regex pre-filter and a strict Gemini system boundary that immediately refuse personal "Should I buy or sell?" questions, keeping the dialogue 100% compliant with SEBI PFUTP regulations.

All sensitive API keys and cron secrets are managed via **Google Cloud Secret Manager** and authenticated by dedicated IAM service accounts (`investpi-pubsub-invoker`).

Best of all: this entire decoupled architecture runs natively within **Google Cloud's Always-Free Tier — operating at $0.00 a month**.

InvestPI is fast, deterministic, and regulatory-immune. We are giving everyday retail investors the institutional defense shield they deserve. 

Thank you!
