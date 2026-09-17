# Sprint 13 — Gate 2A Final Economic Validation

**Gate status:** GO  
**Top3 readiness:** NO  
**Checks:** 41/41 PASS  
**Qualified:** 2/20

## Clean Iteration Counters

- `corrections`: `0`
- `mapping_fixes`: `0`
- `persistence_fixes`: `0`
- `scoring_fixes`: `0`
- `state_discarded_before_second`: `True`

## Autoridad y reproducibilidad

- Run canónico: `sprint12_gate7_reconciled_20260914_211554` (`SPRINT12_FINAL_ANALYTICS_APPROVED`)
- Hash Top20 canónico (Gate1D): `df53c661f8b0bd61e300d7f364095d399331026245f4c0ce3b80fa9d3b2a090a`
- Hash Top20 persistido en DB: `85a543baf63afad339c1643b8f25cadd2b8d7d4ca316ce6e182c130fe39d98e4`
- Hash económico: `4f31ba9ecd635f448e8f413fdfabb31dc233d07c38deba96053b5d45a8954c40`
- Derivación económica: hash canónico del objeto de tres hashes de filas PostgreSQL completas y ordenadas: `rpm`, `cost`, `econ`.
- Auditoría read-only: 0 mutaciones de base de datos y ningún artefacto Gate2C sobrescrito.

## Exact Benchmarks Snapshot

### RPM Benchmarks
| Category | Low ($) | Base ($) | High ($) |
|---|---:|---:|---:|
| Digital Marketing / Business | 4.00 | 6.50 | 9.00 |
| Education / How-To | 2.00 | 4.00 | 6.00 |
| Finance / Investing | 4.00 | 8.00 | 12.00 |
| Technology / Software | 4.00 | 7.00 | 10.00 |

### Production Cost Benchmarks
| Benchmark ID | Low ($/h) | Base ($/h) | High ($/h) |
|---|---:|---:|---:|
| `cost_bench_upwork_video_editor_2026` | 6.00 | 15.50 | 25.00 |
| `cost_bench_upwork_content_creator_2026` | 25.00 | 40.00 | 55.00 |

## Readiness (8 condiciones)

| Condición | Estado | Detalle |
|---|---|---|
| approved_authority | PASS | SPRINT12_FINAL_ANALYTICS_APPROVED |
| canonical_top20_identity | PASS | df53c661f8b0bd61e300d7f364095d399331026245f4c0ce3b80fa9d3b2a090a |
| score_integrity | PASS | 20/20 |
| economic_completeness | PASS | 20/20 |
| economic_formula_integrity | PASS | 20/20 |
| provenance_integrity | PASS | 20/20 |
| closed_loop_determinism | PASS | two fresh reads |
| at_least_three_qualified | UNMET | 2/3 qualified candidates (UNMET readiness for Top3 selection) |

## Checks internos

