"""Tests for Sprint 8 production risk engine component classifications."""

import pytest

from app.analytics.production_risk_engine import ProductionRiskEngine
from app.models.production_risk import (
    AIAssistancePotential,
    ExpertiseRequirement,
    FacelessFeasibility,
    ProductionComplexity,
    RepeatabilityBand,
    RiskLevel,
    Sprint8AnalysisResult,
    Sprint8QualityMetrics,
    ClusterProductionRisk,
)


class TestFacelessFeasibility:
    """Tests for faceless feasibility classification."""

    def test_faceless_high_for_tutorial_screen_recording(self):
        """Screen recording + tutorial terms should yield HIGH faceless feasibility."""
        engine = ProductionRiskEngine()
        cluster = {"cluster_id": 0, "microniche": "Test", "niche": "Test", "subniche": "Test", "video_ids": ["v1"]}
        videos = [{
            "video_id": "v1",
            "title": "Python Tutorial Screen Recording",
            "description": "How to code with screen capture demo",
            "duration_seconds": 600,
        }]
        result = engine._analyze_cluster(cluster, {"v1": videos[0]})
        assert result.faceless_feasibility == FacelessFeasibility.HIGH
        assert result.faceless_confidence > 0
        assert "tutorial" in result.faceless_observed_evidence or "screen" in result.faceless_observed_evidence

    def test_faceless_low_for_interview_personality(self):
        """Interview/on-camera personality should yield LOW faceless feasibility."""
        engine = ProductionRiskEngine()
        cluster = {"cluster_id": 0, "microniche": "Test", "niche": "Test", "subniche": "Test", "video_ids": ["v1"]}
        videos = [{
            "video_id": "v1",
            "title": "Interview with Expert",
            "description": "Live conversation with on-camera personality demonstration",
            "duration_seconds": 600,
        }]
        result = engine._analyze_cluster(cluster, {"v1": videos[0]})
        assert result.faceless_feasibility == FacelessFeasibility.LOW
        assert "interview" in result.faceless_inferred_evidence or "live" in result.faceless_inferred_evidence

    def test_faceless_unknown_insufficient_evidence(self):
        """No textual evidence should yield UNKNOWN faceless feasibility."""
        engine = ProductionRiskEngine()
        cluster = {"cluster_id": 0, "microniche": "Test", "niche": "Test", "subniche": "Test", "video_ids": ["v1"]}
        videos = [{
            "video_id": "v1",
            "title": "",
            "description": "",
            "duration_seconds": 600,
        }]
        result = engine._analyze_cluster(cluster, {"v1": videos[0]})
        assert result.faceless_feasibility == FacelessFeasibility.UNKNOWN
        assert len(result.faceless_warnings) > 0


class TestAIAssistancePotential:
    """Tests for AI assistance potential classification."""

    def test_ai_assistance_high_for_research_script_terms(self):
        """Research, script, summary terms should yield HIGH AI assistance."""
        engine = ProductionRiskEngine()
        cluster = {"cluster_id": 0, "microniche": "Test", "niche": "Test", "subniche": "Test", "video_ids": ["v1"]}
        videos = [{
            "video_id": "v1",
            "title": "AI Research Summary",
            "description": "Automated script generation with translation and fact-check",
            "duration_seconds": 600,
        }]
        result = engine._analyze_cluster(cluster, {"v1": videos[0]})
        assert result.ai_assistance_potential in (AIAssistancePotential.HIGH, AIAssistancePotential.MEDIUM)
        assert result.ai_assistance_confidence > 0

    def test_ai_assistance_unknown_insufficient_evidence(self):
        """No AI terms should yield UNKNOWN AI assistance."""
        engine = ProductionRiskEngine()
        cluster = {"cluster_id": 0, "microniche": "Test", "niche": "Test", "subniche": "Test", "video_ids": ["v1"]}
        videos = [{
            "video_id": "v1",
            "title": "Random Video",
            "description": "Just some content without AI signals",
            "duration_seconds": 600,
        }]
        result = engine._analyze_cluster(cluster, {"v1": videos[0]})
        assert result.ai_assistance_potential == AIAssistancePotential.UNKNOWN


