"""
BigQuery Vector Search & RAG Module for Quarterly Financial Reports
===================================================================
Provides native Google Cloud BigQuery Vector Search capabilities:
1. SQL DDL for `quarterly_report_chunks` table with 768-dim `text-embedding-004` vectors.
2. BigQuery ML `ML.GENERATE_EMBEDDING` and `VECTOR_SEARCH` query execution.
3. Offline/Local fallback chunk retrieval engine (guarantees local tests and offline pitches work seamlessly).
4. Automated ingestion exporter to generate BigQuery JSONL seed datasets.
"""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("investpi.bigquery_rag")

# BigQuery Table & Dataset configuration
BQ_DATASET_DEFAULT = "financial_intelligence"
BQ_TABLE_DEFAULT = "quarterly_report_chunks"
EMBEDDING_MODEL_DEFAULT = "embedding_model"

BIGQUERY_DDL = """
-- 1. Create Dataset
CREATE SCHEMA IF NOT EXISTS `{{PROJECT_ID}}.financial_intelligence`
OPTIONS (location = 'US');

-- 2. Create Vertex AI Remote Connection in BigQuery
-- (Via Cloud Console or: bq mk --connection --location=US --project_id={{PROJECT_ID}} --connection_type=CLOUD_RESOURCE vertex-connection)

-- 3. Create BigQuery ML text-embedding-004 Remote Model
CREATE OR REPLACE MODEL `{{PROJECT_ID}}.financial_intelligence.embedding_model`
REMOTE WITH CONNECTION `{{PROJECT_ID}}.us.vertex-connection`
OPTIONS (ENDPOINT = 'text-embedding-004');

-- 4. Create Financial Chunks Table with Vector Column
CREATE TABLE IF NOT EXISTS `{{PROJECT_ID}}.financial_intelligence.quarterly_report_chunks` (
    chunk_id STRING NOT NULL,
    ticker STRING NOT NULL,
    company_name STRING NOT NULL,
    quarter STRING NOT NULL,
    section_name STRING,
    content STRING NOT NULL,
    embedding ARRAY<FLOAT64>,
    metadata JSON,
    ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
)
PARTITION BY DATE(ingested_at)
CLUSTER BY ticker, quarter;

-- 5. Create Vector Index on Embedding Column
CREATE VECTOR INDEX IF NOT EXISTS quarterly_chunks_vector_idx
ON `{{PROJECT_ID}}.financial_intelligence.quarterly_report_chunks`(embedding)
OPTIONS(distance_type = 'COSINE', index_type = 'IVF');

-- 6. Create Structured Quarterly Reports Master Table
CREATE TABLE IF NOT EXISTS `{{PROJECT_ID}}.financial_intelligence.quarterly_reports` (
    ticker STRING NOT NULL,
    quarter STRING NOT NULL,
    company_name STRING NOT NULL,
    report_data JSON,
    ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
)
CLUSTER BY ticker, quarter;
"""

BIGQUERY_VECTOR_SEARCH_SQL = """
SELECT 
    base.chunk_id,
    base.ticker,
    base.company_name,
    base.quarter,
    base.section_name,
    base.content,
    distance
FROM VECTOR_SEARCH(
    TABLE `{{PROJECT_ID}}.financial_intelligence.quarterly_report_chunks`,
    'embedding',
    (
        SELECT ml_generate_embedding_result AS embedding
        FROM ML.GENERATE_EMBEDDING(
            MODEL `{{PROJECT_ID}}.financial_intelligence.embedding_model`,
            (SELECT @query_text AS content)
        )
    ),
    top_k => @top_k,
    distance_type => 'COSINE'
)
WHERE base.ticker = @target_ticker
ORDER BY distance ASC;
"""