| # | Check | Estado | Detalle |
|---:|---|---|---|
| 1 | authority_run_exists | PASS | SPRINT12_FINAL_ANALYTICS_APPROVED |
| 2 | authority_status | PASS | SPRINT12_FINAL_ANALYTICS_APPROVED |
| 3 | top20_postgres_source_count | PASS | 20 |
| 4 | top20_persisted_hash | PASS | 85a543baf63afad339c1643b8f25cadd2b8d7d4ca316ce6e182c130fe39d98e4 |
| 5 | gate1e_cross_check_identity | PASS | PostgreSQL Top20 == Gate1E items |
| 6 | top20_expected_gate1d_hash | PASS | df53c661f8b0bd61e300d7f364095d399331026245f4c0ce3b80fa9d3b2a090a |
| 7 | rank20_count | PASS | 20 |
| 8 | unique_candidate_ids | PASS | 20 |
| 9 | candidate_economics_count | PASS | 20 |
| 10 | economic_candidate_identity | PASS | canonical=economic |
| 11 | rpm_benchmarks_present | PASS | 4 |
| 12 | cost_benchmarks_present | PASS | 2 |
| 13 | exact_benchmark_values_verified | PASS | RPM & Cost benchmarks match exact values |
| 14 | economic_expected_hash | PASS | 4f31ba9ecd635f448e8f413fdfabb31dc233d07c38deba96053b5d45a8954c40 |
| 15 | views_complete | PASS | 20/20 |
| 16 | rpm_complete | PASS | 20/20 |
| 17 | revenue_complete | PASS | 20/20 |
| 18 | cost_complete | PASS | 20/20 |
| 19 | profit_complete | PASS | 20/20 |
| 20 | ranges_ordered | PASS | low<=base<=high |
| 21 | revenue_formulas | PASS | 20/20 |
| 22 | cost_formulas | PASS | 20/20 |
| 23 | profit_formulas | PASS | 20/20 |
| 24 | provenance_complete | PASS | 20/20 |
| 25 | validator_readback_complete | PASS | 20/20 persisted records consistent |
| 26 | base_profit_rank_attached | PASS | 20/20 mapped |
| 27 | score_reconstruction | PASS | 20/20 |
| 28 | classification_valid | PASS | 20/20 |
| 29 | qualified_not_discard | PASS | invariant |
| 30 | canonical_order | PASS | profitability DESC, ID ASC |
| 31 | economic_order | PASS | profit_base DESC, ID ASC |
| 32 | top5_exactly_five | PASS | 5 |
| 33 | profitability_separate_from_money | PASS | separate fields |
| 34 | revenue_score_is_composition_proxy | PASS | format composition only; no monetary input |
| 35 | configured_weights | PASS | ProfitabilityConfig |
| 36 | risk_scale_from_config | PASS | 0.3 |
| 37 | fix_counters_zero | PASS | corrections=0, mapping_fixes=0, persistence_fixes=0, scoring_fixes=0 |
| 38 | independent_economic_hash | PASS | 4f31ba9ecd635f448e8f413fdfabb31dc233d07c38deba96053b5d45a8954c40 |
| 39 | independent_canonical_result_hash | PASS | ffdd52fe815d322569d6dcc81100f34bcc1bfa90d30331e30ee61daf0b19ca79 |
| 40 | independent_economic_rank_hash | PASS | 46de86337a6aa34167540bed9b8707703f4472660f3a72640b44aa822ca5c8ae |
| 41 | independent_top20_persisted_hash | PASS | 85a543baf63afad339c1643b8f25cadd2b8d7d4ca316ce6e182c130fe39d98e4 |

## Ranking canónico completo (Rank20)

