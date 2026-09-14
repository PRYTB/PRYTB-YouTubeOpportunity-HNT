"""
Migration script for Sprint 12 Gate 7 Schema.

Creates dedicated tables for Gate 7 analytical provenance, first-class semantic definitions,
semantic memberships, Top100 outliers, raw semantic patterns, and Top20 selected definitions.
Also adds baseline fields to video_outlier_analyses.
"""

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from app.database.postgres_client import PostgresClient

MIGRATION_SQL = """
-- 1. Extend video_outlier_analyses with complete baseline & rank fields if not present
ALTER TABLE public.video_outlier_analyses
    ADD COLUMN IF NOT EXISTS channel_mean_views DOUBLE PRECISION,
    ADD COLUMN IF NOT EXISTS channel_median_views_per_day DOUBLE PRECISION,
    ADD COLUMN IF NOT EXISTS baseline_video_count INTEGER DEFAULT 0,
    ADD COLUMN IF NOT EXISTS baseline_confidence TEXT DEFAULT 'VERY_LOW',
    ADD COLUMN IF NOT EXISTS latest_velocity DOUBLE PRECISION,
    ADD COLUMN IF NOT EXISTS latest_acceleration DOUBLE PRECISION,
    ADD COLUMN IF NOT EXISTS views_to_subscribers_ratio DOUBLE PRECISION,
    ADD COLUMN IF NOT EXISTS outlier_rank INTEGER;

-- 2. Dedicated Gate 7 Top100 Outliers Table
CREATE TABLE IF NOT EXISTS public.gate7_top100_outliers (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    run_id TEXT NOT NULL,
    dataset_hash TEXT NOT NULL,
    outlier_rank INTEGER NOT NULL,
    video_id TEXT NOT NULL,
    channel_id TEXT NOT NULL,
    outlier_score DOUBLE PRECISION NOT NULL,
    is_strong_outlier BOOLEAN NOT NULL,
    is_major_outlier BOOLEAN NOT NULL,
    is_extreme_outlier BOOLEAN NOT NULL,
    small_channel_outlier BOOLEAN NOT NULL,
    channel_median_views DOUBLE PRECISION,
    channel_mean_views DOUBLE PRECISION,
    baseline_video_count INTEGER NOT NULL DEFAULT 0,
    baseline_confidence TEXT NOT NULL DEFAULT 'VERY_LOW',
    ranking_hash TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_gate7_top100_run_rank UNIQUE (run_id, outlier_rank),
    CONSTRAINT uq_gate7_top100_run_video UNIQUE (run_id, video_id)
);
CREATE INDEX IF NOT EXISTS idx_gate7_top100_run ON public.gate7_top100_outliers(run_id);

-- 3. Dedicated Gate 7 Raw Semantic Patterns Table
CREATE TABLE IF NOT EXISTS public.gate7_raw_semantic_patterns (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    run_id TEXT NOT NULL,
    pattern_id TEXT NOT NULL,
    parent_cluster_id INTEGER NOT NULL,
    raw_pattern TEXT NOT NULL,
    normalized_intent TEXT NOT NULL,
    frequency INTEGER NOT NULL DEFAULT 1,
    sample_video_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_gate7_raw_patterns UNIQUE (run_id, pattern_id)
);
CREATE INDEX IF NOT EXISTS idx_gate7_raw_patterns_run ON public.gate7_raw_semantic_patterns(run_id);

-- 4. Dedicated Gate 7 First-Class Semantic Definitions Table
CREATE TABLE IF NOT EXISTS public.gate7_semantic_definitions (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    run_id TEXT NOT NULL,
    definition_id TEXT NOT NULL,
    parent_cluster_id INTEGER NOT NULL,
    analytical_ordinal INTEGER NOT NULL,
    niche TEXT NOT NULL,
    subniche TEXT NOT NULL,
    microniche TEXT NOT NULL,
    normalized_intent TEXT NOT NULL,
    distinct_intents_count INTEGER NOT NULL DEFAULT 0,
    content_depth TEXT NOT NULL DEFAULT 'UNKNOWN',
    video_count INTEGER NOT NULL DEFAULT 0,
    outlier_count INTEGER NOT NULL DEFAULT 0,
    small_channel_outliers INTEGER NOT NULL DEFAULT 0,
    channel_count INTEGER NOT NULL DEFAULT 0,
    evidence_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_gate7_semdef_run_def UNIQUE (run_id, definition_id),
    CONSTRAINT uq_gate7_semdef_run_ord UNIQUE (run_id, analytical_ordinal)
);
CREATE INDEX IF NOT EXISTS idx_gate7_semdef_run ON public.gate7_semantic_definitions(run_id);

-- 5. Dedicated Gate 7 Semantic Memberships Table
CREATE TABLE IF NOT EXISTS public.gate7_semantic_memberships (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    run_id TEXT NOT NULL,
    definition_id TEXT NOT NULL,
    video_id TEXT NOT NULL,
    parent_cluster_id INTEGER NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_gate7_membership UNIQUE (run_id, definition_id, video_id)
);
CREATE INDEX IF NOT EXISTS idx_gate7_membership_run ON public.gate7_semantic_memberships(run_id);
CREATE INDEX IF NOT EXISTS idx_gate7_membership_def ON public.gate7_semantic_memberships(run_id, definition_id);

-- 6. Dedicated Gate 7 Top20 Definitions Table
CREATE TABLE IF NOT EXISTS public.gate7_top20_definitions (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    run_id TEXT NOT NULL,
    rank INTEGER NOT NULL,
    definition_id TEXT NOT NULL,
    analytical_ordinal INTEGER NOT NULL,
    niche TEXT NOT NULL,
    subniche TEXT NOT NULL,
    microniche TEXT NOT NULL,
    video_count INTEGER NOT NULL DEFAULT 0,
    outlier_count INTEGER NOT NULL DEFAULT 0,
    channel_count INTEGER NOT NULL DEFAULT 0,
    distinct_intents_count INTEGER NOT NULL DEFAULT 0,
    ranking_hash TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_gate7_top20_run_rank UNIQUE (run_id, rank),
    CONSTRAINT uq_gate7_top20_run_def UNIQUE (run_id, definition_id)
);
CREATE INDEX IF NOT EXISTS idx_gate7_top20_run ON public.gate7_top20_definitions(run_id);
"""


def apply_migration() -> None:
    client = PostgresClient()
    print("Applying Sprint 12 Gate 7 schema migration...")
    client.execute(MIGRATION_SQL)
    print("Migration applied successfully.")


if __name__ == "__main__":
    apply_migration()
