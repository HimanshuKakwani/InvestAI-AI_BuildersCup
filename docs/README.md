<p align="center">
  <img src="../logos/investpi_logo.png" alt="InvestPI Logo" width="110" />
</p>

# InvestPI Documentation Hub

Welcome to the **InvestPI** technical documentation directory. This repository contains the complete architectural, algorithmic, deployment, and evaluation records for the InvestPI Securities Forensic Intelligence Platform.

---

## 📚 Master Technical Specification

- **[TECHNICAL_DOCUMENTATION.md](file:///Users/chawadesharvari17gmail.com/Desktop/projects/InvestAI-AI_BuildersCup/docs/TECHNICAL_DOCUMENTATION.md)**  
  *The authoritative, unified technical reference manual for the entire codebase.* Covers end-to-end multi-tier architecture, multimodal perception pipelines, the 9-parameter deterministic mathematical engine, multi-agent conversational mesh, Google Cloud BigQuery Vector RAG, Pub/Sub event bus, hybrid storage caching tiers, and full REST API specifications.

---

## 🔬 In-Depth Analysis & Subsystem Specifications (`docs/analysis/`)

| Document | Focus & Key Insights |
| :--- | :--- |
| **[PRODUCT_TECHNICAL_SPECIFICATION_AND_GOOGLE_COMPONENTS.md](file:///Users/chawadesharvari17gmail.com/Desktop/projects/InvestAI-AI_BuildersCup/docs/analysis/PRODUCT_TECHNICAL_SPECIFICATION_AND_GOOGLE_COMPONENTS.md)** | Product vision, feature matrix, and comprehensive map of all Google Cloud and GenAI components. |
| **[BIGQUERY_RAG_AGENT_ARCHITECTURE_AND_LOW_COST_DEPLOYMENT.md](file:///Users/chawadesharvari17gmail.com/Desktop/projects/InvestAI-AI_BuildersCup/docs/analysis/BIGQUERY_RAG_AGENT_ARCHITECTURE_AND_LOW_COST_DEPLOYMENT.md)** | Detailed specification of BigQuery Vector Search with `text-embedding-004` (768 dimensions), SQL DDL, ANN vector search queries, and zero-idle-cost architecture. |
| **[VERTEX_AI_MULTIMODAL_VIDEO_PIPELINE.md](file:///Users/chawadesharvari17gmail.com/Desktop/projects/InvestAI-AI_BuildersCup/docs/analysis/VERTEX_AI_MULTIMODAL_VIDEO_PIPELINE.md)** | Vertex AI native video ingestion, SupaData managed transcript fallback, anti-degraded cache guard, and 3-tier persistent video caching. |
| **[CHATBOT_SUBAGENTS_ARCHITECTURE.md](file:///Users/chawadesharvari17gmail.com/Desktop/projects/InvestAI-AI_BuildersCup/docs/analysis/CHATBOT_SUBAGENTS_ARCHITECTURE.md)** | Architecture of the 5 specialized sub-agents (Price, Target, Fundamentals, Explainer, Summarizer) and heavy domain guardrail mechanisms. |
| **[QUARTERLY_REPORT_SUMMARIZER_AGENT.md](file:///Users/chawadesharvari17gmail.com/Desktop/projects/InvestAI-AI_BuildersCup/docs/analysis/QUARTERLY_REPORT_SUMMARIZER_AGENT.md)** | Regulation 33 earnings statement parser, management takeaway generator, and 4-quadrant SWOT matrix generator across 10 benchmark stocks. |
| **[PUB_SUB_ARCHITECTURE.md](file:///Users/chawadesharvari17gmail.com/Desktop/projects/InvestAI-AI_BuildersCup/docs/analysis/PUB_SUB_ARCHITECTURE.md)** | Event-driven decoupled messaging pipeline, topic configurations, push subscriptions, and CaseStore state machine. |
| **[AGENTS_DEPLOYMENT_RATELIMITS_AND_FALLBACKS.md](file:///Users/chawadesharvari17gmail.com/Desktop/projects/InvestAI-AI_BuildersCup/docs/analysis/AGENTS_DEPLOYMENT_RATELIMITS_AND_FALLBACKS.md)** | Production rate-limit handling, dual-client cascade (API Key + Vertex AI ADC), exponential backoffs, and circuit breakers. |
| **[COST_OPTIMIZATION_ANALYSIS.md](file:///Users/chawadesharvari17gmail.com/Desktop/projects/InvestAI-AI_BuildersCup/docs/analysis/COST_OPTIMIZATION_ANALYSIS.md)** | Detailed serverless financial analysis demonstrating how InvestPI scales to zero and operates under **$1.00 USD/month**. |
| **[InvestPI_Planning_Document.md](file:///Users/chawadesharvari17gmail.com/Desktop/projects/InvestAI-AI_BuildersCup/docs/analysis/InvestPI_Planning_Document.md)** | Original product roadmap, problem formulation, and cross-border regulatory scope (SEBI, MAS, ASIC). |

---

## 🎯 Demo Readiness & Judging Playbooks (`docs/demo-readiness/`)

| Document | Focus & Usage |
| :--- | :--- |
| **[PRESENTATION_3MIN_PITCH.md](file:///Users/chawadesharvari17gmail.com/Desktop/projects/InvestAI-AI_BuildersCup/docs/demo-readiness/PRESENTATION_3MIN_PITCH.md)** | A high-impact, 3-minute executive pitch script highlighting the problem, live demo walkthrough, and technical innovations. |
| **[DEMO_VIDEO_SCRIPT_3_MINUTES_AND_JUDGING_PLAYBOOK.md](file:///Users/chawadesharvari17gmail.com/Desktop/projects/InvestAI-AI_BuildersCup/docs/demo-readiness/DEMO_VIDEO_SCRIPT_3_MINUTES_AND_JUDGING_PLAYBOOK.md)** | Turn-by-turn video recording guide, screen capture cues, demo test assets, and anticipated judge Q&A playbook. |

---

## 🚀 Deployment & Operations (`docs/deployment/`)

| Document | Focus & Usage |
| :--- | :--- |
| **[DEPLOYMENT_GUIDE.md](file:///Users/chawadesharvari17gmail.com/Desktop/projects/InvestAI-AI_BuildersCup/docs/deployment/DEPLOYMENT_GUIDE.md)** | End-to-end production deployment guide for Google Cloud Run, Cloud Build, Pub/Sub, and Firestore. |
| **[DEPLOYMENT_CHEATSHEET.md](file:///Users/chawadesharvari17gmail.com/Desktop/projects/InvestAI-AI_BuildersCup/docs/deployment/DEPLOYMENT_CHEATSHEET.md)** | Quick-reference CLI commands, environment variables, and Docker runbooks. |
| **[DEPLOYMENT_READINESS_AUDIT.md](file:///Users/chawadesharvari17gmail.com/Desktop/projects/InvestAI-AI_BuildersCup/docs/deployment/DEPLOYMENT_READINESS_AUDIT.md)** | Pre-deployment checklist covering security, IAM permissions, container health probes, and performance benchmarks. |

---

## 🗺️ Architectural Diagrams (`diagrams/`)

The repository also includes production-grade visual diagrams illustrating system workflows (available in both scalable vector SVG and ultra-high-resolution 4K/Retina PNG for presentations):
- **Architecture Diagram**: [SVG](file:///Users/chawadesharvari17gmail.com/Desktop/projects/InvestAI-AI_BuildersCup/diagrams/investpi_architecture.svg) · [High-Res PNG (3920×2560)](file:///Users/chawadesharvari17gmail.com/Desktop/projects/InvestAI-AI_BuildersCup/diagrams/investpi_architecture.png)
- **Process Flow Diagram**: [SVG](file:///Users/chawadesharvari17gmail.com/Desktop/projects/InvestAI-AI_BuildersCup/diagrams/investpi_process_flow.svg) · [High-Res PNG (3200×2240)](file:///Users/chawadesharvari17gmail.com/Desktop/projects/InvestAI-AI_BuildersCup/diagrams/investpi_process_flow.png)
- **Wireframe Blueprint**: [SVG](file:///Users/chawadesharvari17gmail.com/Desktop/projects/InvestAI-AI_BuildersCup/diagrams/investpi_wireframe_mock.svg) · [High-Res PNG (3200×2300)](file:///Users/chawadesharvari17gmail.com/Desktop/projects/InvestAI-AI_BuildersCup/diagrams/investpi_wireframe_mock.png)