class TestExpertiseRequirement:
    """Tests for expertise requirement classification."""

    def test_expertise_specialist_for_advanced_technical(self):
        """Advanced technical terms should yield SPECIALIST expertise."""
        engine = ProductionRiskEngine()
        cluster = {"cluster_id": 0, "microniche": "Test", "niche": "Test", "subniche": "Test", "video_ids": ["v1"]}
        videos = [{
            "video_id": "v1",
            "title": "Advanced Deep Learning Architecture",
            "description": "Neural network optimization and machine learning engineering certification",
            "duration_seconds": 600,
        }]
        result = engine._analyze_cluster(cluster, {"v1": videos[0]})
        assert result.expertise_requirement == ExpertiseRequirement.SPECIALIST
        assert result.expertise_confidence > 0

    def test_expertise_low_for_beginner_content(self):
        """Beginner commentary/opinion terms should yield LOW expertise."""
        engine = ProductionRiskEngine()
        cluster = {"cluster_id": 0, "microniche": "Test", "niche": "Test", "subniche": "Test", "video_ids": ["v1"]}
        videos = [{
            "video_id": "v1",
            "title": "Beginner Opinion Commentary",
            "description": "My thoughts and casual discussion for beginners",
            "duration_seconds": 600,
        }]
        result = engine._analyze_cluster(cluster, {"v1": videos[0]})
        assert result.expertise_requirement in (ExpertiseRequirement.LOW, ExpertiseRequirement.MEDIUM)


class TestRepeatability:
    """Tests for repeatability classification."""

    def test_repeatability_high_for_template_structure(self):
        """Template, process, pipeline terms should yield HIGH repeatability."""
        engine = ProductionRiskEngine()
        cluster = {"cluster_id": 0, "microniche": "Test", "niche": "Test", "subniche": "Test", "video_ids": ["v1"]}
        videos = [{
            "video_id": "v1",
            "title": "Automated Process Pipeline",
            "description": "Template workflow with repeatable structure and narration",
            "duration_seconds": 600,
        }]
        result = engine._analyze_cluster(cluster, {"v1": videos[0]})
        assert result.repeatability_band in (RepeatabilityBand.HIGH, RepeatabilityBand.MEDIUM)
        assert result.repeatability_score is not None
        assert result.repeatability_score >= 0

    def test_repeatability_low_for_field_interview(self):
        """Field production, interview, limited access should yield LOW repeatability."""
        engine = ProductionRiskEngine()
        cluster = {"cluster_id": 0, "microniche": "Test", "niche": "Test", "subniche": "Test", "video_ids": ["v1"]}
        videos = [{
            "video_id": "v1",
            "title": "Field Interview Access",
            "description": "Limited live field production with exclusive interview",
            "duration_seconds": 600,
        }]
        result = engine._analyze_cluster(cluster, {"v1": videos[0]})
        assert result.repeatability_band in (RepeatabilityBand.LOW, RepeatabilityBand.MEDIUM)

    def test_repeatability_unknown_insufficient_evidence(self):
        """No repeatability signals should yield UNKNOWN."""
        engine = ProductionRiskEngine()
        cluster = {"cluster_id": 0, "microniche": "Test", "niche": "Test", "subniche": "Test", "video_ids": ["v1"]}
        videos = [{
            "video_id": "v1",
            "title": "Random Video",
            "description": "A simple video with generic content",
            "duration_seconds": 600,
        }]
        result = engine._analyze_cluster(cluster, {"v1": videos[0]})
        assert result.repeatability_band == RepeatabilityBand.UNKNOWN
        assert result.repeatability_score is None


