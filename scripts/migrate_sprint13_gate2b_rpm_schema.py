"""Create Sprint 13 Gate 2B economic benchmark and candidate tables."""

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from app.database.postgres_client import PostgresClient


MIGRATION_VERSION = "20260915000100"
MIGRATION_NAME = "sprint13-gate2b-rpm-schema"

MIGRATION_SQL = """
CREATE TABLE IF NOT EXISTS public.rpm_benchmarks (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    benchmark_id TEXT NOT NULL,
    content_category TEXT NOT NULL,
    market TEXT NOT NULL,
    language TEXT NOT NULL,
    content_type TEXT NOT NULL,
    rpm_low DOUBLE PRECISION NOT NULL,
    rpm_base DOUBLE PRECISION NOT NULL,
    rpm_high DOUBLE PRECISION NOT NULL,
    currency TEXT NOT NULL DEFAULT 'USD',
    source_name TEXT NOT NULL,
    source_type TEXT NOT NULL,
    source_version TEXT NOT NULL,
    source_date TEXT NOT NULL DEFAULT '',
    retrieved_at TIMESTAMPTZ NOT NULL,
    confidence DOUBLE PRECISION NOT NULL,
    notes TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_rpm_benchmarks_id UNIQUE (benchmark_id),
    CONSTRAINT uq_rpm_benchmarks_provenance UNIQUE (
        content_category, market, language, content_type,
        source_name, source_type, source_version, source_date
    ),
    CONSTRAINT ck_rpm_benchmarks_values CHECK (
        rpm_low >= 0 AND rpm_low <= rpm_base AND rpm_base <= rpm_high
    ),
    CONSTRAINT ck_rpm_benchmarks_confidence CHECK (
        confidence >= 0 AND confidence <= 100
    ),
    CONSTRAINT ck_rpm_benchmarks_currency CHECK (currency = 'USD'),
    CONSTRAINT ck_rpm_benchmarks_source CHECK (
        source_type IN (
            'EMPIRICAL', 'INDUSTRY_BENCHMARK', 'DERIVED',
            'observed_benchmark', 'external_benchmark', 'manual_benchmark'
        )
    )
);
CREATE INDEX IF NOT EXISTS idx_rpm_benchmarks_lookup ON public.rpm_benchmarks (
    content_category, market, language, content_type, confidence DESC, benchmark_id
);

CREATE TABLE IF NOT EXISTS public.production_cost_benchmarks (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    benchmark_id TEXT NOT NULL,
    hourly_rate_low DOUBLE PRECISION NOT NULL,
    hourly_rate_base DOUBLE PRECISION NOT NULL,
    hourly_rate_high DOUBLE PRECISION NOT NULL,
    currency TEXT NOT NULL DEFAULT 'USD',
    evidence_type TEXT NOT NULL,
    source_name TEXT NOT NULL,
    source_version TEXT NOT NULL DEFAULT '',
    source_date TEXT NOT NULL DEFAULT '',
    retrieved_at TIMESTAMPTZ NOT NULL,
    assumptions JSONB NOT NULL DEFAULT '[]'::jsonb,
    cost_components JSONB NOT NULL DEFAULT '{}'::jsonb,
    confidence DOUBLE PRECISION NOT NULL,
    notes TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_production_cost_benchmarks_id UNIQUE (benchmark_id),
    CONSTRAINT uq_production_cost_benchmarks_provenance UNIQUE (
        source_name, source_version, source_date
    ),
    CONSTRAINT ck_production_cost_benchmarks_values CHECK (
        hourly_rate_low >= 0
        AND hourly_rate_low <= hourly_rate_base
        AND hourly_rate_base <= hourly_rate_high
    ),
    CONSTRAINT ck_production_cost_benchmarks_currency CHECK (currency = 'USD'),
    CONSTRAINT ck_production_cost_benchmarks_evidence CHECK (
        evidence_type = 'EXTERNAL_BENCHMARK'
    ),
    CONSTRAINT ck_production_cost_benchmarks_confidence CHECK (
        confidence >= 0 AND confidence <= 100
    )
);
CREATE INDEX IF NOT EXISTS idx_production_cost_benchmarks_order
    ON public.production_cost_benchmarks (
        confidence DESC, source_name, source_version, source_date, benchmark_id
    );

CREATE TABLE IF NOT EXISTS public.candidate_economics (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    run_id TEXT NOT NULL,
    candidate_id TEXT NOT NULL,
    candidate_rank INTEGER NOT NULL,
    benchmark_id TEXT,
    rpm_available BOOLEAN NOT NULL DEFAULT FALSE,
    cost_benchmark_id TEXT,
    cost_available BOOLEAN NOT NULL DEFAULT FALSE,
    fallback_level TEXT,
    economics_payload JSONB NOT NULL,
    provenance_payload JSONB NOT NULL,
    methodology_version TEXT NOT NULL,
    source_dataset_hash TEXT NOT NULL,
    calculated_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_candidate_economics_candidate UNIQUE (run_id, candidate_id),
    CONSTRAINT uq_candidate_economics_rank UNIQUE (run_id, candidate_rank)
);
ALTER TABLE public.candidate_economics
    ADD COLUMN IF NOT EXISTS cost_benchmark_id TEXT,
    ADD COLUMN IF NOT EXISTS cost_available BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE public.candidate_economics
    DROP CONSTRAINT IF EXISTS fk_candidate_economics_benchmark,
    DROP CONSTRAINT IF EXISTS fk_candidate_economics_cost_benchmark,
    DROP CONSTRAINT IF EXISTS ck_candidate_economics_benchmark,
    DROP CONSTRAINT IF EXISTS ck_candidate_economics_cost_benchmark,
    ADD CONSTRAINT fk_candidate_economics_benchmark FOREIGN KEY (benchmark_id)
        REFERENCES public.rpm_benchmarks (benchmark_id),
    ADD CONSTRAINT fk_candidate_economics_cost_benchmark FOREIGN KEY (cost_benchmark_id)
        REFERENCES public.production_cost_benchmarks (benchmark_id),
    ADD CONSTRAINT ck_candidate_economics_benchmark CHECK (
        rpm_available = (benchmark_id IS NOT NULL)
    ),
    ADD CONSTRAINT ck_candidate_economics_cost_benchmark CHECK (
        cost_available = (cost_benchmark_id IS NOT NULL)
    );
CREATE INDEX IF NOT EXISTS idx_candidate_economics_order
    ON public.candidate_economics (run_id, candidate_rank, candidate_id);
""".strip()


def execute_migration(client: PostgresClient) -> dict:
    client.execute(MIGRATION_SQL)
    return {
        "version": MIGRATION_VERSION,
        "name": MIGRATION_NAME,
        "message": "Migration applied",
    }


def apply_migration() -> None:
    execute_migration(PostgresClient())


if __name__ == "__main__":
    apply_migration()
