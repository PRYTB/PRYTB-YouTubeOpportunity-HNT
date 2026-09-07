"""
PRYTB Sprint 11 — Streamlit Dashboard MVP

Run with:
    .\\.venv\\Scripts\\streamlit.exe run dashboard\\app.py
"""

from __future__ import annotations

from pathlib import Path
import sys

# Force repository root to position 0 in sys.path to prevent namespace collision with dashboard/app.py
PROJECT_ROOT = str(Path(__file__).resolve().parents[1])
while PROJECT_ROOT in sys.path:
    sys.path.remove(PROJECT_ROOT)
sys.path.insert(0, PROJECT_ROOT)
assert sys.path[0] == PROJECT_ROOT

import app
import app.database.repositories

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
from dashboard.i18n import (
    t,
    format_enum_presentation,
    translate_column_header,
    format_number,
    DEFAULT_LANGUAGE,
    SUPPORTED_LANGUAGES,
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


@st.cache_data(show_spinner=False)
def load_dashboard_data() -> DashboardDataset:
    service = DashboardDataService()
    return service.get_dashboard_data()


def render_disclaimer(lang: str = DEFAULT_LANGUAGE):
    st.markdown(
        f"""
        <div class="disclaimer-box">
            <strong>{t("disclaimer.title", lang)}</strong><br/>
            {t("disclaimer.body", lang).replace('\n', '<br/>')}
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_provenance_banner(dataset: DashboardDataset, lang: str = DEFAULT_LANGUAGE):
    prov = dataset.provenance
    if not prov.is_compatible:
        st.error(
            f"🚫 **{t('provenance.blocked_title', lang)}**\n\n"
            f"{t('provenance.error', lang)}: {prov.error_message}\n\n"
            f"- {t('provenance.expected_dataset_hash', lang)}: `{CANONICAL_DATASET_HASH}`\n"
            f"- {t('provenance.actual_dataset_hash', lang)}: `{prov.dataset_hash}`\n"
            f"- {t('provenance.expected_assignments_hash', lang)}: `{CANONICAL_ASSIGNMENTS_HASH}`\n"
            f"- {t('provenance.actual_assignments_hash', lang)}: `{prov.assignments_hash}`"
        )
    else:
        with st.expander(t("provenance.expander_title", lang), expanded=False):
            col1, col2, col3 = st.columns(3)
            with col1:
                st.write(f"**{t('provenance.dataset_hash', lang)}:** `{prov.dataset_hash[:16]}...`")
                st.write(f"**{t('provenance.assignments_hash', lang)}:** `{prov.assignments_hash[:16]}...`")
            with col2:
                st.write(f"**{t('provenance.profitability_run', lang)}:** `{prov.profitability_run_id}`")
                st.write(f"**{t('provenance.validation_run', lang)}:** `{prov.validation_run_id}`")
            with col3:
                st.write(f"**{t('provenance.videos_in_contract', lang)}:** {prov.videos_count} / {CANONICAL_VIDEOS}")
                st.write(f"**{t('provenance.clusters_in_contract', lang)}:** {prov.clusters_count} / {CANONICAL_CLUSTERS}")


def page_overview(dataset: DashboardDataset, lang: str = DEFAULT_LANGUAGE):
    st.title(t("overview.title", lang))
    render_disclaimer(lang)
    render_provenance_banner(dataset, lang)

    st.subheader(t("overview.key_metrics", lang))
    m1, m2, m3, m4, m5, m6 = st.columns(6)
    m1.metric(t("overview.videos_analyzed", lang), format_number(dataset.total_videos, lang))
    m2.metric(t("overview.channels_analyzed", lang), format_number(dataset.total_channels, lang))
    m3.metric(t("overview.clusters_subniches", lang), format_number(dataset.total_clusters, lang))
    m4.metric(t("overview.outliers_identified", lang), format_number(dataset.total_outliers, lang))
    m5.metric(t("overview.validated_candidates", lang), format_number(len(dataset.candidates), lang))

    pass_cnt = dataset.status_counts.get("PASS", 0) + dataset.status_counts.get("PASS_WITH_WARNINGS", 0)
    m6.metric(t("overview.pass_pass_warnings", lang), format_number(pass_cnt, lang))

    st.markdown("---")

    col_left, col_right = st.columns(2)

    with col_left:
        st.subheader(t("overview.validation_status_dist", lang))
        status_df = pd.DataFrame(
            [
                {
                    translate_column_header("Status", lang): format_enum_presentation(st_val, lang),
                    translate_column_header("Count", lang): format_number(count, lang),
                }
                for st_val, count in dataset.status_counts.items()
            ]
        )
        st.dataframe(status_df, use_container_width=True, hide_index=True)

        st.subheader(t("overview.profitability_class_dist", lang))
        prof_df = pd.DataFrame(
            [
                {
                    translate_column_header("Classification", lang): format_enum_presentation(p_cls, lang),
                    translate_column_header("Count", lang): format_number(count, lang),
                }
                for p_cls, count in dataset.profitability_counts.items()
            ]
        )
        st.dataframe(prof_df, use_container_width=True, hide_index=True)

    with col_right:
        st.subheader(t("overview.api_resource_usage", lang))
        st.info(
            f"**{t('overview.yt_quota_usage', lang)}:** {t('overview.unavailable_sprint11', lang)}\n\n"
            f"**{t('overview.ai_model_usage', lang)}:** {t('overview.unavailable_sprint11', lang)}\n\n"
            f"**{t('overview.ai_cost_estimate', lang)}:** {t('overview.unavailable_sprint11', lang)}"
        )

        st.subheader(t("overview.score_distributions", lang))
        scores_data = []
        for c in dataset.candidates:
            scores_data.append(
                {
                    translate_column_header("Cluster", lang): f"{t('common.cluster', lang)} {c.cluster_id}",
                    translate_column_header("ValidationScore", lang): round(c.validation_score, 1),
                    translate_column_header("FragilityScore", lang): round(c.fragility_score, 1),
                    translate_column_header("FalsePositiveRisk", lang): round(c.false_positive_risk, 1),
                    translate_column_header("ValidationConfidence", lang): round(c.validation_confidence, 1),
                }
            )
        scores_df = pd.DataFrame(scores_data)
        st.dataframe(scores_df, use_container_width=True, hide_index=True)


def page_opportunities(dataset: DashboardDataset, lang: str = DEFAULT_LANGUAGE):
    st.title(t("opportunities.title", lang))
    st.caption(t("opportunities.caption", lang))

    # Sidebar / Header Filters
    with st.sidebar.expander(t("opportunities.filters", lang), expanded=True):
        status_options = sorted(list(set(c.validation_status.value for c in dataset.candidates)))
        selected_statuses = st.multiselect(
            t("opportunities.filter_val_status", lang),
            status_options,
            default=status_options,
            format_func=lambda s: format_enum_presentation(s, lang),
        )

        prof_options = sorted(list(set(c.profitability_classification.value for c in dataset.candidates)))
        selected_profs = st.multiselect(
            t("opportunities.filter_prof_class", lang),
            prof_options,
            default=prof_options,
            format_func=lambda p: format_enum_presentation(p, lang),
        )

        min_val_score = st.slider(t("opportunities.filter_min_val_score", lang), 0.0, 100.0, 0.0, 5.0)
        max_fp_risk = st.slider(t("opportunities.filter_max_fp_risk", lang), 0.0, 100.0, 100.0, 5.0)
        max_fragility = st.slider(t("opportunities.filter_max_fragility", lang), 0.0, 100.0, 100.0, 5.0)

        niche_options = sorted(list(set(c.niche for c in dataset.candidates if c.niche)))
        selected_niches = st.multiselect(t("opportunities.filter_niche", lang), niche_options, default=niche_options)

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

    st.write(
        t(
            "opportunities.showing_candidates",
            lang,
            filtered=format_number(len(filtered), lang),
            total=format_number(len(dataset.candidates), lang),
        )
    )

    if not filtered:
        st.warning(t("opportunities.no_matching", lang))
        return

    # Build Table DataFrame with translated headers and localized enum values
    table_data = []
    for c in filtered:
        table_data.append(
            {
                translate_column_header("Cluster", lang): c.cluster_id,
                translate_column_header("Niche / Microniche", lang): f"{c.niche} / {c.microniche}",
                translate_column_header("ProfitabilityScore", lang): round(c.profitability_score, 1),
                translate_column_header("Profitability Classification", lang): format_enum_presentation(c.profitability_classification, lang),
                translate_column_header("Profitability Confidence", lang): f"{round(c.profitability_confidence, 1)}%",
                translate_column_header("ValidationScore", lang): round(c.validation_score, 1),
                translate_column_header("ValidationStatus", lang): format_enum_presentation(c.validation_status, lang),
                translate_column_header("ValidationConfidence", lang): f"{round(c.validation_confidence, 1)}%",
                translate_column_header("FragilityScore", lang): round(c.fragility_score, 1),
                translate_column_header("FalsePositiveRisk", lang): round(c.false_positive_risk, 1),
                translate_column_header("Expected Views Base", lang): format_number(int(c.expected_views_base), lang),
                translate_column_header("Competition", lang): round(c.competition_score, 1),
                translate_column_header("Evergreen", lang): format_enum_presentation(c.evergreen_class, lang),
                translate_column_header("Production Attractiveness", lang): round(c.production_attractiveness, 1),
                translate_column_header("Risk", lang): format_enum_presentation(c.overall_production_risk, lang),
                translate_column_header("Coverage", lang): f"{round(c.coverage, 1)}%",
            }
        )

    df = pd.DataFrame(table_data)
    val_score_hdr = translate_column_header("ValidationScore", lang)
    prof_score_hdr = translate_column_header("ProfitabilityScore", lang)
    df = df.sort_values(by=[val_score_hdr, prof_score_hdr], ascending=[False, False])
    st.dataframe(df, use_container_width=True, hide_index=True)


def page_opportunity_detail(dataset: DashboardDataset, lang: str = DEFAULT_LANGUAGE):
    st.title(t("detail.title", lang))
    render_disclaimer(lang)

    cluster_ids = [c.cluster_id for c in dataset.candidates]
    if not cluster_ids:
        st.error(t("detail.no_candidates", lang))
        return

    selected_cid = st.sidebar.selectbox(
        t("detail.select_cluster", lang),
        options=cluster_ids,
        format_func=lambda cid: f"{t('common.cluster', lang)} {cid} — {next((c.subniche for c in dataset.candidates if c.cluster_id == cid), '')}",
    )

    cand = next((c for c in dataset.candidates if c.cluster_id == selected_cid), None)
    if not cand:
        st.error(t("detail.cluster_not_found", lang, cid=selected_cid))
        return

    # Header Badges & Info
    st.header(t("detail.cluster_header", lang, cid=cand.cluster_id, subniche=cand.subniche))
    st.subheader(t("detail.niche_microniche", lang, niche=cand.niche, microniche=cand.microniche))

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric(t("detail.val_status", lang), format_enum_presentation(cand.validation_status, lang))
    c2.metric(t("detail.val_score", lang), round(cand.validation_score, 1))
    c3.metric(t("detail.prof_score", lang), round(cand.profitability_score, 1))
    c4.metric(t("detail.fragility_score", lang), round(cand.fragility_score, 1))
    c5.metric(t("detail.fp_risk", lang), round(cand.false_positive_risk, 1))

    st.markdown("---")

    # Tabs for grouped evidence
    tab_exec, tab_prof, tab_val, tab_mkt, tab_prod, tab_econ, tab_vids = st.tabs(
        [
            t("tab.executive_summary", lang),
            t("tab.profitability", lang),
            t("tab.validator_sensitivity", lang),
            t("tab.market_competition", lang),
            t("tab.production_risk", lang),
            t("tab.economic_geography", lang),
            t("tab.supporting_videos", lang),
        ]
    )

    with tab_exec:
        st.subheader(t("exec.why_interesting", lang))
        if cand.positive_evidence:
            for ev in cand.positive_evidence:
                st.markdown(f"- ✅ {ev}")
        else:
            st.info(t("exec.no_positive", lang))

        st.subheader(t("exec.why_fail", lang))
        if cand.negative_evidence:
            for ev in cand.negative_evidence:
                st.markdown(f"- ❌ {ev}")
        else:
            st.success(t("exec.no_contradictory", lang))

        st.subheader(t("exec.missing_and_warnings", lang))
        if cand.missing_evidence:
            for ev in cand.missing_evidence:
                st.markdown(f"- ⚠️ **{t('exec.missing_evidence', lang)}:** {ev}")
        if cand.warnings:
            for w in cand.warnings:
                st.markdown(f"- ⚠️ **{t('exec.warning', lang)}:** {w}")
        if cand.critical_failures:
            for cf in cand.critical_failures:
                st.markdown(f"- 🚨 **{t('exec.critical_failure', lang)}:** {cf}")

    with tab_prof:
        st.subheader(t("prof.signals_title", lang))
        pc1, pc2, pc3, pc4 = st.columns(4)
        pc1.metric(t("detail.prof_score", lang), round(cand.profitability_score, 1))
        pc2.metric(t("prof.classification", lang), format_enum_presentation(cand.profitability_classification, lang))
        pc3.metric(t("prof.confidence", lang), f"{round(cand.profitability_confidence, 1)}%")
        pc4.metric(t("prof.coverage", lang), f"{round(cand.coverage, 1)}%")

        st.markdown(f"#### {t('prof.expected_views_dist', lang)}")
        v1, v2, v3 = st.columns(3)
        v1.metric(t("prof.low_views", lang), format_number(int(cand.expected_views_low), lang))
        v2.metric(t("prof.base_views", lang), format_number(int(cand.expected_views_base), lang))
        v3.metric(t("prof.high_views", lang), format_number(int(cand.expected_views_high), lang))

        st.markdown(f"#### {t('prof.revenue_benchmark_status', lang)}")
        st.warning(
            f"**{t('prof.dev_limitation', lang)}**:\n\n"
            f"- **{t('prof.rpm_benchmark_unavail', lang)}**\n"
            f"- **{t('prof.revenue_est_unavail', lang)}**\n"
            f"- **{t('prof.monetary_cost_unavail', lang)}**\n"
            f"- **{t('prof.expected_profit_unavail', lang)}**"
        )

    with tab_val:
        st.subheader(t("val.adversarial_results", lang))
        vc1, vc2, vc3, vc4 = st.columns(4)
        vc1.metric(t("detail.val_score", lang), round(cand.validation_score, 1))
        vc2.metric(t("val.val_confidence", lang), f"{round(cand.validation_confidence, 1)}%")
        vc3.metric(t("detail.fragility_score", lang), round(cand.fragility_score, 1))
        vc4.metric(t("detail.fp_risk", lang), round(cand.false_positive_risk, 1))

        st.markdown(f"#### {t('val.sensitivity_title', lang)}")
        sens_df = pd.DataFrame(
            [
                {translate_column_header("Metric", lang): t("sens.orig_prof_score", lang), translate_column_header("Score", lang): round(cand.original_profitability_score, 1)},
                {translate_column_header("Metric", lang): t("sens.score_no_top_video", lang), translate_column_header("Score", lang): round(cand.score_without_top_video, 1)},
                {translate_column_header("Metric", lang): t("sens.score_no_dom_channel", lang), translate_column_header("Score", lang): round(cand.score_without_dominant_channel, 1)},
                {translate_column_header("Metric", lang): t("sens.stress_adj_score", lang), translate_column_header("Score", lang): round(cand.stress_adjusted_score, 1)},
            ]
        )
        st.dataframe(sens_df, use_container_width=True, hide_index=True)

        st.markdown(f"#### {t('val.signal_stability', lang)}")
        st.write(f"- **{t('val.sample_adequacy', lang)}:** {round(cand.sample_adequacy, 1)} / 100")
        st.write(f"- **{t('val.cross_signal_consistency', lang)}:** {round(cand.cross_signal_consistency, 1)} / 100")
        st.write(f"- **{t('val.expected_views_stability', lang)}:** {round(cand.expected_views_stability, 1)} / 100")

    with tab_mkt:
        st.subheader(t("mkt.structure_title", lang))
        mc1, mc2, mc3, mc4 = st.columns(4)
        mc1.metric(t("mkt.competition_score", lang), round(cand.competition_score, 1))
        mc2.metric(t("mkt.accessibility", lang), format_enum_presentation(cand.accessibility, lang))
        mc3.metric(t("mkt.dom_channel_share", lang), f"{round(cand.dominant_channel_share, 1)}%")
        mc4.metric(t("mkt.top3_channel_share", lang), f"{round(cand.top_3_channel_share, 1)}%")

        mc5, mc6, mc7, mc8 = st.columns(4)
        mc5.metric(t("mkt.channel_hhi", lang), round(cand.channel_hhi, 1))
        mc6.metric(t("mkt.unique_channels", lang), format_number(cand.unique_channels, lang))
        mc7.metric(t("mkt.small_channel_success", lang), f"{round(cand.small_channel_success_rate, 1)}%")
        mc8.metric(t("mkt.outlier_diversity", lang), round(cand.outlier_diversity, 1))

        st.markdown(f"#### {t('mkt.evergreen_depth', lang)}")
        st.write(f"- **{t('mkt.evergreen_score', lang)}:** {round(cand.evergreen_score, 1)}")
        st.write(f"- **{t('mkt.evergreen_class', lang)}:** {format_enum_presentation(cand.evergreen_class, lang)}")
        st.write(f"- **{t('mkt.trend_score', lang)}:** {round(cand.trend_score, 1)}")
        st.write(f"- **{t('mkt.content_depth', lang)}:** `{format_enum_presentation(cand.content_depth_band, lang)}`")

    with tab_prod:
        st.subheader(t("prod.complexity_title", lang))
        pr1, pr2, pr3, pr4 = st.columns(4)
        pr1.metric(t("prod.complexity", lang), format_enum_presentation(cand.production_complexity, lang))
        pr2.metric(t("prod.cost_index", lang), round(cand.production_cost_index, 1))
        pr3.metric(t("prod.attractiveness", lang), round(cand.production_attractiveness, 1))
        pr4.metric(t("prod.overall_risk", lang), format_enum_presentation(cand.overall_production_risk, lang))

        st.markdown(f"#### {t('prod.feasibility_factors', lang)}")
        st.write(f"- **{t('prod.faceless_feasibility', lang)}:** {format_enum_presentation(cand.faceless_feasibility, lang)}")
        st.write(f"- **{t('prod.ai_assistance', lang)}:** {format_enum_presentation(cand.ai_assistance, lang)}")
        st.write(f"- **{t('prod.expertise_req', lang)}:** {format_enum_presentation(cand.expertise_requirement, lang)}")
        st.write(f"- **{t('prod.repeatability', lang)}:** {format_enum_presentation(cand.repeatability, lang)}")

        st.markdown(f"#### {t('prod.individual_risks', lang)}")
        st.write(f"- **{t('prod.copyright_risk', lang)}:** {format_enum_presentation(cand.copyright_risk, lang)}")
        st.write(f"- **{t('prod.platform_risk', lang)}:** {format_enum_presentation(cand.platform_risk, lang)}")
        st.write(f"- **{t('prod.accuracy_risk', lang)}:** {format_enum_presentation(cand.accuracy_risk, lang)}")
        st.write(f"- **{t('prod.update_burden', lang)}:** {format_enum_presentation(cand.update_burden, lang)}")
        st.write(f"- **{t('prod.source_dependency', lang)}:** {format_enum_presentation(cand.source_dependency, lang)}")

    with tab_econ:
        st.subheader(t("econ.value_title", lang))
        ec1, ec2, ec3, ec4 = st.columns(4)
        ec1.metric(t("econ.dom_language", lang), cand.dominant_language)
        ec2.metric(t("econ.market_tier", lang), cand.market_tier)
        ec3.metric(t("econ.audience_econ_val", lang), round(cand.audience_economic_value, 1))
        ec4.metric(t("econ.econ_confidence", lang), f"{round(cand.economic_confidence, 1)}%")

        st.write(f"- **{t('econ.benchmark_coverage', lang)}:** {round(cand.benchmark_coverage, 1)}%")
        st.write(f"- **{t('econ.long_form_count', lang)}:** {format_number(cand.long_form_count, lang)}")
        st.write(f"- **{t('econ.shorts_count', lang)}:** {format_number(cand.short_count, lang)}")

    with tab_vids:
        st.subheader(t("vids.supporting_title", lang, cid=selected_cid))
        cluster_vids = [v for v in dataset.videos if v.cluster_id == selected_cid]
        if not cluster_vids:
            st.info(t("vids.no_supporting", lang))
        else:
            v_data = []
            for v in cluster_vids:
                v_data.append(
                    {
                        translate_column_header("Title", lang): v.title,
                        translate_column_header("Channel", lang): v.channel_title,
                        translate_column_header("Views", lang): format_number(v.views, lang),
                        translate_column_header("Subscribers", lang): format_number(v.subscribers, lang) if v.subscribers is not None else t("common.na", lang),
                        translate_column_header("Published Date", lang): v.published_at[:10] if v.published_at else t("common.na", lang),
                        translate_column_header("Age (Days)", lang): round(v.video_age_days, 1) if v.video_age_days else t("common.na", lang),
                        translate_column_header("Outlier Ratio", lang): round(v.outlier_ratio, 2) if v.outlier_ratio else t("common.na", lang),
                        translate_column_header("Age-Norm Ratio", lang): round(v.age_normalized_outlier_ratio, 2) if v.age_normalized_outlier_ratio else t("common.na", lang),
                        translate_column_header("Velocity", lang): round(v.velocity, 1) if v.velocity else t("common.na", lang),
                        translate_column_header("Duration", lang): v.duration or t("common.na", lang),
                        translate_column_header("Type", lang): v.content_type,
                        translate_column_header("YouTube Link", lang): v.canonical_url or t("common.na", lang),
                    }
                )
            st.dataframe(pd.DataFrame(v_data), use_container_width=True, hide_index=True)


def page_outliers(dataset: DashboardDataset, lang: str = DEFAULT_LANGUAGE):
    st.title(t("outliers.title", lang))
    st.caption(t("outliers.caption", lang))

    # Show total identified outliers vs baseline population banner
    actual_outliers = [o for o in dataset.outliers if o.is_actual_outlier()]
    st.info(t("outliers.summary_banner", lang, count=len(actual_outliers), total=dataset.total_videos))

    with st.sidebar.expander(t("outliers.filters", lang), expanded=True):
        all_label = t("outliers.all_clusters", lang)
        cluster_opts = [all_label] + sorted(list(set(o.cluster_id for o in dataset.videos if o.cluster_id)))
        sel_cluster = st.selectbox(t("outliers.cluster_filter", lang), cluster_opts)

        only_actual = st.checkbox(t("outliers.only_actual_outliers", lang), value=True)
        min_outlier_ratio = st.slider(t("outliers.min_outlier_ratio", lang), 0.0, 50.0, 0.0, 1.0)

    outlier_res_map = {o.video_id: o for o in dataset.outliers}

    outliers_data = []
    for v in dataset.videos:
        if v.outlier_ratio is None:
            continue
        out_res = outlier_res_map.get(v.video_id)
        if only_actual and (not out_res or not out_res.is_actual_outlier()):
            continue
        if sel_cluster != all_label and v.cluster_id != sel_cluster:
            continue
        if v.outlier_ratio < min_outlier_ratio:
            continue

        outliers_data.append(
            {
                translate_column_header("Video", lang): v.title,
                translate_column_header("Channel", lang): v.channel_title,
                translate_column_header("Views", lang): format_number(v.views, lang),
                translate_column_header("Subscribers", lang): format_number(v.subscribers, lang) if v.subscribers is not None else t("common.na", lang),
                translate_column_header("Outlier Ratio", lang): round(v.outlier_ratio, 2),
                translate_column_header("Age-Norm Outlier Ratio", lang): round(v.age_normalized_outlier_ratio, 2) if v.age_normalized_outlier_ratio else t("common.na", lang),
                translate_column_header("Velocity (views/day)", lang): round(v.velocity, 1) if v.velocity else t("common.na", lang),
                translate_column_header("Cluster", lang): f"{t('common.cluster', lang)} {v.cluster_id}",
                translate_column_header("Niche", lang): v.niche,
                translate_column_header("YouTube Link", lang): v.canonical_url,
            }
        )

    if not outliers_data:
        st.warning(t("outliers.no_matching", lang))
        return

    df = pd.DataFrame(outliers_data)
    ratio_hdr = translate_column_header("Outlier Ratio", lang)
    df = df.sort_values(by=ratio_hdr, ascending=False)
    st.dataframe(df, use_container_width=True, hide_index=True)


def page_channels(dataset: DashboardDataset, lang: str = DEFAULT_LANGUAGE):
    st.title(t("channels.title", lang))
    st.caption(t("channels.caption", lang))

    ch_data = []
    for ch in dataset.channels:
        ch_data.append(
            {
                translate_column_header("Channel", lang): ch.channel_title,
                translate_column_header("Subscribers", lang): format_number(ch.subscribers, lang) if ch.subscribers is not None else t("common.na", lang),
                translate_column_header("Video Count in Dataset", lang): format_number(ch.video_count_in_dataset, lang),
                translate_column_header("Outlier Count", lang): format_number(ch.outlier_count, lang),
                translate_column_header("Clusters Represented", lang): ", ".join(f"#{c}" for c in ch.clusters_represented),
                translate_column_header("Median Performance (Views)", lang): format_number(int(ch.median_views), lang),
                translate_column_header("Small Channel (<=50k subs)", lang): t("common.yes", lang) if ch.is_small_channel else t("common.no", lang),
            }
        )

    df = pd.DataFrame(ch_data)
    out_cnt_hdr = translate_column_header("Outlier Count", lang)
    vid_cnt_hdr = translate_column_header("Video Count in Dataset", lang)
    df = df.sort_values(by=[out_cnt_hdr, vid_cnt_hdr], ascending=[False, False])
    st.dataframe(df, use_container_width=True, hide_index=True)


def page_costs(dataset: DashboardDataset, lang: str = DEFAULT_LANGUAGE):
    st.title(t("costs.title", lang))

    not_tracked_str = t("costs.not_tracked", lang)
    st.info(
        f"{t('costs.tracked_info_header', lang)}\n\n"
        f"- **{t('costs.yt_quota', lang)}:** `{not_tracked_str}`\n"
        f"- **{t('costs.ai_usage', lang)}:** `{not_tracked_str}`\n"
        f"- **{t('costs.ai_cost', lang)}:** `{not_tracked_str}`\n"
        f"- **{t('costs.data_runs', lang)}:** {t('costs.validation_run_desc', lang)} (`sprint10_val_96475cfe1e39`)\n"
    )

    st.markdown("---")

    st.subheader(t("costs.financial_status_header", lang))
    st.write(t("costs.financial_dev_desc", lang))


def main():
    # Language Selector in Sidebar above Navigation (Requirement 1)
    if "language" not in st.session_state:
        st.session_state["language"] = DEFAULT_LANGUAGE

    lang_code_map = {"Español": "es", "English": "en"}

    st.sidebar.title(t("app.nav_title", st.session_state["language"]))

    selected_lang_label = st.sidebar.selectbox(
        t("app.language_selector", st.session_state["language"]),
        options=list(SUPPORTED_LANGUAGES.values()),
        index=0 if st.session_state.get("language", DEFAULT_LANGUAGE) == "es" else 1,
        key="lang_selector",
    )
    st.session_state["language"] = lang_code_map.get(selected_lang_label, DEFAULT_LANGUAGE)
    lang = st.session_state["language"]

    if st.sidebar.button(t("app.refresh_data", lang)):
        st.cache_data.clear()
        st.rerun()

    nav_keys = [
        "Overview",
        "Opportunities",
        "Opportunity Detail",
        "Outliers",
        "Channels",
        "Costs",
    ]
    nav_map = {
        "Overview": t("nav.overview", lang),
        "Opportunities": t("nav.opportunities", lang),
        "Opportunity Detail": t("nav.opportunity_detail", lang),
        "Outliers": t("nav.outliers", lang),
        "Channels": t("nav.channels", lang),
        "Costs": t("nav.costs", lang),
    }

    page = st.sidebar.radio(
        t("app.go_to", lang),
        options=nav_keys,
        format_func=lambda k: nav_map[k],
    )

    with st.spinner(t("app.loading_data", lang)):
        dataset = load_dashboard_data()

    if page == "Overview":
        page_overview(dataset, lang)
    elif page == "Opportunities":
        page_opportunities(dataset, lang)
    elif page == "Opportunity Detail":
        page_opportunity_detail(dataset, lang)
    elif page == "Outliers":
        page_outliers(dataset, lang)
    elif page == "Channels":
        page_channels(dataset, lang)
    elif page == "Costs":
        page_costs(dataset, lang)


if __name__ == "__main__":
    main()