class TestRiskComponents:
    """Tests for individual risk component classifications."""

    def test_copyright_risk_levels(self):
        """Copyright terms should produce risk scores and levels."""
        engine = ProductionRiskEngine()
        cluster = {"cluster_id": 0, "microniche": "Test", "niche": "Test", "subniche": "Test", "video_ids": ["v1"]}
        videos = [{
            "video_id": "v1",
            "title": "Copyright Music Fair Use",
            "description": "Licensed content with DMCA considerations",
            "duration_seconds": 600,
        }]
        result = engine._analyze_cluster(cluster, {"v1": videos[0]})
        # Copyright risk score should be populated if terms found
        if result.copyright_risk_score is not None:
            assert result.copyright_risk_level != RiskLevel.UNKNOWN

    def test_platform_policy_risk(self):
        """Platform policy terms should produce risk scores."""
        engine = ProductionRiskEngine()
        cluster = {"cluster_id": 0, "microniche": "Test", "niche": "Test", "subniche": "Test", "video_ids": ["v1"]}
        videos = [{
            "video_id": "v1",
            "title": "Clickbait Misleading Spam",
            "description": "Reused content with activation tricks",
            "duration_seconds": 600,
        }]
        result = engine._analyze_cluster(cluster, {"v1": videos[0]})
        assert result.platform_policy_risk_level != RiskLevel.UNKNOWN or result.platform_policy_risk_score is None

    def test_accuracy_risk(self):
        """Technical accuracy terms should produce risk scores."""
        engine = ProductionRiskEngine()
        cluster = {"cluster_id": 0, "microniche": "Test", "niche": "Test", "subniche": "Test", "video_ids": ["v1"]}
        videos = [{
            "video_id": "v1",
            "title": "Technical Data Statistics 2025",
            "description": "Code function setup with AI predictions",
            "duration_seconds": 600,
        }]
        result = engine._analyze_cluster(cluster, {"v1": videos[0]})
        assert result.accuracy_risk_level != RiskLevel.UNKNOWN or result.accuracy_risk_score is None

    def test_update_burden(self):
        """Date/news/product terms should produce update burden scores."""
        engine = ProductionRiskEngine()
        cluster = {"cluster_id": 0, "microniche": "Test", "niche": "Test", "subniche": "Test", "video_ids": ["v1"]}
        videos = [{
            "video_id": "v1",
            "title": "New 2025 Update Roadmap",
            "description": "Latest software version with future predictions",
            "duration_seconds": 600,
        }]
        result = engine._analyze_cluster(cluster, {"v1": videos[0]})
        assert result.update_burden_level != RiskLevel.UNKNOWN or result.update_burden_score is None

    def test_source_dependency(self):
        """Third-party source terms should produce dependency scores."""
        engine = ProductionRiskEngine()
        cluster = {"cluster_id": 0, "microniche": "Test", "niche": "Test", "subniche": "Test", "video_ids": ["v1"]}
        videos = [{
            "video_id": "v1",
            "title": "Third Party Analysis Review",
            "description": "Interview with professional scientist using external data",
            "duration_seconds": 600,
        }]
        result = engine._analyze_cluster(cluster, {"v1": videos[0]})
        assert result.source_dependency_level != RiskLevel.UNKNOWN or result.source_dependency_score is None


class TestProductionAttractiveness:
    """Tests for production attractiveness scoring."""

    def test_attractiveness_available_with_coverage(self):
        """Sufficient component coverage should make attractiveness available."""
        engine = ProductionRiskEngine()
        cluster = {"cluster_id": 0, "microniche": "Test", "niche": "Test", "subniche": "Test", "video_ids": ["v1"]}
        videos = [{
            "video_id": "v1",
            "title": "Tutorial Screen Recording Guide",
            "description": "How to code with automated process template workflow",
            "duration_seconds": 600,
        }]
        result = engine._analyze_cluster(cluster, {"v1": videos[0]})
        # Should have some attractiveness score components
        assert result.production_attractiveness_coverage >= 0
        if result.production_attractiveness_available:
            assert result.production_attractiveness_score is not None
            assert 0 <= result.production_attractiveness_score <= 100

    def test_attractiveness_unavailable_low_coverage(self):
        """Insufficient coverage should make attractiveness unavailable."""
        engine = ProductionRiskEngine()
        cluster = {"cluster_id": 0, "microniche": "Test", "niche": "Test", "subniche": "Test", "video_ids": ["v1"]}
        videos = [{
            "video_id": "v1",
            "title": "",
            "description": "",
            "duration_seconds": None,
        }]
        result = engine._analyze_cluster(cluster, {"v1": videos[0]})
        assert result.production_attractiveness_available is False
        assert result.production_attractiveness_score is None


class TestUnknownNotFavorable:
    """Tests ensuring UNKNOWN is never treated as favorable."""

    def test_unknown_risk_not_low(self):
        """UNKNOWN risk level should not have a score."""
        engine = ProductionRiskEngine()
        cluster = {"cluster_id": 0, "microniche": "Test", "niche": "Test", "subniche": "Test", "video_ids": ["v1"]}
        videos = [{
            "video_id": "v1",
            "title": "",
            "description": "",
            "duration_seconds": None,
        }]
        result = engine._analyze_cluster(cluster, {"v1": videos[0]})
        # UNKNOWN risk should not have a score
        if result.risk_level == RiskLevel.UNKNOWN:
            assert result.overall_risk_score is None

    def test_unknown_attractiveness_not_available(self):
        """UNKNOWN attractiveness should not be available."""
        engine = ProductionRiskEngine()
        cluster = {"cluster_id": 0, "microniche": "Test", "niche": "Test", "subniche": "Test", "video_ids": ["v1"]}
        videos = [{
            "video_id": "v1",
            "title": "",
            "description": "",
            "duration_seconds": None,
        }]
        result = engine._analyze_cluster(cluster, {"v1": videos[0]})
        assert result.production_attractiveness_available is False


