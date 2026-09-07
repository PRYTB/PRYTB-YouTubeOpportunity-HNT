"""
PRYTB Centralized Internationalization (I18n) Module.

Provides translation dictionaries, helpers, presentation layer enum mappings,
and localized table column / numeric formatting for English and Spanish.
"""

from __future__ import annotations
from typing import Any, Dict, Optional, Union
from enum import Enum


DEFAULT_LANGUAGE = "es"
SUPPORTED_LANGUAGES = {
    "es": "Español",
    "en": "English",
}

TRANSLATIONS: Dict[str, Dict[str, str]] = {
    "es": {
        # General & App Metadata
        "app.title": "PRYTB — Dashboard de Inteligencia de Oportunidades",
        "app.nav_title": "🎯 Navegación PRYTB",
        "app.language_selector": "Language / Idioma",
        "app.refresh_data": "🔄 Actualizar datos",
        "app.loading_data": "Cargando datos de inteligencia de oportunidades de PRYTB...",
        "app.go_to": "Ir a",

        # Navigation Pages
        "nav.overview": "Resumen General",
        "nav.opportunities": "Oportunidades",
        "nav.opportunity_detail": "Detalle de Oportunidad",
        "nav.outliers": "Outliers",
        "nav.channels": "Canales",
        "nav.costs": "Costos",

        # Development Disclaimer
        "disclaimer.title": "⚠️ DATASET DE DESARROLLO",
        "disclaimer.body": (
            "Estas clasificaciones corresponden a la validación del sistema sobre 83 videos canónicos.\n"
            "No constituyen recomendaciones finales de mercado. Sprint 12 analizará entre 10.000 y 20.000 videos."
        ),

        # Provenance Banner
        "provenance.blocked_title": "🚫 BLOQUEO POR DESINCONCORDANCIA DE PROCEDENCIA: ¡El ranking analítico está bloqueado!",
        "provenance.error": "Error",
        "provenance.expected_dataset_hash": "Hash de dataset esperado",
        "provenance.actual_dataset_hash": "Hash de dataset actual",
        "provenance.expected_assignments_hash": "Hash de asignaciones esperado",
        "provenance.actual_assignments_hash": "Hash de asignaciones actual",
        "provenance.expander_title": "ℹ️ Procedencia de datos y contrato de producción",
        "provenance.dataset_hash": "Hash de Dataset",
        "provenance.assignments_hash": "Hash de Asignaciones",
        "provenance.profitability_run": "Ejecución de Rentabilidad",
        "provenance.validation_run": "Ejecución de Validación",
        "provenance.videos_in_contract": "Videos en contrato",
        "provenance.clusters_in_contract": "Clusters en contrato",

        # Overview Page
        "overview.title": "🎯 Resumen general y validación",
        "overview.key_metrics": "Métricas clave del portafolio",
        "overview.videos_analyzed": "Videos analizados",
        "overview.channels_analyzed": "Canales analizados",
        "overview.clusters_subniches": "Clusters / Subnichos",
        "overview.outliers_identified": "Outliers identificados",
        "overview.validated_candidates": "Candidatos validados",
        "overview.pass_pass_warnings": "APROBADO / CON ADVERTENCIAS",

        "overview.validation_status_dist": "Distribución de estado de validación (Sprint 10)",
        "overview.profitability_class_dist": "Distribución de clasificación de rentabilidad",
        "overview.api_resource_usage": "Uso de API y recursos",
        "overview.score_distributions": "Distribución de métricas de puntuación",

        "overview.yt_quota_usage": "Uso de cuota API de YouTube",
        "overview.ai_model_usage": "Uso de IA / Modelos",
        "overview.ai_cost_estimate": "Estimación de costo de IA",
        "overview.unavailable_sprint11": "No disponible / No rastreado en Sprint 11",

        # Opportunities Page
        "opportunities.title": "💡 Candidatos a oportunidad",
        "opportunities.caption": "Vista ordenable y filtrable de todos los candidatos a oportunidad de clusters.",
        "opportunities.filters": "🔍 Filtros",
        "opportunities.filter_val_status": "Estado de validación",
        "opportunities.filter_prof_class": "Clasificación de rentabilidad",
        "opportunities.filter_min_val_score": "Puntaje mínimo de validación",
        "opportunities.filter_max_fp_risk": "Riesgo máximo de falso positivo",
        "opportunities.filter_max_fragility": "Puntaje máximo de fragilidad",
        "opportunities.filter_niche": "Nicho",
        "opportunities.showing_candidates": "Mostrando {filtered} de {total} candidatos.",
        "opportunities.no_matching": "Ningún candidato coincide con los criterios de filtro seleccionados.",

        # Opportunity Detail Page
        "detail.title": "🔎 Detalle de oportunidad y evidencia subyacente",
        "detail.no_candidates": "No hay candidatos a oportunidad disponibles.",
        "detail.select_cluster": "Seleccionar cluster",
        "detail.cluster_not_found": "Cluster {cid} no encontrado.",
        "detail.cluster_header": "Cluster #{cid}: {subniche}",
        "detail.niche_microniche": "Nicho: {niche} | Micronicho: {microniche}",

        # Detail Metrics
        "detail.val_status": "Estado de validación",
        "detail.val_score": "Puntaje de validación",
        "detail.prof_score": "Puntaje de rentabilidad",
        "detail.fragility_score": "Puntaje de fragilidad",
        "detail.fp_risk": "Riesgo de falso positivo",

        # Tabs
        "tab.executive_summary": "📋 Resumen ejecutivo",
        "tab.profitability": "💰 Rentabilidad",
        "tab.validator_sensitivity": "🛡️ Validador y sensibilidad",
        "tab.market_competition": "📊 Mercado y competencia",
        "tab.production_risk": "⚙️ Riesgo de producción",
        "tab.economic_geography": "🌍 Económico / Geografía",
        "tab.supporting_videos": "🎬 Videos de soporte",

        # Executive Summary Tab
        "exec.why_interesting": "Por qué este candidato es interesante (Evidencia positiva)",
        "exec.no_positive": "Sin evidencia positiva registrada.",
        "exec.why_fail": "Por qué podría fallar (Evidencia contradictoria / negativa)",
        "exec.no_contradictory": "Sin evidencia contradictoria crítica registrada.",
        "exec.missing_and_warnings": "Evidencia faltante y advertencias",
        "exec.missing_evidence": "Evidencia faltante",
        "exec.warning": "Advertencia",
        "exec.critical_failure": "Falla crítica",

        # Profitability Tab
        "prof.signals_title": "Señales de rentabilidad y monetización",
        "prof.classification": "Clasificación",
        "prof.confidence": "Confianza",
        "prof.coverage": "Cobertura de componentes",
        "prof.expected_views_dist": "Distribución de vistas esperadas",
        "prof.low_views": "Vistas esperadas bajas",
        "prof.base_views": "Vistas esperadas base",
        "prof.high_views": "Vistas esperadas altas",
        "prof.revenue_benchmark_status": "Estado de ingresos y benchmarks",
        "prof.dev_limitation": "⚠️ LIMITACIÓN DEL DATASET DE DESARROLLO",
        "prof.rpm_benchmark_unavail": "Benchmark RPM: No disponible (Sin benchmark RPM de producción en Sprint 11)",
        "prof.revenue_est_unavail": "Estimación de ingresos: No disponible (No mostrar $0)",
        "prof.monetary_cost_unavail": "Costo monetario: No disponible (No mostrar $0)",
        "prof.expected_profit_unavail": "Ganancia esperada: No disponible (No mostrar $0)",

        # Validator & Sensitivity Tab
        "val.adversarial_results": "Resultados de validación adversarial",
        "val.val_confidence": "Confianza de validación",
        "val.sensitivity_title": "Análisis de sensibilidad y pruebas de estrés",
        "val.signal_stability": "Métricas de estabilidad de señal",
        "val.sample_adequacy": "Adecuación de la muestra",
        "val.cross_signal_consistency": "Consistencia entre señales",
        "val.expected_views_stability": "Estabilidad de vistas esperadas",

        # Sensitivity Metrics Labels
        "sens.orig_prof_score": "Puntaje de rentabilidad original",
        "sens.score_no_top_video": "Puntaje sin el video principal",
        "sens.score_no_dom_channel": "Puntaje sin el canal dominante",
        "sens.stress_adj_score": "Puntaje ajustado por estrés",

        # Market & Competition Tab
        "mkt.structure_title": "Estructura de mercado y competencia (Sprint 7)",
        "mkt.competition_score": "Puntaje de competencia",
        "mkt.accessibility": "Accesibilidad de entrada",
        "mkt.dom_channel_share": "Cuota del canal dominante",
        "mkt.top3_channel_share": "Cuota de los top 3 canales",
        "mkt.channel_hhi": "HHI de canales",
        "mkt.unique_channels": "Canales únicos",
        "mkt.small_channel_success": "Éxito de canales pequeños",
        "mkt.outlier_diversity": "Diversidad de outliers",
        "mkt.evergreen_depth": "Evergreen y profundidad de contenido",
        "mkt.evergreen_score": "Puntaje evergreen",
        "mkt.evergreen_class": "Clase evergreen",
        "mkt.trend_score": "Puntaje de tendencia",
        "mkt.content_depth": "Profundidad de contenido",

        # Production Risk Tab
        "prod.complexity_title": "Complejidad de producción y riesgo (Sprint 8)",
        "prod.complexity": "Complejidad de producción",
        "prod.cost_index": "Índice de costo de producción",
        "prod.attractiveness": "Puntaje de atractividad",
        "prod.overall_risk": "Nivel de riesgo general",
        "prod.feasibility_factors": "Factores de factibilidad y operación",
        "prod.faceless_feasibility": "Factibilidad faceless",
        "prod.ai_assistance": "Potencial de asistencia de IA",
        "prod.expertise_req": "Requerimiento de experiencia",
        "prod.repeatability": "Banda de repetibilidad",
        "prod.individual_risks": "Niveles de riesgo individual",
        "prod.copyright_risk": "Riesgo de derechos de autor",
        "prod.platform_risk": "Riesgo de plataforma",
        "prod.accuracy_risk": "Riesgo de precisión",
        "prod.update_burden": "Carga de actualización",
        "prod.source_dependency": "Dependencia de fuentes",

        # Economic & Geography Tab
        "econ.value_title": "Valor económico y geografía (Sprint 6)",
        "econ.dom_language": "Idioma dominante",
        "econ.market_tier": "Nivel de mercado principal",
        "econ.audience_econ_val": "Valor económico de audiencia",
        "econ.econ_confidence": "Confianza económica",
        "econ.benchmark_coverage": "Cobertura de benchmark",
        "econ.long_form_count": "Conteo de formato largo",
        "econ.shorts_count": "Conteo de Shorts",

        # Supporting Videos Tab
        "vids.supporting_title": "Videos de soporte para Cluster #{cid}",
        "vids.no_supporting": "No se encontraron videos de soporte para este cluster.",

        # Outliers Page
        "outliers.title": "🚀 Videos outliers",
        "outliers.caption": "Outliers de video más fuertes ordenados por evidencia de outlier.",
        "outliers.summary_banner": "Población total de outliers identificados: {count} videos (de {total} videos de producción analizados).",
        "outliers.filters": "🔍 Filtros de outliers",
        "outliers.all_clusters": "Todos",
        "outliers.cluster_filter": "Filtro de cluster",
        "outliers.only_actual_outliers": "Solo outliers reales (is_strong / is_major / is_extreme)",
        "outliers.min_outlier_ratio": "Ratio mínimo de outlier",
        "outliers.no_matching": "Ningún outlier coincide con los criterios de filtro.",

        # Channels Page
        "channels.title": "📺 Canales emergentes y relevantes",
        "channels.caption": "Canales representados a través de clusters de oportunidad en el dataset canónico.",

        # Costs Page
        "costs.title": "💳 Uso de API y recursos",
        "costs.tracked_info_header": "### Información de recursos rastreados",
        "costs.yt_quota": "Uso de cuota API de YouTube",
        "costs.ai_usage": "Uso de IA / Modelos",
        "costs.ai_cost": "Costo estimado de IA / Modelos",
        "costs.data_runs": "Ejecuciones de recolección de datos",
        "costs.not_tracked": "No rastreado / no disponible",
        "costs.validation_run_desc": "1 ejecución de validación",
        "costs.financial_status_header": "Estado de benchmarks financieros y de ingresos",
        "costs.financial_dev_desc": (
            "En este dataset de desarrollo (83 videos, 10 clusters):\n\n"
            "- **Costo monetario de producción:** `No disponible`\n"
            "- **Benchmarks RPM:** `No disponible`\n"
            "- **Ingresos estimados:** `No disponible`\n"
            "- **Ganancia neta esperada:** `No disponible`\n\n"
            "*No se fabrican valores monetarios ficticios ($0) ni estimaciones falsas de costo de acuerdo con los lineamientos de transparencia de PRYTB.*"
        ),

        # Common Labels
        "common.yes": "Sí",
        "common.no": "No",
        "common.na": "N/A",
        "common.cluster": "Cluster",
        "common.cluster_n": "Cluster {cid}",
    },

    "en": {
        # General & App Metadata
        "app.title": "PRYTB — Opportunity Intelligence Dashboard",
        "app.nav_title": "🎯 PRYTB Navigation",
        "app.language_selector": "Language / Idioma",
        "app.refresh_data": "🔄 Refresh Data",
        "app.loading_data": "Loading PRYTB Opportunity Intelligence Data...",
        "app.go_to": "Go to",

        # Navigation Pages
        "nav.overview": "Overview",
        "nav.opportunities": "Opportunities",
        "nav.opportunity_detail": "Opportunity Detail",
        "nav.outliers": "Outliers",
        "nav.channels": "Channels",
        "nav.costs": "Costs",

        # Development Disclaimer
        "disclaimer.title": "⚠️ DEVELOPMENT DATASET",
        "disclaimer.body": (
            "These rankings are for system validation on 83 canonical videos.\n"
            "They are not final market recommendations. Sprint 12 will run 10K–20K videos."
        ),

        # Provenance Banner
        "provenance.blocked_title": "🚫 PROVENANCE MISMATCH BLOCK: Analytical ranking is blocked!",
        "provenance.error": "Error",
        "provenance.expected_dataset_hash": "Expected dataset hash",
        "provenance.actual_dataset_hash": "Actual dataset hash",
        "provenance.expected_assignments_hash": "Expected assignments hash",
        "provenance.actual_assignments_hash": "Actual assignments hash",
        "provenance.expander_title": "ℹ️ Data Provenance & Production Contract",
        "provenance.dataset_hash": "Dataset Hash",
        "provenance.assignments_hash": "Assignments Hash",
        "provenance.profitability_run": "Profitability Run",
        "provenance.validation_run": "Validation Run",
        "provenance.videos_in_contract": "Videos in contract",
        "provenance.clusters_in_contract": "Clusters in contract",

        # Overview Page
        "overview.title": "🎯 Overview & Validation Summary",
        "overview.key_metrics": "Key Portfolio Metrics",
        "overview.videos_analyzed": "Videos Analyzed",
        "overview.channels_analyzed": "Channels Analyzed",
        "overview.clusters_subniches": "Clusters / Subniches",
        "overview.outliers_identified": "Outliers Identified",
        "overview.validated_candidates": "Validated Candidates",
        "overview.pass_pass_warnings": "PASS / PASS_WITH_WARNINGS",

        "overview.validation_status_dist": "Sprint 10 Validation Status Distribution",
        "overview.profitability_class_dist": "Profitability Classification Distribution",
        "overview.api_resource_usage": "API & Resource Usage",
        "overview.score_distributions": "Score Metric Distributions",

        "overview.yt_quota_usage": "YouTube API Quota Usage",
        "overview.ai_model_usage": "AI/Model Usage",
        "overview.ai_cost_estimate": "AI Cost Estimate",
        "overview.unavailable_sprint11": "Unavailable / Not tracked in Sprint 11",

        # Opportunities Page
        "opportunities.title": "💡 Opportunity Candidates",
        "opportunities.caption": "Sortable and filterable view of all cluster opportunity candidates.",
        "opportunities.filters": "🔍 Filters",
        "opportunities.filter_val_status": "Validation Status",
        "opportunities.filter_prof_class": "Profitability Classification",
        "opportunities.filter_min_val_score": "Minimum Validation Score",
        "opportunities.filter_max_fp_risk": "Maximum False Positive Risk",
        "opportunities.filter_max_fragility": "Maximum Fragility Score",
        "opportunities.filter_niche": "Niche",
        "opportunities.showing_candidates": "Showing {filtered} of {total} candidates.",
        "opportunities.no_matching": "No candidates match the selected filter criteria.",

        # Opportunity Detail Page
        "detail.title": "🔎 Opportunity Detail & Underlying Evidence",
        "detail.no_candidates": "No opportunity candidates available.",
        "detail.select_cluster": "Select Cluster",
        "detail.cluster_not_found": "Cluster {cid} not found.",
        "detail.cluster_header": "Cluster #{cid}: {subniche}",
        "detail.niche_microniche": "Niche: {niche} | Microniche: {microniche}",

        # Detail Metrics
        "detail.val_status": "Validation Status",
        "detail.val_score": "Validation Score",
        "detail.prof_score": "Profitability Score",
        "detail.fragility_score": "Fragility Score",
        "detail.fp_risk": "False Positive Risk",

        # Tabs
        "tab.executive_summary": "📋 Executive Summary",
        "tab.profitability": "💰 Profitability",
        "tab.validator_sensitivity": "🛡️ Validator & Sensitivity",
        "tab.market_competition": "📊 Market & Competition",
        "tab.production_risk": "⚙️ Production Risk",
        "tab.economic_geography": "🌍 Economic / Geography",
        "tab.supporting_videos": "🎬 Supporting Videos",

        # Executive Summary Tab
        "exec.why_interesting": "Why this candidate is interesting (Positive Evidence)",
        "exec.no_positive": "No positive evidence listed.",
        "exec.why_fail": "Why it may fail (Contradictory / Negative Evidence)",
        "exec.no_contradictory": "No critical contradictory evidence noted.",
        "exec.missing_and_warnings": "Missing Evidence & Warnings",
        "exec.missing_evidence": "Missing Evidence",
        "exec.warning": "Warning",
        "exec.critical_failure": "Critical Failure",

        # Profitability Tab
        "prof.signals_title": "Profitability & Monetization Signals",
        "prof.classification": "Classification",
        "prof.confidence": "Confidence",
        "prof.coverage": "Component Coverage",
        "prof.expected_views_dist": "Expected Views Distribution",
        "prof.low_views": "Low Expected Views",
        "prof.base_views": "Base Expected Views",
        "prof.high_views": "High Expected Views",
        "prof.revenue_benchmark_status": "Revenue & Benchmark Status",
        "prof.dev_limitation": "⚠️ DEVELOPMENT DATASET LIMITATION",
        "prof.rpm_benchmark_unavail": "RPM benchmark: Unavailable (No production RPM benchmark in Sprint 11)",
        "prof.revenue_est_unavail": "Revenue estimate: Unavailable (Do not display $0)",
        "prof.monetary_cost_unavail": "Monetary cost: Unavailable (Do not display $0)",
        "prof.expected_profit_unavail": "Expected profit: Unavailable (Do not display $0)",

        # Validator & Sensitivity Tab
        "val.adversarial_results": "Adversarial Validation Results",
        "val.val_confidence": "Validation Confidence",
        "val.sensitivity_title": "Sensitivity Analysis & Stress Tests",
        "val.signal_stability": "Signal Stability Metrics",
        "val.sample_adequacy": "Sample Adequacy",
        "val.cross_signal_consistency": "Cross-Signal Consistency",
        "val.expected_views_stability": "Expected Views Stability",

        # Sensitivity Metrics Labels
        "sens.orig_prof_score": "Original Profitability Score",
        "sens.score_no_top_video": "Score Without Top Video",
        "sens.score_no_dom_channel": "Score Without Dominant Channel",
        "sens.stress_adj_score": "Stress-Adjusted Score",

        # Market & Competition Tab
        "mkt.structure_title": "Market Structure & Competition (Sprint 7)",
        "mkt.competition_score": "Competition Score",
        "mkt.accessibility": "Entry Accessibility",
        "mkt.dom_channel_share": "Dominant Channel Share",
        "mkt.top3_channel_share": "Top 3 Channel Share",
        "mkt.channel_hhi": "Channel HHI",
        "mkt.unique_channels": "Unique Channels",
        "mkt.small_channel_success": "Small Channel Success",
        "mkt.outlier_diversity": "Outlier Diversity",
        "mkt.evergreen_depth": "Evergreen & Content Depth",
        "mkt.evergreen_score": "Evergreen Score",
        "mkt.evergreen_class": "Evergreen Class",
        "mkt.trend_score": "Trend Score",
        "mkt.content_depth": "Content Depth",

        # Production Risk Tab
        "prod.complexity_title": "Production Complexity & Risk (Sprint 8)",
        "prod.complexity": "Production Complexity",
        "prod.cost_index": "Production Cost Index",
        "prod.attractiveness": "Attractiveness Score",
        "prod.overall_risk": "Overall Risk Level",
        "prod.feasibility_factors": "Feasibility & Operating Factors",
        "prod.faceless_feasibility": "Faceless Feasibility",
        "prod.ai_assistance": "AI Assistance Potential",
        "prod.expertise_req": "Expertise Requirement",
        "prod.repeatability": "Repeatability Band",
        "prod.individual_risks": "Individual Risk Levels",
        "prod.copyright_risk": "Copyright Risk",
        "prod.platform_risk": "Platform Risk",
        "prod.accuracy_risk": "Accuracy Risk",
        "prod.update_burden": "Update Burden",
        "prod.source_dependency": "Source Dependency",

        # Economic & Geography Tab
        "econ.value_title": "Economic Value & Geography (Sprint 6)",
        "econ.dom_language": "Dominant Language",
        "econ.market_tier": "Primary Market Tier",
        "econ.audience_econ_val": "Audience Economic Value",
        "econ.econ_confidence": "Economic Confidence",
        "econ.benchmark_coverage": "Benchmark Coverage",
        "econ.long_form_count": "Long-form Count",
        "econ.shorts_count": "Shorts Count",

        # Supporting Videos Tab
        "vids.supporting_title": "Supporting Videos for Cluster #{cid}",
        "vids.no_supporting": "No supporting videos found for this cluster.",

        # Outliers Page
        "outliers.title": "🚀 Outlier Videos",
        "outliers.caption": "Strongest video outliers sorted by outlier evidence.",
        "outliers.summary_banner": "Total identified outlier population: {count} videos (out of {total} analyzed production videos).",
        "outliers.filters": "🔍 Outlier Filters",
        "outliers.all_clusters": "All",
        "outliers.cluster_filter": "Cluster Filter",
        "outliers.only_actual_outliers": "Only actual outliers (is_strong / is_major / is_extreme)",
        "outliers.min_outlier_ratio": "Minimum Outlier Ratio",
        "outliers.no_matching": "No outliers match the filter criteria.",

        # Channels Page
        "channels.title": "📺 Emerging & Relevant Channels",
        "channels.caption": "Channels represented across opportunity clusters in the canonical dataset.",

        # Costs Page
        "costs.title": "💳 API & Resource Usage",
        "costs.tracked_info_header": "### Tracked Resource Information",
        "costs.yt_quota": "YouTube API Quota Usage",
        "costs.ai_usage": "AI / Model Usage",
        "costs.ai_cost": "AI / Model Estimated Cost",
        "costs.data_runs": "Data Collection Runs",
        "costs.not_tracked": "Not tracked / unavailable",
        "costs.validation_run_desc": "1 validation run",
        "costs.financial_status_header": "Financial & Revenue Benchmark Status",
        "costs.financial_dev_desc": (
            "In this development dataset (83 videos, 10 clusters):\n\n"
            "- **Production monetary cost:** `Unavailable`\n"
            "- **RPM benchmarks:** `Unavailable`\n"
            "- **Estimated revenue:** `Unavailable`\n"
            "- **Expected net profit:** `Unavailable`\n\n"
            "*No dummy monetary values ($0) or fake cost estimates are fabricated in accordance with PRYTB transparency guidelines.*"
        ),

        # Common Labels
        "common.yes": "Yes",
        "common.no": "No",
        "common.na": "N/A",
        "common.cluster": "Cluster",
        "common.cluster_n": "Cluster {cid}",
    },
}

