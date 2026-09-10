"""
Integration and Smoke tests for Streamlit Dashboard MVP (Sprint 11).
"""

import pytest
from streamlit.testing.v1 import AppTest
from dashboard.data_service import DashboardDataService


@pytest.mark.integration
def test_dashboard_data_service_integration():
    """Verify the service reads PostgreSQL data and builds a compatible dataset without writes."""
    service = DashboardDataService()
    dataset = service.get_dashboard_data()

    assert dataset.provenance.is_compatible is True
    assert dataset.total_videos == 7611
    assert dataset.total_clusters == 10
    assert len(dataset.candidates) == 10
    assert len(dataset.videos) == 7611


@pytest.mark.integration
def test_streamlit_app_smoke_test():
    """Smoke test running Streamlit app initialization using Streamlit AppTest framework across pages."""
    from pathlib import Path
    app_path = Path(__file__).parent.parent.parent / "dashboard" / "app.py"
    at = AppTest.from_file(str(app_path), default_timeout=120)
    at.run(timeout=120)
    assert not at.exception, f"Overview page threw exception: {at.exception}"

    pages = ["Opportunities", "Opportunity Detail", "Outliers", "Channels", "Costs"]
    for page in pages:
        at.sidebar.radio[0].set_value(page)
        at.run(timeout=120)
        assert not at.exception, f"Page '{page}' threw exception: {at.exception}"
