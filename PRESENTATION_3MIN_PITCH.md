# InvestPI — 3-Minute Presentation Writeup

### [0:00 – 0:45] The Problem & The Use Case

Judges, every day across JAPAC, millions of retail investors risk their hard-earned life savings on unregulated stock tips circulating on YouTube, Telegram, and WhatsApp. Fraudulent "finfluencers" orchestrate pump-and-dump scams using false urgency, fake screenshots, and claims of guaranteed returns. Regulators have institutional surveillance systems like SEBI's *Sudarshan*, but everyday retail investors have zero tools to defend themselves.

That is why we built **InvestPI** — an AI-powered forensic due-diligence platform.

Our core doctrine is: **"Rate the Claim, Not the Stock."** We do not issue unlicensed buy/sell advice. Instead, we take any YouTube video, chat screenshot, or text tip, and deterministically audit that specific claim against 5 years of empirical market data and official regulatory registries across India, Singapore, and Australia.

---

### [0:45 – 1:45] Decoupled Core: Google Cloud Run & Cloud Pub/Sub

To engineer this at production scale, we built an event-driven, serverless pipeline on Google Cloud.

At the front door, **Google Cloud Run** hosts our containerized Flask application. It directly serves our native, lightweight HTML5 and JavaScript single-page UI with zero runtime Node overhead, auto-scaling from 0 to 1,000 instances with zero idle costs. We integrated Werkzeug `ProxyFix` middleware to ensure seamless HTTPS header forwarding behind Google's edge load balancer.

Because parsing a multi-minute video or complex trading chart is compute-heavy, we eliminated user-facing latency using **Google Cloud Pub/Sub**. When a user drops a tip, Cloud Run registers the case in Firestore as `QUEUED`, publishes a `LeadSubmittedEvent` to our inbound topic (`investpi-leads-inbound`), and returns an immediate `HTTP 202 Accepted` response in **under 50 milliseconds**.

Pub/Sub then pushes the task to worker instances via an **OIDC-authenticated push subscription** (`investpi-worker-sub`) with a 300-second deadline. If an invalid or poisoned payload causes five consecutive failures, Pub/Sub automatically routes it to our **Dead-Letter Queue (`investpi-leads-dlq`)**, preventing worker starvation.

---

### [1:45 – 2:30] Multimodal AI, Deterministic Math & Persistence

Inside the worker, **Google Gemini 2.5 Flash** performs multimodal extraction: parsing YouTube audio and video titles via the YouTube oEmbed API, executing Vision OCR across chat bubbles, and structuring claims into precise JSON payloads.

Our deterministic Python engine audits these claims across **9 forensic parameters** — including price-move standard deviations, implied forward P/E bands, promoter pledge ratios, exchange surveillance stages, and debarred director registries. If any hard gate triggers — like guaranteed return claims or banned entities — the system instantly flags it as **High Risk**.

For state persistence across serverless container restarts, we rely on **Google Firebase Firestore**. Firestore acts as our multi-instance L2 store for case lifecycles (`investpi_cases`), 5-year price series (`investpi_prices`), and audit scorecards (`investpi_reports`), allowing users to generate a report on Worker A and stream live Server-Sent Events or download high-res PDF briefs from Worker B.

To keep our market data perpetually fresh, **Google Cloud Scheduler** dispatches time-locked EOD webhooks authenticated with secret headers post market-close for India, Singapore, and Australia.

---

### [2:30 – 3:00] Guardrailed Agent, Security & Closing

Users can also cross-examine their audit using our **Forensic Assistant Agent**, powered by Gemini with strict domain-boundary guardrails that reject out-of-scope queries.

All sensitive API keys and cron secrets are securely injected at runtime via **Google Cloud Secret Manager**, authenticated by dedicated **Google Cloud IAM** service accounts (`investpi-pubsub-invoker`).

Best of all, this entire architecture fits completely within Google Cloud's **Always-Free Tier — operating at $0.00 a month**.

InvestPI is fast, deterministic, and regulatory-immune. We are giving retail investors the institutional shield they deserve. Thank you!
