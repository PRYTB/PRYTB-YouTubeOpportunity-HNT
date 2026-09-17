"""Revenue benchmark provider abstractions and PostgreSQL implementation."""

from abc import ABC, abstractmethod
import json
from typing import Any, Dict, List, Optional, Tuple

from app.database.repositories import YouTubeRepository
from app.models.geography import BenchmarkSourceType, ContentType, RevenueBenchmark
from app.models.profitability import (
    EvidenceType,
    ProductionCostBenchmark,
    ProductionCostMonetary,
)


WILDCARD = "*"
FALLBACK_CONTENT_TYPE = "content_type_wildcard"
FALLBACK_GLOBAL_MARKET = "global_market"
FALLBACK_GLOBAL_CATEGORY = "global_category"
FALLBACK_CONFIDENCE_FACTORS = {
    FALLBACK_CONTENT_TYPE: 0.90,
    FALLBACK_GLOBAL_MARKET: 0.80,
    FALLBACK_GLOBAL_CATEGORY: 0.70,
}


class ProductionCostBenchmarkProvider(ABC):
    """Convert estimated labor hours only when an explicit sourced benchmark exists."""

    @abstractmethod
    def estimate_cost(
        self,
        estimated_hours_low: Optional[float],
        estimated_hours_high: Optional[float],
    ) -> ProductionCostMonetary:
        pass


class EmptyProductionCostBenchmarkProvider(ProductionCostBenchmarkProvider):
    """Safe no-data provider that never fabricates monetary production costs."""

    def estimate_cost(
        self,
        estimated_hours_low: Optional[float],
        estimated_hours_high: Optional[float],
    ) -> ProductionCostMonetary:
        return ProductionCostMonetary(
            available=False,
            estimated_hours_low=estimated_hours_low,
            estimated_hours_high=estimated_hours_high,
            warnings=["Production cost unavailable: no explicit sourced benchmark supplied."],
        )


class ConfiguredProductionCostBenchmarkProvider(ProductionCostBenchmarkProvider):
    """Provider backed by one explicitly supplied, sourced USD hourly-rate benchmark."""

    def __init__(self, benchmark: ProductionCostBenchmark):
        self.benchmark = benchmark

    def estimate_cost(
        self,
        estimated_hours_low: Optional[float],
        estimated_hours_high: Optional[float],
    ) -> ProductionCostMonetary:
        if estimated_hours_low is None or estimated_hours_high is None:
            return ProductionCostMonetary(
                available=False,
                estimated_hours_low=estimated_hours_low,
                estimated_hours_high=estimated_hours_high,
                warnings=["Production cost unavailable: estimated production hours are incomplete."],
            )
        if estimated_hours_low > estimated_hours_high:
            raise ValueError("Production hour bounds must be ordered.")

        estimated_hours_base = (estimated_hours_low + estimated_hours_high) / 2.0
        benchmark = self.benchmark
        cost_components = dict(benchmark.cost_components)
        cost_components["labor"] = {
            "estimated_hours": {
                "low": estimated_hours_low,
                "base": estimated_hours_base,
                "high": estimated_hours_high,
            },
            "hourly_rate_usd": {
                "low": benchmark.hourly_rate_low,
                "base": benchmark.hourly_rate_base,
                "high": benchmark.hourly_rate_high,
            },
        }
        return ProductionCostMonetary(
            available=True,
            low=estimated_hours_low * benchmark.hourly_rate_low,
            base=estimated_hours_base * benchmark.hourly_rate_base,
            high=estimated_hours_high * benchmark.hourly_rate_high,
            estimated_hours_low=estimated_hours_low,
            estimated_hours_base=estimated_hours_base,
            estimated_hours_high=estimated_hours_high,
            cost_components=cost_components,
            evidence_type=benchmark.evidence_type,
            source_name=benchmark.source_name,
            source_version=benchmark.source_version,
            source_date=benchmark.source_date,
            benchmark_id=benchmark.benchmark_id,
            assumptions=benchmark.assumptions.copy(),
            confidence=benchmark.confidence,
        )