# ---------------------------------------------------------------------------
# Presentation Mappings for Canonical Analytical Enums (Requirement 4)
# Internal database values MUST REMAIN CANONICAL (PASS_WITH_WARNINGS, WATCH, etc.).
# Only presentation display string changes.
# ---------------------------------------------------------------------------

ENUM_TRANSLATIONS: Dict[str, Dict[str, Dict[str, str]]] = {
    "es": {
        # ValidationStatus
        "PASS": "APROBADO",
        "PASS_WITH_WARNINGS": "APROBADO CON ADVERTENCIAS",
        "WATCH": "EN OBSERVACIÓN",
        "FAIL": "DESCARTADO / FALLA DE VALIDACIÓN",
        "DISCARD": "DESCARTADO",
        "UNKNOWN": "DESCONOCIDO",
        "UNDETERMINED": "INDETERMINADO",

        # ProfitabilityClassification
        "HIGH_PROFITABILITY": "ALTA RENTABILIDAD",
        "MODERATE_PROFITABILITY": "RENTABILIDAD MODERADA",
        "LOW_PROFITABILITY": "BAJA RENTABILIDAD",
        "UNPROFITABLE": "NO RENTABLE",
        "UNCERTAIN": "INCIERTO",

        # EntryAccessibility
        "HIGH_ACCESSIBILITY": "ALTA ACCESIBILIDAD",
        "MODERATE_ACCESSIBILITY": "ACCESIBILIDAD MODERADA",
        "LOW_ACCESSIBILITY": "BAJA ACCESIBILIDAD",
        "RESTRICTED_ACCESSIBILITY": "ACCESIBILIDAD RESTRINGIDA",

        # RiskLevel
        "VERY_LOW": "MUY BAJO",
        "LOW": "BAJO",
        "MEDIUM": "MEDIO",
        "HIGH": "ALTO",
        "VERY_HIGH": "MUY ALTO",
        "CRITICAL": "CRÍTICO",

        # EvergreenClass
        "EVERGREEN": "EVERGREEN",
        "SEASONAL": "ESTACIONAL",
        "TREND_DRIVEN": "TENDENCIA",
        "FLASH_IN_PAN": "EFÍMERO",

        # ContentDepthBand
        "SHALLOW": "SUPERFICIAL",
        "MODERATE": "MODERADO",
        "DEEP": "PROFUNDO",
        "VERY_DEEP": "MUY PROFUNDO",

        # ProductionComplexity
        "VERY_LOW_COMPLEXITY": "COMPLEJIDAD MUY BAJA",
        "LOW_COMPLEXITY": "COMPLEJIDAD BAJA",
        "MODERATE_COMPLEXITY": "COMPLEJIDAD MODERADA",
        "HIGH_COMPLEXITY": "COMPLEJIDAD ALTA",
        "VERY_HIGH_COMPLEXITY": "COMPLEJIDAD MUY ALTA",

        # FacelessFeasibility
        "FULLY_FACELESS": "100% FACELESS",
        "HYBRID": "HÍBRIDO",
        "PERSONAL_BRAND_REQUIRED": "REQUIERE MARCA PERSONAL",

        # AIAssistancePotential
        "HIGH_AUTOMATION": "ALTA AUTOMATIZACIÓN",
        "MODERATE_AUTOMATION": "AUTOMATIZACIÓN MODERADA",
        "LOW_AUTOMATION": "BAJA AUTOMATIZACIÓN",

        # ExpertiseRequirement
        "BEGINNER": "PRINCIPIANTE",
        "INTERMEDIATE": "INTERMEDIO",
        "EXPERT": "EXPERTO",

        # RepeatabilityBand
        "HIGHLY_REPEATABLE": "ALTAMENTE REPETIBLE",
        "MODERATELY_REPEATABLE": "MODERADAMENTE REPETIBLE",
        "LOW_REPEATABILITY": "BAJA REPETIBILIDAD",
    },

    "en": {
        # ValidationStatus
        "PASS": "PASS",
        "PASS_WITH_WARNINGS": "PASS WITH WARNINGS",
        "WATCH": "WATCH",
        "FAIL": "FAIL",
        "DISCARD": "DISCARD",
        "UNKNOWN": "UNKNOWN",
        "UNDETERMINED": "UNDETERMINED",

        # ProfitabilityClassification
        "HIGH_PROFITABILITY": "HIGH PROFITABILITY",
        "MODERATE_PROFITABILITY": "MODERATE PROFITABILITY",
        "LOW_PROFITABILITY": "LOW PROFITABILITY",
        "UNPROFITABLE": "UNPROFITABLE",
        "UNCERTAIN": "UNCERTAIN",

        # EntryAccessibility
        "HIGH_ACCESSIBILITY": "HIGH ACCESSIBILITY",
        "MODERATE_ACCESSIBILITY": "MODERATE ACCESSIBILITY",
        "LOW_ACCESSIBILITY": "LOW ACCESSIBILITY",
        "RESTRICTED_ACCESSIBILITY": "RESTRICTED ACCESSIBILITY",

        # RiskLevel
        "VERY_LOW": "VERY LOW",
        "LOW": "LOW",
        "MEDIUM": "MEDIUM",
        "HIGH": "HIGH",
        "VERY_HIGH": "VERY HIGH",
        "CRITICAL": "CRITICAL",

        # EvergreenClass
        "EVERGREEN": "EVERGREEN",
        "SEASONAL": "SEASONAL",
        "TREND_DRIVEN": "TREND DRIVEN",
        "FLASH_IN_PAN": "FLASH IN PAN",

        # ContentDepthBand
        "SHALLOW": "SHALLOW",
        "MODERATE": "MODERATE",
        "DEEP": "DEEP",
        "VERY_DEEP": "VERY DEEP",

        # ProductionComplexity
        "VERY_LOW_COMPLEXITY": "VERY LOW COMPLEXITY",
        "LOW_COMPLEXITY": "LOW COMPLEXITY",
        "MODERATE_COMPLEXITY": "MODERATE COMPLEXITY",
        "HIGH_COMPLEXITY": "HIGH COMPLEXITY",
        "VERY_HIGH_COMPLEXITY": "VERY HIGH COMPLEXITY",

        # FacelessFeasibility
        "FULLY_FACELESS": "FULLY FACELESS",
        "HYBRID": "HYBRID",
        "PERSONAL_BRAND_REQUIRED": "PERSONAL BRAND REQUIRED",

        # AIAssistancePotential
        "HIGH_AUTOMATION": "HIGH AUTOMATION",
        "MODERATE_AUTOMATION": "MODERATE AUTOMATION",
        "LOW_AUTOMATION": "LOW AUTOMATION",

        # ExpertiseRequirement
        "BEGINNER": "BEGINNER",
        "INTERMEDIATE": "INTERMEDIATE",
        "EXPERT": "EXPERT",

        # RepeatabilityBand
        "HIGHLY_REPEATABLE": "HIGHLY REPEATABLE",
        "MODERATELY_REPEATABLE": "MODERATELY REPEATABLE",
        "LOW_REPEATABILITY": "LOW REPEATABILITY",
    },
}