| Rank | ID | Subniche | Demand | Viral | RevScore | Comp | Geog | Everg | Prod | Depth | Short | Risk | Conf | Profitability | BaseProfitRank | ProfitBase USD | Class | Qualified |
|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---|---|---:|---:|---:|---:|---:|---|---|
| 1 | `def_052` | De & Hotmart | 0.0 | 9.8 | 75.0 | 54.4 | 60.0 | 75.7 | 86.7 | 100.0 | 60.0 | 4.0 | 85.6 | 50.0641 | 5 | 180.000 | OBSERVE | YES |
| 2 | `def_045` | De & De Software | 0.0 | 11.7 | 75.0 | 55.5 | 60.0 | 74.9 | 91.0 | 100.0 | 60.0 | 5.8 | 96.3 | 50.0564 | 15 | -54.486 | OBSERVE | YES |
| 3 | `def_053` | PC Hardware & System Optimization | 0.0 | 10.9 | 75.0 | 55.3 | 60.0 | 80.2 | 79.7 | 100.0 | 60.0 | 4.7 | 83.6 | 49.6848 | 4 | 205.860 | DISCARD | NO |
| 4 | `def_004` | PC Hardware & System Optimization | 0.0 | 9.3 | 75.0 | 53.6 | 60.0 | 71.5 | 89.0 | 100.0 | 60.0 | 5.5 | 86.2 | 49.4373 | 16 | -75.367 | DISCARD | NO |
| 5 | `def_024` | PC Hardware & System Optimization | 0.0 | 10.0 | 75.0 | 54.0 | 60.0 | 77.4 | 86.0 | 100.0 | 60.0 | 8.9 | 87.8 | 48.7686 | 10 | 44.893 | DISCARD | NO |
| 6 | `def_025` | Backend & Backend Frontend | 0.0 | 11.7 | 60.0 | 59.5 | 60.0 | 82.2 | 97.1 | 100.0 | 60.0 | 4.8 | 87.9 | 48.2911 | 17 | -76.498 | DISCARD | NO |
| 7 | `def_057` | De & De Software | 0.0 | 9.8 | 75.0 | 54.4 | 60.0 | 75.0 | 87.9 | 100.0 | 60.0 | 10.1 | 88.3 | 48.2895 | 7 | 101.753 | DISCARD | NO |
| 8 | `def_046` | Crear & Curso | 0.0 | 10.9 | 60.0 | 54.5 | 60.0 | 76.9 | 92.9 | 100.0 | 60.0 | 4.2 | 87.8 | 47.8997 | 2 | 290.916 | DISCARD | NO |
| 9 | `def_020` | Agencia & Agencia De | 0.0 | 11.6 | 75.0 | 53.3 | 60.0 | 64.1 | 79.0 | 95.0 | 60.0 | 5.4 | 82.4 | 47.8536 | 20 | -91.511 | DISCARD | NO |
| 10 | `def_055` | Cybersecurity Education | 0.0 | 10.2 | 75.0 | 53.5 | 60.0 | 73.6 | 79.7 | 100.0 | 60.0 | 14.9 | 88.3 | 46.0411 | 9 | 53.111 | DISCARD | NO |
| 11 | `def_038` | Bootstrap & Bootstrap Saas | 0.0 | 10.0 | 75.0 | 54.0 | 60.0 | 78.7 | 81.2 | 100.0 | 60.0 | 17.5 | 89.6 | 45.8328 | 19 | -91.440 | DISCARD | NO |
| 12 | `def_023` | Agency & Marketing | 0.0 | 9.5 | 75.0 | 55.3 | 60.0 | 81.5 | 78.9 | 100.0 | 60.0 | 18.4 | 90.5 | 45.4143 | 18 | -87.462 | DISCARD | NO |
| 13 | `def_015` | PC Hardware & System Optimization | 0.0 | 10.0 | 75.0 | 53.5 | 60.0 | 73.4 | 76.2 | 100.0 | 60.0 | 17.0 | 89.2 | 45.0051 | 6 | 135.767 | DISCARD | NO |
| 14 | `def_030` | Azure & Azure Devops | 0.0 | 11.2 | 75.0 | 55.9 | 60.0 | 85.9 | 66.7 | 100.0 | 60.0 | 18.2 | 90.9 | 44.8916 | 13 | -31.144 | DISCARD | NO |
| 15 | `def_054` | 2025 & In | 0.0 | 10.4 | 75.0 | 54.6 | 60.0 | 65.1 | 76.9 | 100.0 | 60.0 | 17.1 | 91.0 | 44.1629 | 14 | -38.346 | DISCARD | NO |
| 16 | `def_016` | By & By Step | 0.0 | 10.3 | 75.0 | 54.8 | 60.0 | 64.9 | 71.5 | 100.0 | 60.0 | 22.0 | 88.9 | 42.0991 | 8 | 100.417 | DISCARD | NO |
| 17 | `def_026` | 2025 & In | 0.0 | 10.8 | 75.0 | 57.6 | 60.0 | 74.1 | 68.8 | 72.0 | 60.0 | 21.5 | 87.8 | 41.3070 | 3 | 209.100 | DISCARD | NO |
| 18 | `def_009` | AI Automation & Autonomous Agents | 0.0 | 9.7 | 60.0 | 54.6 | 60.0 | 66.3 | 75.9 | 100.0 | 60.0 | 20.0 | 90.2 | 40.2125 | 11 | 34.743 | DISCARD | NO |
| 19 | `def_002` | 20 & Budget | 0.0 | 8.6 | 60.0 | 52.6 | 60.0 | 72.4 | 86.5 | 100.0 | 60.0 | 26.8 | 87.3 | 39.8850 | 12 | -12.064 | DISCARD | NO |
| 20 | `def_036` | AI Safety & Risk Analysis | 0.0 | 9.4 | 60.0 | 53.4 | 60.0 | 73.0 | 76.1 | 100.0 | 60.0 | 23.9 | 89.9 | 39.8156 | 1 | 1321.064 | DISCARD | NO |