class PostgresProductionCostBenchmarkProvider(ProductionCostBenchmarkProvider):
    """Use the canonical sourced production-cost benchmark persisted in PostgreSQL."""

    def __init__(self, repository: Optional[YouTubeRepository] = None):
        self.repository = repository or YouTubeRepository()

    @staticmethod
    def _json_value(value: Any) -> Any:
        return json.loads(value) if isinstance(value, str) else value

    @classmethod
    def _from_record(cls, record: Dict[str, Any]) -> ProductionCostBenchmark:
        return ProductionCostBenchmark(
            hourly_rate_low=record["hourly_rate_low"],
            hourly_rate_base=record["hourly_rate_base"],
            hourly_rate_high=record["hourly_rate_high"],
            currency=record["currency"],
            evidence_type=EvidenceType(record["evidence_type"]),
            source_name=record["source_name"],
            source_version=record.get("source_version") or None,
            source_date=record.get("source_date") or None,
            benchmark_id=str(record["benchmark_id"]),
            assumptions=cls._json_value(record.get("assumptions") or []),
            cost_components=cls._json_value(record.get("cost_components") or {}),
            confidence=record["confidence"],
        )

    @staticmethod
    def _sort_key(record: Dict[str, Any]) -> Tuple[Any, ...]:
        return (
            -float(record["confidence"]),
            str(record.get("source_name") or ""),
            str(record.get("source_version") or ""),
            str(record.get("source_date") or ""),
            str(record["benchmark_id"]),
        )

    def estimate_cost(
        self,
        estimated_hours_low: Optional[float],
        estimated_hours_high: Optional[float],
    ) -> ProductionCostMonetary:
        records = self.repository.get_production_cost_benchmarks()
        if not records:
            return EmptyProductionCostBenchmarkProvider().estimate_cost(
                estimated_hours_low, estimated_hours_high
            )
        selected = sorted(records, key=self._sort_key)[0]
        benchmark = self._from_record(selected)
        return ConfiguredProductionCostBenchmarkProvider(benchmark).estimate_cost(
            estimated_hours_low, estimated_hours_high
        )


class RevenueBenchmarkProvider(ABC):
    """Provide documented RPM benchmarks without deriving missing values."""

    @abstractmethod
    def get_benchmark(
        self,
        market: str,
        content_type: ContentType,
        language: Optional[str] = None,
        content_category: Optional[str] = None,
    ) -> Optional[RevenueBenchmark]:
        pass

    @abstractmethod
    def list_benchmarks(self) -> List[RevenueBenchmark]:
        pass

    @abstractmethod
    def get_coverage_stats(self) -> Dict[str, Any]:
        pass


class EmptyBenchmarkProvider(RevenueBenchmarkProvider):
    """Safe no-data provider that never fabricates a benchmark."""

    def get_benchmark(
        self,
        market: str,
        content_type: ContentType,
        language: Optional[str] = None,
        content_category: Optional[str] = None,
    ) -> Optional[RevenueBenchmark]:
        return None

    def list_benchmarks(self) -> List[RevenueBenchmark]:
        return []

    def get_coverage_stats(self) -> Dict[str, Any]:
        return {
            "total_benchmarks": 0,
            "markets_covered": 0,
            "content_types_covered": 0,
            "source_types": {},
        }


class ConfiguredBenchmarkProvider(RevenueBenchmarkProvider):
    """Provider backed by explicitly configured in-memory records."""

    def __init__(self, benchmarks: Optional[List[RevenueBenchmark]] = None):
        self._benchmarks = benchmarks or []
        self._index: Dict[Tuple[str, str, str, str], RevenueBenchmark] = {}
        self._build_index()

    def _build_index(self) -> None:
        self._index = {}
        for benchmark in self._benchmarks:
            key = (
                benchmark.content_category,
                benchmark.market,
                benchmark.language,
                benchmark.content_type.value,
            )
            current = self._index.get(key)
            if current is None or benchmark.confidence > current.confidence:
                self._index[key] = benchmark

    def add_benchmark(self, benchmark: RevenueBenchmark) -> None:
        self._benchmarks.append(benchmark)
        self._build_index()

    def get_benchmark(
        self,
        market: str,
        content_type: ContentType,
        language: Optional[str] = None,
        content_category: Optional[str] = None,
    ) -> Optional[RevenueBenchmark]:
        key = (
            content_category or "general",
            market,
            language or "en",
            content_type.value,
        )
        return self._index.get(key)

    def list_benchmarks(self) -> List[RevenueBenchmark]:
        return self._benchmarks.copy()

    def get_coverage_stats(self) -> Dict[str, Any]:
        markets = {benchmark.market for benchmark in self._benchmarks}
        content_types = {benchmark.content_type.value for benchmark in self._benchmarks}
        source_types: Dict[str, int] = {}
        for benchmark in self._benchmarks:
            source_type = benchmark.source_type.value
            source_types[source_type] = source_types.get(source_type, 0) + 1
        return {
            "total_benchmarks": len(self._benchmarks),
            "markets_covered": len(markets),
            "content_types_covered": len(content_types),
            "source_types": source_types,
            "markets": sorted(markets),
            "content_types": sorted(content_types),
        }