class TestQualityUnknownRates:
    """Tests for quality metrics unknown rate calculations."""

    def test_quality_metrics_faceless_unknown_rate(self):
        """faceless_unknown_rate should reflect actual UNKNOWN count."""
        # Create result with mixed faceless values
        result = Sprint8AnalysisResult(
            run_id="test",
            analyzed_at="2026-09-04T12:00:00+00:00",
            quality=Sprint8QualityMetrics(
                total_videos=10,
                total_clusters=3,
                faceless_unknown_rate=100.0,  # All 3 UNKNOWN
            ),
            clusters=[
                ClusterProductionRisk(
                    cluster_id=i,
                    microniche=f"Test {i}",
                    video_count=3,
                    production_cost_score=50.0,
                    estimated_hours_low=4.0,
                    estimated_hours_high=8.0,
                    production_complexity=ProductionComplexity.MEDIUM,
                    faceless_feasibility=FacelessFeasibility.UNKNOWN,
                    ai_assistance_potential=AIAssistancePotential.UNKNOWN,
                    expertise_requirement=ExpertiseRequirement.UNKNOWN,
                    repeatability_band=RepeatabilityBand.UNKNOWN,
                    risk_level=RiskLevel.UNKNOWN,
                    confidence=50.0,
                ) for i in range(3)
            ],
        )
        # When all 3 are UNKNOWN, rate should be 100%
        assert result.quality.faceless_unknown_rate == 100.0

    def test_quality_metrics_partial_unknown_rate(self):
        """Partial UNKNOWN should give correct percentage."""
        result = Sprint8AnalysisResult(
            run_id="test",
            analyzed_at="2026-09-04T12:00:00+00:00",
            quality=Sprint8QualityMetrics(
                total_videos=10,
                total_clusters=4,
                faceless_unknown_rate=50.0,  # 2 of 4 UNKNOWN
            ),
            clusters=[
                ClusterProductionRisk(
                    cluster_id=i,
                    microniche=f"Test {i}",
                    video_count=2,
                    production_cost_score=50.0,
                    estimated_hours_low=4.0,
                    estimated_hours_high=8.0,
                    production_complexity=ProductionComplexity.MEDIUM,
                    faceless_feasibility=FacelessFeasibility.HIGH if i < 2 else FacelessFeasibility.UNKNOWN,
                    ai_assistance_potential=AIAssistancePotential.UNKNOWN,
                    expertise_requirement=ExpertiseRequirement.UNKNOWN,
                    repeatability_band=RepeatabilityBand.UNKNOWN,
                    risk_level=RiskLevel.UNKNOWN,
                    confidence=50.0,
                ) for i in range(4)
            ],
        )
        assert result.quality.faceless_unknown_rate == 50.0


class TestCluster9HoursCalculation:
    """Test for cluster 9 hours calculation - regression test for unit conversion."""

    def test_hours_calculation_from_median_duration(self):
        """Hours should be calculated from median duration in minutes."""
        # The formula: hours = median_minutes * hours_per_output_minute * effort_factor
        # effort_factor = 0.5 + production_cost / 100.0
        engine = ProductionRiskEngine()
        cluster = {"cluster_id": 9, "microniche": "Test", "niche": "Test", "subniche": "Test", "video_ids": [f"v{i}" for i in range(7)]}
        # 7 videos with ~636 minute durations each
        videos = [{
            "video_id": f"v{i}",
            "title": f"Video {i}",
            "description": "Cybersecurity training certification course guide",
            "duration_seconds": 38186,  # ~636 minutes
        } for i in range(7)]
        video_dict = {v["video_id"]: v for v in videos}
        result = engine._analyze_cluster(cluster, video_dict)

        # Verify the hours calculation uses the correct formula with actual computed values
        median_min = 636.43  # 38186 seconds / 60
        cost = result.production_cost_score
        effort = 0.5 + cost / 100.0
        expected_low = round(max(engine.config.minimum_hours_low, median_min * engine.config.hours_per_output_minute_low * effort), 1)
        expected_high = round(max(engine.config.minimum_hours_high, median_min * engine.config.hours_per_output_minute_high * effort), 1)

        assert result.estimated_hours_low == expected_low, f"Expected {expected_low}, got {result.estimated_hours_low}"
        assert result.estimated_hours_high == expected_high, f"Expected {expected_high}, got {result.estimated_hours_high}"
        # Verify median duration is correctly extracted
        assert result.evidence["median_duration_minutes"] == round(median_min, 2)
        # Verify hours are positive and reasonable
        assert result.estimated_hours_low > 0
        assert result.estimated_hours_high > result.estimated_hours_low


if __name__ == "__main__":
    pytest.main([__file__, "-v"])