## Top5

| Rank | ID | Profitability | BaseProfitRank | Profit base USD | Clase | Qualified |
|---:|---|---:|---:|---:|---|---|
| 1 | `def_052` | 50.0641 | 5 | 180.000 | OBSERVE | YES |
| 2 | `def_045` | 50.0564 | 15 | -54.486 | OBSERVE | YES |
| 3 | `def_053` | 49.6848 | 4 | 205.860 | DISCARD | NO |
| 4 | `def_004` | 49.4373 | 16 | -75.367 | DISCARD | NO |
| 5 | `def_024` | 48.7686 | 10 | 44.893 | DISCARD | NO |

## Qualified Opportunities (Dedicated Section)

| Rank | ID | Subniche | Profitability | BaseProfitRank | Profit Base USD | Class |
|---:|---|---|---:|---:|---:|---|
| 1 | `def_052` | De & Hotmart | 50.0641 | 5 | 180.000 | OBSERVE |
| 2 | `def_045` | De & De Software | 50.0564 | 15 | -54.486 | OBSERVE |

## Ranking económico diagnóstico completo

| EconRank | ID | Profit base USD | Canonical Rank | Profitability | Clase |
|---:|---|---:|---:|---:|---|
| 1 | `def_036` | 1321.064 | 20 | 39.8156 | DISCARD |
| 2 | `def_046` | 290.916 | 8 | 47.8997 | DISCARD |
| 3 | `def_026` | 209.100 | 17 | 41.3070 | DISCARD |
| 4 | `def_053` | 205.860 | 3 | 49.6848 | DISCARD |
| 5 | `def_052` | 180.000 | 1 | 50.0641 | OBSERVE |
| 6 | `def_015` | 135.767 | 13 | 45.0051 | DISCARD |
| 7 | `def_057` | 101.753 | 7 | 48.2895 | DISCARD |
| 8 | `def_016` | 100.417 | 16 | 42.0991 | DISCARD |
| 9 | `def_055` | 53.111 | 10 | 46.0411 | DISCARD |
| 10 | `def_024` | 44.893 | 5 | 48.7686 | DISCARD |
| 11 | `def_009` | 34.743 | 18 | 40.2125 | DISCARD |
| 12 | `def_002` | -12.064 | 19 | 39.8850 | DISCARD |
| 13 | `def_030` | -31.144 | 14 | 44.8916 | DISCARD |
| 14 | `def_054` | -38.346 | 15 | 44.1629 | DISCARD |
| 15 | `def_045` | -54.486 | 2 | 50.0564 | OBSERVE |
| 16 | `def_004` | -75.367 | 4 | 49.4373 | DISCARD |
| 17 | `def_025` | -76.498 | 6 | 48.2911 | DISCARD |
| 18 | `def_023` | -87.462 | 12 | 45.4143 | DISCARD |
| 19 | `def_038` | -91.440 | 11 | 45.8328 | DISCARD |
| 20 | `def_020` | -91.511 | 9 | 47.8536 | DISCARD |

## Persisted Opportunity Validator Details & Evidence