class PostgresBenchmarkProvider(RevenueBenchmarkProvider):
    """Provider backed by canonical RPM records persisted in PostgreSQL."""

    def __init__(self, repository: Optional[YouTubeRepository] = None):
        self.repository = repository or YouTubeRepository()

    @staticmethod
    def _from_record(record: Dict[str, Any]) -> RevenueBenchmark:
        source_date = record.get("source_date") or None
        return RevenueBenchmark(
            id=str(record["benchmark_id"]),
            market=record["market"],
            language=record["language"],
            content_category=record["content_category"],
            content_type=ContentType(record["content_type"]),
            rpm_low=record["rpm_low"],
            rpm_base=record["rpm_base"],
            rpm_high=record["rpm_high"],
            currency=record["currency"],
            source_name=record["source_name"],
            source_type=BenchmarkSourceType(record["source_type"]),
            source_version=record["source_version"],
            source_date=source_date,
            retrieved_at=record["retrieved_at"],
            confidence=record["confidence"],
            notes=record.get("notes", ""),
        )

    @staticmethod
    def _pick(
        records: List[Dict[str, Any]],
        predicate: Any,
    ) -> Optional[Dict[str, Any]]:
        matches = [record for record in records if predicate(record)]
        if not matches:
            return None
        return sorted(
            matches,
            key=lambda record: (-float(record["confidence"]), str(record["benchmark_id"])),
        )[0]

    def get_benchmark(
        self,
        market: str,
        content_type: ContentType,
        language: Optional[str] = None,
        content_category: Optional[str] = None,
    ) -> Optional[RevenueBenchmark]:
        language = language or "en"
        content_category = content_category or "general"
        content_type_value = content_type.value
        records = self.repository.get_rpm_benchmarks()
        levels = (
            (
                None,
                lambda record: record["content_category"] == content_category
                and record["market"] == market
                and record["language"] == language
                and record["content_type"] == content_type_value,
            ),
            (
                FALLBACK_CONTENT_TYPE,
                lambda record: record["content_category"] == content_category
                and record["market"] == market
                and record["language"] == language
                and record["content_type"] == WILDCARD,
            ),
            (
                FALLBACK_GLOBAL_MARKET,
                lambda record: record["content_category"] == content_category
                and record["market"] == WILDCARD
                and record["language"] == language
                and record["content_type"] == content_type_value,
            ),
            (
                FALLBACK_GLOBAL_CATEGORY,
                lambda record: record["content_category"] == content_category
                and record["market"] == WILDCARD
                and record["language"] == WILDCARD
                and record["content_type"] == WILDCARD,
            ),
        )
        for fallback_level, predicate in levels:
            selected = self._pick(records, predicate)
            if selected is None:
                continue
            benchmark = self._from_record(selected)
            if fallback_level is None:
                return benchmark
            return benchmark.model_copy(
                update={
                    "fallback_level": fallback_level,
                    "confidence": benchmark.confidence
                    * FALLBACK_CONFIDENCE_FACTORS[fallback_level],
                }
            )
        return None

    def list_benchmarks(self) -> List[RevenueBenchmark]:
        return [self._from_record(record) for record in self.repository.get_rpm_benchmarks()]

    def get_coverage_stats(self) -> Dict[str, Any]:
        benchmarks = self.list_benchmarks()
        markets = {benchmark.market for benchmark in benchmarks}
        content_types = {benchmark.content_type.value for benchmark in benchmarks}
        source_types: Dict[str, int] = {}
        for benchmark in benchmarks:
            source_type = benchmark.source_type.value
            source_types[source_type] = source_types.get(source_type, 0) + 1
        return {
            "total_benchmarks": len(benchmarks),
            "markets_covered": len(markets),
            "content_types_covered": len(content_types),
            "source_types": source_types,
            "markets": sorted(markets),
            "content_types": sorted(content_types),
        }


def create_default_provider() -> RevenueBenchmarkProvider:
    return EmptyBenchmarkProvider()
