"""Create and verify the Sprint 7 schema through the InsForge migration API."""
import sys
from pathlib import Path
from typing import Any, Dict, List

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database.insforge_client import InsForgeClient, InsForgeClientError

MIGRATION_VERSION = "20260903000200"
MIGRATION_NAME = "complete-sprint7-market-structure-schema"
MIGRATION_SQL = """
CREATE TABLE IF NOT EXISTS public.market_structure_analyses (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    run_id TEXT NOT NULL,
    source_cluster_run_id TEXT,
    cluster_id INTEGER NOT NULL,
    analyzed_at TIMESTAMPTZ NOT NULL,
    config JSONB NOT NULL,
    quality JSONB NOT NULL,
    metrics JSONB NOT NULL,
    competition_score DOUBLE PRECISION NOT NULL CHECK (competition_score BETWEEN 0 AND 100),
    accessibility_score DOUBLE PRECISION NOT NULL CHECK (accessibility_score BETWEEN 0 AND 100),
    content_depth_score DOUBLE PRECISION NOT NULL CHECK (content_depth_score BETWEEN 0 AND 100),
    evergreen_score DOUBLE PRECISION NOT NULL CHECK (evergreen_score BETWEEN 0 AND 100),
    market_structure_class TEXT NOT NULL CHECK (market_structure_class IN (
        'VIRAL_SATURATED', 'CONTENT_CONSTRAINED',
        'SUSTAINABLE_ACCESSIBLE', 'UNCERTAIN'
    )),
    confidence DOUBLE PRECISION NOT NULL CHECK (confidence BETWEEN 0 AND 100),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT market_structure_run_cluster_key UNIQUE (run_id, cluster_id)
);

CREATE INDEX IF NOT EXISTS market_structure_run_id_idx
    ON public.market_structure_analyses (run_id);
CREATE INDEX IF NOT EXISTS market_structure_source_run_idx
    ON public.market_structure_analyses (source_cluster_run_id);

ALTER TABLE public.market_structure_analyses
    ADD COLUMN IF NOT EXISTS microniche TEXT NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS top_5_rank INTEGER CHECK (top_5_rank BETWEEN 1 AND 5),
    ADD COLUMN IF NOT EXISTS market_structure_score DOUBLE PRECISION NOT NULL DEFAULT 0 CHECK (market_structure_score BETWEEN 0 AND 100),
    ADD COLUMN IF NOT EXISTS trend_score DOUBLE PRECISION CHECK (trend_score BETWEEN 0 AND 100),
    ADD COLUMN IF NOT EXISTS evergreen_class TEXT NOT NULL DEFAULT 'UNKNOWN' CHECK (evergreen_class IN (
        'TREND', 'SEMI_EVERGREEN', 'EVERGREEN', 'UNKNOWN'
    ));
""".strip()


def execute_migration(client: InsForgeClient) -> Dict[str, Any]:
    if not client.url:
        raise InsForgeClientError("INSFORGE_URL is not configured.")
    try:
        response = httpx.post(
            f"{client.url}/api/database/migrations",
            headers=client._get_headers(),
            json={"version": MIGRATION_VERSION, "name": MIGRATION_NAME, "sql": MIGRATION_SQL},
            timeout=client.timeout,
        )
    except httpx.RequestError as exc:
        raise InsForgeClientError(f"Sprint 7 migration network error: {exc}") from exc
    if response.status_code != 201:
        raise InsForgeClientError(
            f"Sprint 7 migration failed (HTTP {response.status_code}): {response.text}"
        )
    try:
        body = response.json()
    except ValueError as exc:
        raise InsForgeClientError(
            "Invalid Sprint 7 migration JSON response."
        ) from exc
    if (
        not isinstance(body, dict)
        or body.get("version") != MIGRATION_VERSION
        or not body.get("statements")
        or not body.get("message")
    ):
        raise InsForgeClientError(f"Invalid Sprint 7 migration response: {body}")
    return body


def verify_tables(client: InsForgeClient) -> List[str]:
    if not client.url:
        raise InsForgeClientError("INSFORGE_URL is not configured.")
    table = "market_structure_analyses"
    try:
        response = httpx.get(
            f"{client.url}/api/database/records/{table}",
            headers=client._get_headers(),
            params={"limit": 1},
            timeout=client.timeout,
        )
    except httpx.RequestError as exc:
        raise InsForgeClientError(
            f"Sprint 7 table verification network error: {exc}"
        ) from exc
    if response.status_code != 200:
        raise InsForgeClientError(
            f"Sprint 7 table {table} is not accessible (HTTP {response.status_code}): {response.text}"
        )
    return [table]


def main() -> None:
    client = InsForgeClient()
    result = execute_migration(client)
    print(f"Migration HTTP 201: {result['message']}")
    for table in verify_tables(client):
        print(f"{table}: EXISTS")


if __name__ == "__main__":
    main()