# ---------------------------------------------------------------------------
# Dynamic Table Column Header Translation Map (Requirement 5)
# ---------------------------------------------------------------------------

COLUMN_HEADERS: Dict[str, Dict[str, str]] = {
    "es": {
        "Cluster": "Cluster",
        "Niche / Microniche": "Nicho / Micronicho",
        "Niche": "Nicho",
        "ProfitabilityScore": "Puntaje de rentabilidad",
        "Profitability Classification": "Clasificación de rentabilidad",
        "Profitability Confidence": "Confianza de rentabilidad",
        "ValidationScore": "Puntaje de validación",
        "ValidationStatus": "Estado de validación",
        "Status": "Estado",
        "Classification": "Clasificación",
        "Count": "Conteo",
        "ValidationConfidence": "Confianza de validación",
        "FragilityScore": "Puntaje de fragilidad",
        "FalsePositiveRisk": "Riesgo de falso positivo",
        "Expected Views Base": "Vistas esperadas base",
        "Expected Views": "Vistas esperadas",
        "Competition": "Competencia",
        "Evergreen": "Evergreen",
        "Production Attractiveness": "Atractividad de producción",
        "Risk": "Riesgo",
        "Coverage": "Cobertura",
        "Metric": "Métrica",
        "Score": "Puntaje",
        "Video": "Video",
        "Channel": "Canal",
        "Views": "Vistas",
        "Subscribers": "Suscriptores",
        "Published Date": "Fecha de publicación",
        "Age (Days)": "Edad (Días)",
        "Outlier Ratio": "Ratio de outlier",
        "Age-Norm Ratio": "Ratio norm. edad",
        "Age-Norm Outlier Ratio": "Ratio de outlier norm. por edad",
        "Velocity": "Velocidad",
        "Velocity (views/day)": "Velocidad (vistas/día)",
        "Duration": "Duración",
        "Type": "Tipo",
        "YouTube Link": "Enlace de YouTube",
        "Video Count in Dataset": "Conteo de videos en dataset",
        "Outlier Count": "Conteo de outliers",
        "Clusters Represented": "Clusters representados",
        "Median Performance (Views)": "Mediana de desempeño (Vistas)",
        "Small Channel (<=50k subs)": "Canal pequeño (<=50k subs)",
        "Title": "Título",
    },

    "en": {
        "Cluster": "Cluster",
        "Niche / Microniche": "Niche / Microniche",
        "Niche": "Niche",
        "ProfitabilityScore": "Profitability Score",
        "Profitability Classification": "Profitability Classification",
        "Profitability Confidence": "Profitability Confidence",
        "ValidationScore": "Validation Score",
        "ValidationStatus": "Validation Status",
        "Status": "Status",
        "Classification": "Classification",
        "Count": "Count",
        "ValidationConfidence": "Validation Confidence",
        "FragilityScore": "Fragility Score",
        "FalsePositiveRisk": "False Positive Risk",
        "Expected Views Base": "Expected Views Base",
        "Expected Views": "Expected Views",
        "Competition": "Competition",
        "Evergreen": "Evergreen",
        "Production Attractiveness": "Production Attractiveness",
        "Risk": "Risk",
        "Coverage": "Coverage",
        "Metric": "Metric",
        "Score": "Score",
        "Video": "Video",
        "Channel": "Channel",
        "Views": "Views",
        "Subscribers": "Subscribers",
        "Published Date": "Published Date",
        "Age (Days)": "Age (Days)",
        "Outlier Ratio": "Outlier Ratio",
        "Age-Norm Ratio": "Age-Norm Ratio",
        "Age-Norm Outlier Ratio": "Age-Norm Outlier Ratio",
        "Velocity": "Velocity",
        "Velocity (views/day)": "Velocity (views/day)",
        "Duration": "Duration",
        "Type": "Type",
        "YouTube Link": "YouTube Link",
        "Video Count in Dataset": "Video Count in Dataset",
        "Outlier Count": "Outlier Count",
        "Clusters Represented": "Clusters Represented",
        "Median Performance (Views)": "Median Performance (Views)",
        "Small Channel (<=50k subs)": "Small Channel (<=50k subs)",
        "Title": "Title",
    },
}


