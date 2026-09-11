"""Unit tests for Sprint 12 Gate 7 final analytical rerun."""

import pytest
import hashlib
from pathlib import Path
from scripts.create_sprint12_dataset_contract import clean_text_for_embedding, compute_dataset_hash, is_test_video
from scripts.execute_sprint12_gate7 import compute_assignments_hash, normalize_intent_string


def test_dataset_guard_and_clean_embedding():
    text = clean_text_for_embedding("Building an AI Agent in Python", "Learn how to build agents with OpenAI and LangChain.")
    assert "ai" in text
    assert "agent" in text
    assert "python" in text
    assert "https" not in text


def test_fixture_video_detection():
    test_v = {"video_id": "test_video_001", "title": "Test Video"}
    prod_v = {"video_id": "--Z5F-c1PAA", "title": "Real YouTube Video"}
    assert is_test_video(test_v) is True
    assert is_test_video(prod_v) is False


def test_compute_dataset_hash_reproducibility():
    rows1 = [
        {"video_id": "v2", "semantic_text": "text two"},
        {"video_id": "v1", "semantic_text": "text one"}
    ]
    rows2 = [
        {"video_id": "v1", "semantic_text": "text one"},
        {"video_id": "v2", "semantic_text": "text two"}
    ]
    h1 = compute_dataset_hash(rows1)
    h2 = compute_dataset_hash(rows2)
    assert h1 == h2


def test_assignments_hash_determinism():
    assignments1 = [("vid_b", 1), ("vid_a", 0)]
    assignments2 = [("vid_a", 0), ("vid_b", 1)]
    hash1 = compute_assignments_hash(assignments1)
    hash2 = compute_assignments_hash(assignments2)
    assert hash1 == hash2


def test_intent_string_normalization():
    intent1 = normalize_intent_string("AI Automation Tools 2026!!!")
    intent2 = normalize_intent_string("ai automation tools 2026")
    assert intent1 == intent2
