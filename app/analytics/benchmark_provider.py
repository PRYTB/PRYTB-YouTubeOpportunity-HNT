"""
Sprint 6: Revenue Benchmark Provider Abstraction

Architecture for benchmark abstraction. No web scraping required.
Primary requirement: correct architecture allowing observed/external/manual/unknown sources.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from app.models.geography import (
    RevenueBenchmark,
    BenchmarkSourceType,
    ContentType,
    MarketTier
)


class RevenueBenchmarkProvider(ABC):
    """Abstract base class for revenue benchmark providers.

    Implementations must provide benchmarks for market/content_type combinations.
    If no benchmark exists for a query, return None (not fabricated values).
    """

    @abstractmethod
    def get_benchmark(
        self,
        market: str,  # country code, region group, or tier name
        content_type: ContentType
    ) -> Optional[RevenueBenchmark]:
        """Get a benchmark for the given market and content type.

        Returns None if no benchmark is available.
        """
        pass

    @abstractmethod
    def list_benchmarks(self) -> List[RevenueBenchmark]:
        """List all available benchmarks."""
        pass

    @abstractmethod
    def get_coverage_stats(self) -> Dict[str, Any]:
        """Get coverage statistics for available benchmarks."""
        pass


class EmptyBenchmarkProvider(RevenueBenchmarkProvider):
    """Provider with no benchmarks - returns None for all queries.

    Use when no benchmark data is available or configured.
    This is the safe default that never fabricates values.
    """

    def get_benchmark(
        self,
        market: str,
        content_type: ContentType
    ) -> Optional[RevenueBenchmark]:
        return None

    def list_benchmarks(self) -> List[RevenueBenchmark]:
        return []

    def get_coverage_stats(self) -> Dict[str, Any]:
        return {
            "total_benchmarks": 0,
            "markets_covered": 0,
            "content_types_covered": 0,
            "source_types": {}
        }


class ConfiguredBenchmarkProvider(RevenueBenchmarkProvider):
    """Benchmark provider backed by configured benchmark records.

    Benchmarks are loaded from configuration (file, env, or code).
    Supports observed, external, and manual benchmark sources.
    """

    def __init__(self, benchmarks: Optional[List[RevenueBenchmark]] = None):
        self._benchmarks = benchmarks or []
        self._index: Dict[str, RevenueBenchmark] = {}
        self._build_index()

    def _build_index(self) -> None:
        """Build lookup index: market|content_type -> benchmark"""
        self._index = {}
        for bm in self._benchmarks:
            key = f"{bm.market}|{bm.content_type.value}"
            # Keep highest confidence benchmark for each key
            if key not in self._index or bm.confidence > self._index[key].confidence:
                self._index[key] = bm

    def add_benchmark(self, benchmark: RevenueBenchmark) -> None:
        """Add a benchmark to the provider."""
        self._benchmarks.append(benchmark)
        self._build_index()

    def get_benchmark(
        self,
        market: str,
        content_type: ContentType
    ) -> Optional[RevenueBenchmark]:
        key = f"{market}|{content_type.value}"
        return self._index.get(key)

    def list_benchmarks(self) -> List[RevenueBenchmark]:
        return self._benchmarks.copy()

    def get_coverage_stats(self) -> Dict[str, Any]:
        markets = set()
        content_types = set()
        source_types = {}

        for bm in self._benchmarks:
            markets.add(bm.market)
            content_types.add(bm.content_type.value)
            st = bm.source_type.value
            source_types[st] = source_types.get(st, 0) + 1

        return {
            "total_benchmarks": len(self._benchmarks),
            "markets_covered": len(markets),
            "content_types_covered": len(content_types),
            "source_types": source_types,
            "markets": sorted(markets),
            "content_types": sorted(content_types)
        }


def create_default_provider() -> RevenueBenchmarkProvider:
    """Create the default benchmark provider.

    Currently returns EmptyBenchmarkProvider as no verified benchmarks
    are configured in this sprint. Architecture is ready for future
    integration of observed/external/manual benchmarks.
    """
    return EmptyBenchmarkProvider()


# Example of how to create a provider with manual benchmarks:
# def create_manual_benchmark_provider() -> ConfiguredBenchmarkProvider:
#     from datetime import datetime
#     benchmarks = [
#         RevenueBenchmark(
#             source_type=BenchmarkSourceType.MANUAL_BENCHMARK,
#             source_name="Industry Report 2024",
#             market="US",
#             content_type=ContentType.LONG_FORM,
#             value_low=2.0,
#             value_mid=5.0,
#             value_high=12.0,
#             currency="USD",
#             retrieved_at=datetime(2024, 1, 15),
#             confidence=70.0,
#             notes="US long-form RPM range from industry survey"
#         ),
#         RevenueBenchmark(
#             source_type=BenchmarkSourceType.MANUAL_BENCHMARK,
#             source_name="Creator Survey 2024",
#             market="US",
#             content_type=ContentType.SHORT,
#             value_low=0.01,
#             value_mid=0.05,
#             value_high=0.15,
#             currency="USD",
#             retrieved_at=datetime(2024, 1, 15),
#             confidence=60.0,
#             notes="US Shorts RPM range from creator survey"
#         ),
#     ]
#     return ConfiguredBenchmarkProvider(benchmarks)