def t(key: str, lang: str = DEFAULT_LANGUAGE, **kwargs: Any) -> str:
    """
    Returns localized translation string for key in given language.
    Falls back gracefully if key is missing in target language.
    """
    lang_dict = TRANSLATIONS.get(lang, TRANSLATIONS[DEFAULT_LANGUAGE])
    text = lang_dict.get(key)
    
    if text is None:
        # Fallback to ES then EN
        text = TRANSLATIONS["es"].get(key, TRANSLATIONS["en"].get(key, key))
    
    if kwargs and isinstance(text, str):
        try:
            return text.format(**kwargs)
        except Exception:
            return text
    return text


def format_enum_presentation(value: Union[str, Enum, None], lang: str = DEFAULT_LANGUAGE) -> str:
    """
    Translates an analytical enum or internal string for presentation without mutating
    the underlying internal value (Requirement 4).
    """
    if value is None:
        return t("common.na", lang=lang)
    
    raw_str = value.value if isinstance(value, Enum) else str(value)
    
    lang_enums = ENUM_TRANSLATIONS.get(lang, ENUM_TRANSLATIONS[DEFAULT_LANGUAGE])
    if raw_str in lang_enums:
        return lang_enums[raw_str]
    
    # Fallback check across languages
    for l_key in ["es", "en"]:
        if raw_str in ENUM_TRANSLATIONS[l_key]:
            return ENUM_TRANSLATIONS[l_key][raw_str]
            
    return raw_str


def translate_column_header(header: str, lang: str = DEFAULT_LANGUAGE) -> str:
    """Translates table column headers dynamically for presentation (Requirement 5)."""
    lang_cols = COLUMN_HEADERS.get(lang, COLUMN_HEADERS[DEFAULT_LANGUAGE])
    return lang_cols.get(header, header)


def format_number(val: Union[int, float, None], lang: str = DEFAULT_LANGUAGE) -> str:
    """
    Formats numbers safely for presentation without modifying underlying values (Requirement 6).
    In Spanish: uses '.' for thousands separator (e.g. 10.000).
    In English: uses ',' for thousands separator (e.g. 10,000).
    """
    if val is None:
        return t("common.na", lang=lang)
    try:
        if isinstance(val, float):
            formatted_raw = f"{val:,.1f}"
        else:
            formatted_raw = f"{val:,}"
            
        if lang == "es":
            # Swap comma and dot for Spanish
            formatted = formatted_raw.replace(",", "X").replace(".", ",").replace("X", ".")
            return formatted
        return formatted_raw
    except Exception:
        return str(val)
