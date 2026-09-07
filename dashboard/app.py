"""
PRYTB Sprint 11 — Streamlit Dashboard MVP

Run with:
    .\\.venv\\Scripts\\streamlit.exe run dashboard\\app.py
"""

from __future__ import annotations

import streamlit as st
import pandas as pd
from typing import List, Optional

from dashboard.data_service import (
    DashboardDataService,
    DashboardDataset,
    OpportunityCandidateViewModel,
    VideoViewModel,
    ChannelViewModel,
    CANONICAL_DATASET_HASH,
    CANONICAL_ASSIGNMENTS_HASH,
    CANONICAL_VIDEOS,
    CANONICAL_CLUSTERS,
)

# Set page config
st.set_page_config(
    page_title="PRYTB — Opportunity Intelligence Dashboard",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom Styling
st.markdown(
    """
    <style>
    .main .block-container {
        padding-top: 1.5rem;
        padding-bottom: 2rem;
    }
    .stMetric {
        background-color: #f8f9fa;
        padding: 0.75rem 1rem;
        border-radius: 0.5rem;
        border: 1px solid #e9ecef;
    }
    .disclaimer-box {
        background-color: #fff3cd;
        color: #856404;
        padding: 1rem;
        border-radius: 0.5rem;
        border-left: 5px solid #ffeeba;
        margin-bottom: 1.5rem;
        font-weight: 500;
    }
    .badge-pass {
        background-color: #d4edda;
        color: #155724;
        padding: 0.2rem 0.6rem;
        border-radius: 0.25rem;
        font-weight: bold;
    }
    .badge-watch {
        background-color: #fff3cd;
        color: #856404;
        padding: 0.2rem 0.6rem;
        border-radius: 0.25rem;
        font-weight: bold;
    }
    .badge-fail {
        background-color: #f8d7da;
        color: #721c24;
        padding: 0.2rem 0.6rem;
        border-radius: 0.25rem;
        font-weight: bold;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_data(show_spinner="Loading PRYTB Opportunity Intelligence Data...")
def load_dashboard_data() -> DashboardDataset:
    service = DashboardDataService()
    return service.get_dashboard_data()


def render_disclaimer():
    st.markdown(
        """
        <div class="disclaimer-box">
            <strong>⚠️ DEVELOPMENT DATASET</strong><br/>
            These rankings are for system validation on 83 canonical videos.<br/>
            They are not final market recommendations. Sprint 12 will run 10K–20K videos.
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_provenance_banner(dataset: DashboardDataset):
    prov = dataset.provenance
    if not prov.is_compatible:
        st.error(
            f"🚫 **PROVENANCE MISMATCH BLOCK**: Analytical ranking is blocked!\n\n"
            f"Error: {prov.error_message}\n\n"
            f"- Expected dataset hash: `{CANONICAL_DATASET_HASH}`\n"
            f"- Actual dataset hash: `{prov.dataset_hash}`\n"
            f"- Expected assignments hash: `{CANONICAL_ASSIGNMENTS_HASH}`\n"
            f"- Actual assignments hash: `{prov.assignments_hash}`"
        )
    else:
        with st.expander("ℹ️ Data Provenance & Production Contract", expanded=False):
            col1, col2, col3 = st.columns(3)
            with col1:
                st.write(f"**Dataset Hash:** `{prov.dataset_hash[:16]}...`")
                st.write(f"**Assignments Hash:** `{prov.assignments_hash[:16]}...`")
            with col2:
                st.write(f"**Profitability Run:** `{prov.profitability_run_id}`")
                st.write(f"**Validation Run:** `{prov.validation_run_id}`")
            with col3:
                st.write(f"**Videos in contract:** {prov.videos_count} / {CANONICAL_VIDEOS}")
                st.write(f"**Clusters in contract:** {prov.clusters_count} / {CANONICAL_CLUSTERS}")


def page_overview(dataset: DashboardDataset):
    st.title("🎯 Overview & Validation Summary")
    render_disclaimer()
    render_provenance_banner(dataset)

    st.subheader("Key Portfolio Metrics")
    m1, m2, m3, m4, m5, m6 = st.columns(6)
    m1.metric("Videos Analyzed", dataset.total_videos)
    m2.metric("Channels Analyzed", dataset.total_channels)
    m3.metric("Clusters / Subniches", dataset.total_clusters)
    m4.metric("Outliers Identified", dataset.total_outliers)
    m5.metric("Validated Candidates", len(dataset.candidates))
    
    pass_cnt = dataset.status_counts.get("PASS", 0) + dataset.status_counts.get("PASS_WITH_WARNINGS", 0)
    m6.metric("PASS / PASS_WITH_WARNINGS", pass_cnt)

    st.markdown("---")

    col_left, col_right = st.columns(2)

    with col_left:
        st.subheader("Sprint 10 Validation Status Distribution")
        status_df = pd.DataFrame(
            list(dataset.status_counts.items()), columns=["Status", "Count"]
        )
        st.dataframe(status_df, use_container_width=True)

        st.subheader("Profitability Classification Distribution")
        prof_df = pd.DataFrame(
            list(dataset.profitability_counts.items()), columns=["Classification", "Count"]
        )
        st.dataframe(prof_df, use_container_width=True)

    with col_right:
        st.subheader("API & Resource Usage")
        st.info(
            "**YouTube API Quota Usage:** Unavailable / Not tracked in Sprint 11\n\n"
            "**AI/Model Usage:** Unavailable / Not tracked in Sprint 11\n\n"
            "**AI Cost Estimate:** Unavailable / Not tracked in Sprint 11"
        )

        st.subheader("Score Metric Distributions")
        scores_data = []
        for c in dataset.candidates:
            scores_data.append(
                {
                    "Cluster": f"Cluster {c.cluster_id}",
                    "ValidationScore": round(c.validation_score, 1),
                    "FragilityScore": round(c.fragility_score, 1),
                    "FalsePositiveRisk": round(c.false_positive_risk, 1),
                    "ValidationConfidence": round(c.validation_confidence, 1),
                }
            )
        scores_df = pd.DataFrame(scores_data)
        st.dataframe(scores_df, use_container_width=True)


def page_opportunities(dataset: DashboardDataset):
    st.title("💡 Opportunity Candidates")
    st.caption("Sortable and filterable view of all cluster opportunity candidates.")

    # Sidebar / Header Filters
    with st.sidebar.expander("🔍 Filters", expanded=True):
        status_options = sorted(list(set(c.validation_status.value for c in dataset.candidates)))
        selected_statuses = st.multiselect("Validation Status", status_options, default=status_options)

        prof_options = sorted(list(set(c.profitability_classification.value for c in dataset.candidates)))
        selected_profs = st.multiselect("Profitability Classification", prof_options, default=prof_options)

        min_val_score = st.slider("Minimum Validation Score", 0.0, 100.0, 0.0, 5.0)
        max_fp_risk = st.slider("Maximum False Positive Risk", 0.0, 100.0, 100.0, 5.0)
        max_fragility = st.slider("Maximum Fragility Score", 0.0, 100.0, 100.0, 5.0)

        niche_options = sorted(list(set(c.niche for c in dataset.candidates if c.niche)))
        selected_niches = st.multiselect("Niche", niche_options, default=niche_options)

    # Filter data
    filtered: List[OpportunityCandidateViewModel] = []
    for c in dataset.candidates:
        if c.validation_status.value not in selected_statuses:
            continue
        if c.profitability_classification.value not in selected_profs:
            continue
        if c.validation_score < min_val_score:
            continue
        if c.false_positive_risk > max_fp_risk:
            continue
        if c.fragility_score > max_fragility:
            continue
        if selected_niches and c.niche not in selected_niches:
            continue
        filtered.append(c)

    st.write(f"Showing **{len(filtered)}** of **{len(dataset.candidates)}** candidates.")

    if not filtered:
        st.warning("No candidates match the selected filter criteria.")
        return

    # Build Table DataFrame
    table_data = []
    for c in filtered:
        table_data.append(
            {
                "Cluster": c.cluster_id,
                "Niche / Microniche": f"{c.niche} / {c.microniche}",
                "ProfitabilityScore": round(c.profitability_score, 1),
                "Profitability Classification": c.profitability_classification.value,
                "Profitability Confidence": f"{round(c.profitability_confidence, 1)}%",
                "ValidationScore": round(c.validation_score, 1),
                "ValidationStatus": c.validation_status.value,
                "ValidationConfidence": f"{round(c.validation_confidence, 1)}%",
                "FragilityScore": round(c.fragility_score, 1),
                "FalsePositiveRisk": round(c.false_positive_risk, 1),
                "Expected Views Base": f"{int(c.expected_views_base):,}",
                "Competition": round(c.competition_score, 1),
                "Evergreen": c.evergreen_class.value,
                "Production Attractiveness": round(c.production_attractiveness, 1),
                "Risk": c.overall_production_risk.value,
                "Coverage": f"{round(c.coverage, 1)}%",
            }
        )

    df = pd.DataFrame(table_data)
    # Default sorting favoring validation strength
    df = df.sort_values(by=["ValidationScore", "ProfitabilityScore"], ascending=[False, False])
    st.dataframe(df, use_container_width=True, hide_index=True)


def page_opportunity_detail(dataset: DashboardDataset):
    st.title("🔎 Opportunity Detail & Underlying Evidence")
    render_disclaimer()

    cluster_ids = [c.cluster_id for c in dataset.candidates]
    if not cluster_ids:
        st.error("No opportunity candidates available.")
        return

    selected_cid = st.sidebar.selectbox(
        "Select Cluster",
        options=cluster_ids,
        format_func=lambda cid: f"Cluster {cid} — {next((c.subniche for c in dataset.candidates if c.cluster_id == cid), '')}",
    )

    cand = next((c for c in dataset.candidates if c.cluster_id == selected_cid), None)
    if not cand:
        st.error(f"Cluster {selected_cid} not found.")
        return

    # Header Badges
    st.header(f"Cluster #{cand.cluster_id}: {cand.subniche}")
    st.subheader(f"Niche: {cand.niche} | Microniche: {cand.microniche}")

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Validation Status", cand.validation_status.value)
    c2.metric("Validation Score", round(cand.validation_score, 1))
    c3.metric("Profitability Score", round(cand.profitability_score, 1))
    c4.metric("Fragility Score", round(cand.fragility_score, 1))
    c5.metric("False Positive Risk", round(cand.false_positive_risk, 1))

    st.markdown("---")

    # Tabs for grouped evidence
    tab_exec, tab_prof, tab_val, tab_mkt, tab_prod, tab_econ, tab_vids = st.tabs(
        [
            "📋 Executive Summary",
            "💰 Profitability",
            "🛡️ Validator & Sensitivity",
            "📊 Market & Competition",
            "⚙️ Production Risk",
            "🌍 Economic / Geography",
            "🎬 Supporting Videos",
        ]
    )

    with tab_exec:
        st.subheader("Why this candidate is interesting (Positive Evidence)")
        if cand.positive_evidence:
            for ev in cand.positive_evidence:
                st.markdown(f"- ✅ {ev}")
        else:
            st.info("No positive evidence listed.")

        st.subheader("Why it may fail (Contradictory / Negative Evidence)")
        if cand.negative_evidence:
            for ev in cand.negative_evidence:
                st.markdown(f"- ❌ {ev}")
        else:
            st.success("No critical contradictory evidence noted.")

        st.subheader("Missing Evidence & Warnings")
        if cand.missing_evidence:
            for ev in cand.missing_evidence:
                st.markdown(f"- ⚠️ **Missing Evidence:** {ev}")
        if cand.warnings:
            for w in cand.warnings:
                st.markdown(f"- ⚠️ **Warning:** {w}")
        if cand.critical_failures:
            for cf in cand.critical_failures:
                st.markdown(f"- 🚨 **Critical Failure:** {cf}")

    with tab_prof:
        st.subheader("Profitability & Monetization Signals")
        pc1, pc2, pc3, pc4 = st.columns(4)
        pc1.metric("Profitability Score", round(cand.profitability_score, 1))
        pc2.metric("Classification", cand.profitability_classification.value)
        pc3.metric("Confidence", f"{round(cand.profitability_confidence, 1)}%")
        pc4.metric("Component Coverage", f"{round(cand.coverage, 1)}%")

        st.markdown("#### Expected Views Distribution")
        v1, v2, v3 = st.columns(3)
        v1.metric("Low Expected Views", f"{int(cand.expected_views_low):,}")
        v2.metric("Base Expected Views", f"{int(cand.expected_views_base):,}")
        v3.metric("High Expected Views", f"{int(cand.expected_views_high):,}")

        st.markdown("#### Revenue & Benchmark Status")
        st.warning(
            "⚠️ **DEVELOPMENT DATASET LIMITATION**:\n\n"
            "- **RPM benchmark:** `Unavailable` (No production RPM benchmark in Sprint 11)\n"
            "- **Revenue estimate:** `Unavailable` (Do not display $0)\n"
            "- **Monetary cost:** `Unavailable` (Do not display $0)\n"
            "- **Expected profit:** `Unavailable` (Do not display $0)"
        )

    with tab_val:
        st.subheader("Adversarial Validation Results")
        vc1, vc2, vc3, vc4 = st.columns(4)
        vc1.metric("Validation Score", round(cand.validation_score, 1))
        vc2.metric("Validation Confidence", f"{round(cand.validation_confidence, 1)}%")
        vc3.metric("Fragility Score", round(cand.fragility_score, 1))
        vc4.metric("False Positive Risk", round(cand.false_positive_risk, 1))

        st.markdown("#### Sensitivity Analysis & Stress Tests")
        sens_df = pd.DataFrame(
            [
                {"Metric": "Original Profitability Score", "Score": round(cand.original_profitability_score, 1)},
                {"Metric": "Score Without Top Video", "Score": round(cand.score_without_top_video, 1)},
                {"Metric": "Score Without Dominant Channel", "Score": round(cand.score_without_dominant_channel, 1)},
                {"Metric": "Stress-Adjusted Score", "Score": round(cand.stress_adjusted_score, 1)},
            ]
        )
        st.dataframe(sens_df, use_container_width=True, hide_index=True)

        st.markdown("#### Signal Stability Metrics")
        st.write(f"- **Sample Adequacy:** {round(cand.sample_adequacy, 1)} / 100")
        st.write(f"- **Cross-Signal Consistency:** {round(cand.cross_signal_consistency, 1)} / 100")
        st.write(f"- **Expected Views Stability:** {round(cand.expected_views_stability, 1)} / 100")

    with tab_mkt:
        st.subheader("Market Structure & Competition (Sprint 7)")
        mc1, mc2, mc3, mc4 = st.columns(4)
        mc1.metric("Competition Score", round(cand.competition_score, 1))
        mc2.metric("Entry Accessibility", cand.accessibility.value)
        mc3.metric("Dominant Channel Share", f"{round(cand.dominant_channel_share, 1)}%")
        mc4.metric("Top 3 Channel Share", f"{round(cand.top_3_channel_share, 1)}%")

        mc5, mc6, mc7, mc8 = st.columns(4)
        mc5.metric("Channel HHI", round(cand.channel_hhi, 1))
        mc6.metric("Unique Channels", cand.unique_channels)
        mc7.metric("Small Channel Success", f"{round(cand.small_channel_success_rate, 1)}%")
        mc8.metric("Outlier Diversity", round(cand.outlier_diversity, 1))

        st.markdown("#### Evergreen & Content Depth")
        st.write(f"- **Evergreen Score:** {round(cand.evergreen_score, 1)}")
        st.write(f"- **Evergreen Class:** {cand.evergreen_class.value}")
        st.write(f"- **Trend Score:** {round(cand.trend_score, 1)}")
        st.write(f"- **Content Depth:** `{cand.content_depth_band.value}`")

    with tab_prod:
        st.subheader("Production Complexity & Risk (Sprint 8)")
        pr1, pr2, pr3, pr4 = st.columns(4)
        pr1.metric("Production Complexity", cand.production_complexity.value)
        pr2.metric("Production Cost Index", round(cand.production_cost_index, 1))
        pr3.metric("Attractiveness Score", round(cand.production_attractiveness, 1))
        pr4.metric("Overall Risk Level", cand.overall_production_risk.value)

        st.markdown("#### Feasibility & Operating Factors")
        st.write(f"- **Faceless Feasibility:** {cand.faceless_feasibility.value}")
        st.write(f"- **AI Assistance Potential:** {cand.ai_assistance.value}")
        st.write(f"- **Expertise Requirement:** {cand.expertise_requirement.value}")
        st.write(f"- **Repeatability Band:** {cand.repeatability.value}")

        st.markdown("#### Individual Risk Levels")
        st.write(f"- **Copyright Risk:** {cand.copyright_risk.value}")
        st.write(f"- **Platform Risk:** {cand.platform_risk.value}")
        st.write(f"- **Accuracy Risk:** {cand.accuracy_risk.value}")
        st.write(f"- **Update Burden:** {cand.update_burden.value}")
        st.write(f"- **Source Dependency:** {cand.source_dependency.value}")

    with tab_econ:
        st.subheader("Economic Value & Geography (Sprint 6)")
        ec1, ec2, ec3, ec4 = st.columns(4)
        ec1.metric("Dominant Language", cand.dominant_language)
        ec2.metric("Primary Market Tier", cand.market_tier)
        ec3.metric("Audience Economic Value", round(cand.audience_economic_value, 1))
        ec4.metric("Economic Confidence", f"{round(cand.economic_confidence, 1)}%")

        st.write(f"- **Benchmark Coverage:** {round(cand.benchmark_coverage, 1)}%")
        st.write(f"- **Long-form Count:** {cand.long_form_count}")
        st.write(f"- **Shorts Count:** {cand.short_count}")

    with tab_vids:
        st.subheader(f"Supporting Videos for Cluster #{selected_cid}")
        cluster_vids = [v for v in dataset.videos if v.cluster_id == selected_cid]
        if not cluster_vids:
            st.info("No supporting videos found for this cluster.")
        else:
            v_data = []
            for v in cluster_vids:
                v_data.append(
                    {
                        "Title": v.title,
                        "Channel": v.channel_title,
                        "Views": f"{v.views:,}",
                        "Subscribers": f"{v.subscribers:,}" if v.subscribers is not None else "N/A",
                        "Published Date": v.published_at[:10] if v.published_at else "N/A",
                        "Age (Days)": round(v.video_age_days, 1) if v.video_age_days else "N/A",
                        "Outlier Ratio": round(v.outlier_ratio, 2) if v.outlier_ratio else "N/A",
                        "Age-Norm Ratio": round(v.age_normalized_outlier_ratio, 2) if v.age_normalized_outlier_ratio else "N/A",
                        "Velocity": round(v.velocity, 1) if v.velocity else "N/A",
                        "Duration": v.duration or "N/A",
                        "Type": v.content_type,
                        "YouTube Link": v.canonical_url or "N/A",
                    }
                )
            st.dataframe(pd.DataFrame(v_data), use_container_width=True, hide_index=True)


def page_outliers(dataset: DashboardDataset):
    st.title("🚀 Outlier Videos")
    st.caption("Strongest video outliers ordered by outlier evidence.")

    with st.sidebar.expander("🔍 Outlier Filters", expanded=True):
        cluster_opts = ["All"] + sorted(list(set(o.cluster_id for o in dataset.videos if o.cluster_id)))
        sel_cluster = st.selectbox("Cluster Filter", cluster_opts)

        min_outlier_ratio = st.slider("Minimum Outlier Ratio", 0.0, 50.0, 0.0, 1.0)

    outliers_data = []
    for v in dataset.videos:
        if v.outlier_ratio is None:
            continue
        if sel_cluster != "All" and v.cluster_id != sel_cluster:
            continue
        if v.outlier_ratio < min_outlier_ratio:
            continue

        outliers_data.append(
            {
                "Video": v.title,
                "Channel": v.channel_title,
                "Views": v.views,
                "Subscribers": v.subscribers if v.subscribers is not None else "N/A",
                "Outlier Ratio": round(v.outlier_ratio, 2),
                "Age-Norm Outlier Ratio": round(v.age_normalized_outlier_ratio, 2) if v.age_normalized_outlier_ratio else "N/A",
                "Velocity (views/day)": round(v.velocity, 1) if v.velocity else "N/A",
                "Cluster": f"Cluster {v.cluster_id}",
                "Niche": v.niche,
                "YouTube Link": v.canonical_url,
            }
        )

    if not outliers_data:
        st.warning("No outliers match the filter criteria.")
        return

    df = pd.DataFrame(outliers_data)
    df = df.sort_values(by="Outlier Ratio", ascending=False)
    st.dataframe(df, use_container_width=True, hide_index=True)


def page_channels(dataset: DashboardDataset):
    st.title("📺 Emerging & Relevant Channels")
    st.caption("Channels represented across opportunity clusters in the canonical dataset.")

    ch_data = []
    for ch in dataset.channels:
        ch_data.append(
            {
                "Channel": ch.channel_title,
                "Subscribers": f"{ch.subscribers:,}" if ch.subscribers is not None else "N/A",
                "Video Count in Dataset": ch.video_count_in_dataset,
                "Outlier Count": ch.outlier_count,
                "Clusters Represented": ", ".join(f"#{c}" for c in ch.clusters_represented),
                "Median Performance (Views)": f"{int(ch.median_views):,}",
                "Small Channel (<=50k subs)": "Yes" if ch.is_small_channel else "No",
            }
        )

    df = pd.DataFrame(ch_data)
    df = df.sort_values(by=["Outlier Count", "Video Count in Dataset"], ascending=[False, False])
    st.dataframe(df, use_container_width=True, hide_index=True)


def page_costs(dataset: DashboardDataset):
    st.title("💳 API & Resource Usage")

    st.info(
        "### Tracked Resource Information\n\n"
        "- **YouTube API Quota Usage:** `Not tracked / unavailable`\n"
        "- **AI / Model Usage:** `Not tracked / unavailable`\n"
        "- **AI / Model Estimated Cost:** `Not tracked / unavailable`\n"
        "- **Data Collection Runs:** 1 validation run (`sprint10_val_96475cfe1e39`)\n"
    )

    st.markdown("---")

    st.subheader("Financial & Revenue Benchmark Status")
    st.write(
        "In this development dataset (83 videos, 10 clusters):\n\n"
        "- **Production monetary cost:** `Unavailable`\n"
        "- **RPM benchmarks:** `Unavailable`\n"
        "- **Estimated revenue:** `Unavailable`\n"
        "- **Expected net profit:** `Unavailable`\n\n"
        "*No dummy monetary values ($0) or fake cost estimates are fabricated in accordance with PRYTB transparency guidelines.*"
    )


def main():
    st.sidebar.title("🎯 PRYTB Navigation")
    
    if st.sidebar.button("🔄 Refresh Data"):
        st.cache_data.clear()
        st.rerun()

    page = st.sidebar.radio(
        "Go to",
        options=[
            "Overview",
            "Opportunities",
            "Opportunity Detail",
            "Outliers",
            "Channels",
            "Costs",
        ],
    )

    dataset = load_dashboard_data()

    if page == "Overview":
        page_overview(dataset)
    elif page == "Opportunities":
        page_opportunities(dataset)
    elif page == "Opportunity Detail":
        page_opportunity_detail(dataset)
    elif page == "Outliers":
        page_outliers(dataset)
    elif page == "Channels":
        page_channels(dataset)
    elif page == "Costs":
        page_costs(dataset)


if __name__ == "__main__":
    main()