| Rank | ID | Score | Status | Conf | FP Risk | Fragility | Positive Evidence | Contradictory Evidence | Warnings | Critical Failures |
|---:|---|---:|---|---:|---:|---:|---|---|---|---|
| 1 | `def_052` | 78.86 | PASS | 85.6 | 25.15 | 0.43 | Repeatable outliers across 15 creators; Evergreen demand stability | High economic revenue potential asserted with zero RPM benchmark | HIGH_EXPECTED_VIEWS_VARIANCE; NO_MONETARY_BENCHMARK; ECONOMIC_SIGNAL_ASSUMPTION_HEAVY | None |
| 2 | `def_045` | 77.82 | PASS | 96.3 | 25.47 | 1.35 | Repeatable outliers across 19 creators; Evergreen demand stability; High faceless feasibility confirmed | High economic revenue potential asserted with zero RPM benchmark | HIGH_EXPECTED_VIEWS_VARIANCE; NO_MONETARY_BENCHMARK; ECONOMIC_SIGNAL_ASSUMPTION_HEAVY | None |
| 3 | `def_053` | 77.75 | PASS | 83.6 | 25.42 | 1.19 | Repeatable outliers across 12 creators; Evergreen demand stability | High economic revenue potential asserted with zero RPM benchmark | HIGH_EXPECTED_VIEWS_VARIANCE; NO_MONETARY_BENCHMARK; ECONOMIC_SIGNAL_ASSUMPTION_HEAVY | None |
| 4 | `def_004` | 77.97 | PASS | 86.2 | 25.25 | 0.71 | Repeatable outliers across 17 creators; Evergreen demand stability | High economic revenue potential asserted with zero RPM benchmark | HIGH_EXPECTED_VIEWS_VARIANCE; NO_MONETARY_BENCHMARK; ECONOMIC_SIGNAL_ASSUMPTION_HEAVY | None |
| 5 | `def_024` | 78.13 | PASS | 87.8 | 25.13 | 0.37 | Repeatable outliers across 23 creators; Evergreen demand stability | High economic revenue potential asserted with zero RPM benchmark | HIGH_EXPECTED_VIEWS_VARIANCE; NO_MONETARY_BENCHMARK; ECONOMIC_SIGNAL_ASSUMPTION_HEAVY | None |
| 6 | `def_025` | 76.88 | PASS | 87.9 | 26.37 | 3.92 | Repeatable outliers across 9 creators; Evergreen demand stability | None | HIGH_EXPECTED_VIEWS_VARIANCE; NO_MONETARY_BENCHMARK; ECONOMIC_SIGNAL_ASSUMPTION_HEAVY | None |
| 7 | `def_057` | 77.44 | PASS | 88.3 | 25.09 | 0.26 | Repeatable outliers across 22 creators; Evergreen demand stability | High economic revenue potential asserted with zero RPM benchmark | HIGH_EXPECTED_VIEWS_VARIANCE; NO_MONETARY_BENCHMARK; ECONOMIC_SIGNAL_ASSUMPTION_HEAVY | None |
| 8 | `def_046` | 79.63 | PASS | 87.8 | 25.16 | 0.45 | Repeatable outliers across 62 creators; Evergreen demand stability | None | HIGH_EXPECTED_VIEWS_VARIANCE; NO_MONETARY_BENCHMARK; ECONOMIC_SIGNAL_ASSUMPTION_HEAVY | None |
| 9 | `def_020` | 76.88 | PASS | 82.4 | 25.20 | 0.56 | Repeatable outliers across 12 creators; Evergreen demand stability | High economic revenue potential asserted with zero RPM benchmark | HIGH_EXPECTED_VIEWS_VARIANCE; NO_MONETARY_BENCHMARK; ECONOMIC_SIGNAL_ASSUMPTION_HEAVY | None |
| 10 | `def_055` | 77.83 | PASS | 88.3 | 25.06 | 0.18 | Repeatable outliers across 49 creators; Evergreen demand stability | High economic revenue potential asserted with zero RPM benchmark | HIGH_EXPECTED_VIEWS_VARIANCE; NO_MONETARY_BENCHMARK; ECONOMIC_SIGNAL_ASSUMPTION_HEAVY | None |
| 11 | `def_038` | 76.92 | PASS | 89.6 | 25.35 | 0.99 | Repeatable outliers across 11 creators; Evergreen demand stability | High economic revenue potential asserted with zero RPM benchmark | HIGH_EXPECTED_VIEWS_VARIANCE; NO_MONETARY_BENCHMARK; ECONOMIC_SIGNAL_ASSUMPTION_HEAVY | None |
| 12 | `def_023` | 76.02 | PASS | 90.5 | 25.33 | 0.95 | Repeatable outliers across 8 creators; Evergreen demand stability; High faceless feasibility confirmed | High economic revenue potential asserted with zero RPM benchmark | HIGH_EXPECTED_VIEWS_VARIANCE; NO_MONETARY_BENCHMARK; ECONOMIC_SIGNAL_ASSUMPTION_HEAVY | None |
| 13 | `def_015` | 77.12 | PASS | 89.2 | 25.12 | 0.34 | Repeatable outliers across 137 creators; Evergreen demand stability | High economic revenue potential asserted with zero RPM benchmark | HIGH_EXPECTED_VIEWS_VARIANCE; NO_MONETARY_BENCHMARK; ECONOMIC_SIGNAL_ASSUMPTION_HEAVY | None |
| 14 | `def_030` | 75.69 | PASS | 90.9 | 25.57 | 1.62 | Repeatable outliers across 16 creators; Evergreen demand stability; High faceless feasibility confirmed | High economic revenue potential asserted with zero RPM benchmark | HIGH_EXPECTED_VIEWS_VARIANCE; NO_MONETARY_BENCHMARK; ECONOMIC_SIGNAL_ASSUMPTION_HEAVY | None |
| 15 | `def_054` | 76.42 | PASS | 91.0 | 25.57 | 1.62 | Repeatable outliers across 12 creators; Evergreen demand stability; High faceless feasibility confirmed | High economic revenue potential asserted with zero RPM benchmark | HIGH_EXPECTED_VIEWS_VARIANCE; NO_MONETARY_BENCHMARK; ECONOMIC_SIGNAL_ASSUMPTION_HEAVY | None |
| 16 | `def_016` | 75.65 | PASS | 88.9 | 25.70 | 1.99 | Repeatable outliers across 12 creators; Evergreen demand stability | High economic revenue potential asserted with zero RPM benchmark | HIGH_EXPECTED_VIEWS_VARIANCE; NO_MONETARY_BENCHMARK; ECONOMIC_SIGNAL_ASSUMPTION_HEAVY | None |
| 17 | `def_026` | 73.59 | PASS_WITH_WARNINGS | 87.8 | 25.80 | 2.27 | Repeatable outliers across 9 creators; Evergreen demand stability | High economic revenue potential asserted with zero RPM benchmark | HIGH_EXPECTED_VIEWS_VARIANCE; NO_MONETARY_BENCHMARK; ECONOMIC_SIGNAL_ASSUMPTION_HEAVY | None |
| 18 | `def_009` | 77.37 | PASS | 90.2 | 25.38 | 1.08 | Repeatable outliers across 9 creators; Evergreen demand stability; High faceless feasibility confirmed | None | HIGH_EXPECTED_VIEWS_VARIANCE; NO_MONETARY_BENCHMARK; ECONOMIC_SIGNAL_ASSUMPTION_HEAVY | None |
| 19 | `def_002` | 77.37 | PASS | 87.3 | 25.22 | 0.64 | Repeatable outliers across 9 creators; Evergreen demand stability | None | HIGH_EXPECTED_VIEWS_VARIANCE; NO_MONETARY_BENCHMARK; ECONOMIC_SIGNAL_ASSUMPTION_HEAVY | None |
| 20 | `def_036` | 77.85 | PASS | 89.9 | 25.15 | 0.43 | Repeatable outliers across 45 creators; Evergreen demand stability | None | HIGH_EXPECTED_VIEWS_VARIANCE; NO_MONETARY_BENCHMARK; ECONOMIC_SIGNAL_ASSUMPTION_HEAVY | None |

## Registro de defectos y root cause

| ID | Root cause | Resolución | DB modificada |
|---|---|---|---|
| G2A-OLD-ECON-SOURCE | Previous Gate2A read obsolete embedded economics from profitability metrics. | Final rerun reads persisted Gate2C candidate_economics and benchmark tables. | False |
| G2A-OLD-HASH-LOOP | Previous double hash reused one in-memory Top5 string. | Two complete chains use newly-created PostgreSQL clients, discard in-memory state between passes, and compare deterministic hashes. | False |
| G2A-OLD-HARDCODED-WEIGHTS | Previous reconstruction duplicated literal weights. | Weights and risk scale now come from ProfitabilityConfig. | False |

## Semántica

`ProfitabilityScore` sigue siendo el índice compuesto canónico. `profit_base` es beneficio monetario USD y se expone separadamente. `RevenueScore` sigue siendo un proxy de composición de formato y no incorpora dinero.