class BigQueryFinancialRAG:
    """
    Manages vector retrieval against Google Cloud BigQuery Vector Search
    with deterministic local fallback for zero-cloud-lock offline testing.
    """

    def __init__(self, project_id: Optional[str] = None, dataset_id: Optional[str] = None):
        from app.config import Config
        self.project_id = project_id or getattr(Config, "BIGQUERY_PROJECT_ID", None) or os.getenv("BIGQUERY_PROJECT_ID") or os.getenv("GCP_PROJECT_ID")
        self.dataset_id = dataset_id or getattr(Config, "BIGQUERY_DATASET", None) or os.getenv("BIGQUERY_DATASET") or BQ_DATASET_DEFAULT
        self._bq_client = None
        self._init_client()

    def _init_client(self):
        """Attempts to initialize google-cloud-bigquery client if credentials exist."""
        if not self.project_id:
            logger.info("No BIGQUERY_PROJECT_ID configured; operating in Local RAG Fallback mode.")
            return

        try:
            from google.cloud import bigquery
            self._bq_client = bigquery.Client(project=self.project_id)
            logger.info(f"BigQuery client initialized successfully for project: {self.project_id}")
        except Exception as e:
            logger.warning(f"Could not initialize BigQuery client ({e}). Falling back to Local RAG.")
            self._bq_client = None

    @property
    def is_cloud_enabled(self) -> bool:
        from app.config import Config
        # When running in Cloud (Cloud Run), strictly use BigQuery.
        # When running in Local development, use local data/ folder.
        cloud_active = Config.IS_CLOUD or os.getenv("FORCE_BIGQUERY_LOCAL", "0").lower() in ("1", "true", "yes")
        return bool(cloud_active and self._bq_client is not None and self.project_id)

    def search_chunks(
        self,
        ticker: str,
        query_text: str = "Quarterly financial results, revenue, EBITDA, profit after tax and SWOT analysis",
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Execute vector similarity search for relevant financial chunks.
        Dispatches to Google BigQuery if cloud credentials present, otherwise uses local chunker.
        """
        norm_ticker = ticker.strip().upper()
        if not norm_ticker.endswith(".NS") and "." not in norm_ticker:
            norm_ticker = f"{norm_ticker}.NS"

        if self.is_cloud_enabled:
            try:
                return self._search_bigquery(norm_ticker, query_text, top_k)
            except Exception as e:
                logger.error(f"BigQuery vector search failed ({e}). Reverting to Local RAG Fallback.")

        return self._search_local(norm_ticker, query_text, top_k)

    def _search_bigquery(self, ticker: str, query_text: str, top_k: int) -> List[Dict[str, Any]]:
        from google.cloud import bigquery
        query = BIGQUERY_VECTOR_SEARCH_SQL.replace("{{PROJECT_ID}}", self.project_id)
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("query_text", "STRING", query_text),
                bigquery.ScalarQueryParameter("target_ticker", "STRING", ticker),
                bigquery.ScalarQueryParameter("top_k", "INT64", top_k),
            ]
        )
        query_job = self._bq_client.query(query, job_config=job_config)
        results = []
        for row in query_job:
            results.append({
                "chunk_id": row.chunk_id,
                "ticker": row.ticker,
                "company_name": row.company_name,
                "quarter": row.quarter,
                "section_name": row.section_name,
                "content": row.content,
                "distance": float(row.distance),
                "source": "BigQuery Vector Search (text-embedding-004)"
            })
        return results

    def _search_local(self, ticker: str, query_text: str, top_k: int) -> List[Dict[str, Any]]:
        """
        Deterministic local chunk search over the stock's Markdown filing document.
        Chunks sections by markdown headers (##), computing term overlap relevance.
        """
        from app.config import DATA_DIR
        q_dir = DATA_DIR / "quarterly_reports"
        
        # Look for matching file stem
        matches = list(q_dir.glob(f"{ticker}*.md"))
        if not matches:
            # Try prefix match
            base = ticker.replace(".NS", "")
            matches = list(q_dir.glob(f"{base}*.md"))

        if not matches:
            return []

        md_file = matches[0]
        try:
            content = md_file.read_text(encoding="utf-8")
        except Exception as e:
            logger.warning(f"Failed to read local markdown filing {md_file}: {e}")
            return []

        # Split into sections by markdown headers
        raw_sections = content.split("## ")
        chunks: List[Dict[str, Any]] = []

        query_tokens = set(query_text.lower().replace(",", " ").replace(".", " ").split())

        for idx, sec in enumerate(raw_sections):
            text = sec.strip()
            if not text:
                continue
            lines = text.splitlines()
            title = lines[0].strip() if lines else f"Section {idx}"
            body = "\n".join(lines[1:]).strip() if len(lines) > 1 else text

            # Compute term overlap score
            body_tokens = set(body.lower().replace(",", " ").replace(".", " ").split())
            overlap = len(query_tokens.intersection(body_tokens))
            score = round(1.0 / (1.0 + overlap), 4)

            chunks.append({
                "chunk_id": f"{ticker}_sec_{idx}",
                "ticker": ticker,
                "company_name": lines[0] if idx == 0 else ticker,
                "quarter": "Q1 FY2026-27",
                "section_name": title,
                "content": text,
                "distance": score,
                "source": f"Local Filing Document ({md_file.name})"
            })

        chunks.sort(key=lambda x: x["distance"])
        return chunks[:top_k]

    def get_quarterly_report(self, ticker: str) -> Optional[Dict[str, Any]]:
        """
        Retrieves full structured quarterly report (headline metrics, segments, SWOT, 5 pointers)
        from Google Cloud BigQuery financial_intelligence.quarterly_reports table.
        Falls back to local file if BigQuery is unavailable.
        """
        norm_ticker = ticker.strip().upper()
        if not norm_ticker.endswith(".NS") and "." not in norm_ticker:
            norm_ticker = f"{norm_ticker}.NS"

        if self.is_cloud_enabled:
            try:
                from google.cloud import bigquery
                query = f"""
                SELECT report_data 
                FROM `{self.project_id}.{self.dataset_id}.quarterly_reports` 
                WHERE ticker = @target_ticker 
                ORDER BY ingested_at DESC 
                LIMIT 1
                """
                job_config = bigquery.QueryJobConfig(
                    query_parameters=[
                        bigquery.ScalarQueryParameter("target_ticker", "STRING", norm_ticker),
                    ]
                )
                query_job = self._bq_client.query(query, job_config=job_config)
                for row in query_job:
                    raw = row.report_data
                    if isinstance(raw, str):
                        data = json.loads(raw)
                    elif isinstance(raw, dict):
                        data = raw
                    else:
                        continue
                    data["source_engine"] = "Google BigQuery (financial_intelligence.quarterly_reports)"
                    logger.info(f"Retrieved quarterly report for {norm_ticker} from BigQuery.")
                    return data
            except Exception as e:
                logger.warning(f"BigQuery fetch of quarterly_reports for {norm_ticker} failed: {e}. Falling back to local file.")

        return self._get_quarterly_report_local(norm_ticker)

    def _get_quarterly_report_local(self, ticker: str) -> Optional[Dict[str, Any]]:
        from app.config import DATA_DIR
        q_dir = DATA_DIR / "quarterly_reports"
        matches = list(q_dir.glob(f"{ticker}*.json"))
        if not matches:
            base = ticker.replace(".NS", "")
            matches = list(q_dir.glob(f"{base}*.json"))
        if matches:
            try:
                with open(matches[0], "r", encoding="utf-8") as f:
                    data = json.load(f)
                    data["source_engine"] = "Local Filing Document Parser"
                    return data
            except Exception:
                pass
        return None

    @classmethod
    def export_seed_data_for_bigquery(cls, output_jsonl: Optional[Path] = None) -> Path:
        """
        Scans all 10 quarterly report documents in `data/quarterly_reports/`
        and produces a BigQuery-ready JSONL file suitable for `bq load`.
        """
        from app.config import DATA_DIR
        q_dir = DATA_DIR / "quarterly_reports"
        out_path = output_jsonl or (DATA_DIR / "bigquery_seed_chunks.jsonl")

        records: List[Dict[str, Any]] = []
        for md_file in sorted(q_dir.glob("*.md")):
            stem = md_file.stem
            ticker = stem.split("_")[0]
            try:
                text = md_file.read_text(encoding="utf-8")
            except Exception:
                continue

            sections = text.split("## ")
            for idx, sec in enumerate(sections):
                s_text = sec.strip()
                if not s_text:
                    continue
                lines = s_text.splitlines()
                title = lines[0].strip() if lines else f"Section {idx}"
                records.append({
                    "chunk_id": f"{stem}_{idx}",
                    "ticker": ticker,
                    "company_name": ticker,
                    "quarter": "Q1 FY2026-27",
                    "section_name": title,
                    "content": s_text,
                    "metadata": json.dumps({"source_file": md_file.name, "section_idx": idx})
                })

        with open(out_path, "w", encoding="utf-8") as f:
            for r in records:
                f.write(json.dumps(r) + "\n")

        logger.info(f"Exported {len(records)} chunks to BigQuery seed JSONL at {out_path}")
        return out_path
