# SPRINT 13 — GATE 1: FUNNEL RECONSTRUCTION

**Authoritative source run:** `sprint12_gate7_reconciled_20260914_211554`

**Dataset hash:** `ecc6ad6d164e586bd718ff8c17be3801b5e3c0bbfa4e39cfc555b26f5c82c4ba`

## Mandatory two-read closed loop

Two full PostgreSQL reconstructions were performed with separate clients before artifact writing.

- Read count: 2
- Full reconstruction equality: **True**
- Ranking-hash equality: **True**
- Read 1 payload SHA-256: `b07c356610084acb96c74a811024e63c3d7263b60ba3ae71b1bf1a3638b09fc1`
- Read 2 payload SHA-256: `b07c356610084acb96c74a811024e63c3d7263b60ba3ae71b1bf1a3638b09fc1`

## Funnel validation

- Source outlier analyses: 10585 (754 actual; 282 small-channel)
- Source clusters/memberships: 35/10585
- Source semantic definitions/memberships: 58/9603
- Top100 ranking SHA-256: `d2df88751980afb7af1e9ecadf145a2a0ff514a0dba6062f8d62e03d980426d2` (persisted match: True)
- Top30 ranking SHA-256: `decc570011b881414202cba3f0c03144c954f0be5c21c4167e756f5ff5780c77`
- Top20 ranking SHA-256: `85a543baf63afad339c1643b8f25cadd2b8d7d4ca316ce6e182c130fe39d98e4` (persisted match: True)

## Prior-set comparison

The prior set is read from PostgreSQL run `sprint12_gate4_subniche_20260910_184255`. Case-insensitive exact normalized-intent equality; stable IDs are run-specific and are not equated.

- Prior/current counts: 20/20
- Shared normalized intents: 6 (agency scale, ai automation autonomous agents, artificial intelligence fundamentals, azure azure devops, information security fundamentals, pc hardware system optimization)
- Prior-only/current-only: 14/14

The run-specific stable IDs are intentionally not compared as identities. Dataset and assignment lineage for every prior item is retained in the Top20 JSON.

## Semantic classification of suspicious labels

This audit does not invent corrected labels. It flags generic templates, numeric/token-derived labels, stopword-dominated labels, and label/intent token mismatches for human review.

| ID | Niche | Subniche | Normalized Intent | Classification | Reasons |
| --- | --- | --- | --- | --- | --- |
| `def_015` | Computer Hardware & Operating Systems | PC Hardware & System Optimization | Artificial Intelligence fundamentals | SUSPICIOUS_GENERATED_LABEL | label_intent_token_mismatch |
| `def_046` | Crear Overview | Crear & Curso | de en | SUSPICIOUS_GENERATED_LABEL | generic_overview_template, label_intent_token_mismatch |
| `def_055` | Cybersecurity | Cybersecurity Education | information security fundamentals | SUSPICIOUS_GENERATED_LABEL | label_intent_token_mismatch |
| `def_036` | Artificial Intelligence | AI Safety & Risk Analysis | beginners recording | SUSPICIOUS_GENERATED_LABEL | label_intent_token_mismatch |
| `def_024` | Computer Hardware & Operating Systems | PC Hardware & System Optimization | ai automation autonomous agents | SUSPICIOUS_GENERATED_LABEL | label_intent_token_mismatch |
| `def_057` | De Overview | De & De Software | pc hardware system optimization | SUSPICIOUS_GENERATED_LABEL | generic_overview_template, stopword_dominated_label, label_intent_token_mismatch |
| `def_045` | De Overview | De & De Software | de de software | SUSPICIOUS_GENERATED_LABEL | generic_overview_template, stopword_dominated_label |
| `def_030` | Azure Overview | Azure & Azure Devops | azure azure devops | SUSPICIOUS_GENERATED_LABEL | generic_overview_template |
| `def_004` | Computer Hardware & Operating Systems | PC Hardware & System Optimization | 101 de | SUSPICIOUS_GENERATED_LABEL | label_intent_token_mismatch |
| `def_038` | Bootstrap Overview | Bootstrap & Bootstrap Saas | bootstrap dashboard | SUSPICIOUS_GENERATED_LABEL | generic_overview_template |
| `def_052` | De Overview | De & Hotmart | es la | SUSPICIOUS_GENERATED_LABEL | generic_overview_template, stopword_dominated_label, label_intent_token_mismatch |
| `def_020` | Agencia Overview | Agencia & Agencia De | agencia de | SUSPICIOUS_GENERATED_LABEL | generic_overview_template |
| `def_053` | Computer Hardware & Operating Systems | PC Hardware & System Optimization | finanzas mejorar tus | SUSPICIOUS_GENERATED_LABEL | label_intent_token_mismatch |
| `def_016` | By Overview | By & By Step | Cybersecurity education | SUSPICIOUS_GENERATED_LABEL | generic_overview_template, label_intent_token_mismatch |
| `def_054` | 2025 Overview | 2025 & In | freelance business notion | SUSPICIOUS_GENERATED_LABEL | generic_overview_template, numeric_token_label, label_intent_token_mismatch |
| `def_025` | Backend Overview | Backend & Backend Frontend | al backend | SUSPICIOUS_GENERATED_LABEL | generic_overview_template |
| `def_002` | 20 Overview | 20 & Budget | 10 budgeting | SUSPICIOUS_GENERATED_LABEL | generic_overview_template, numeric_token_label, label_intent_token_mismatch |
| `def_009` | Artificial Intelligence | AI Automation & Autonomous Agents | 2026 github | SUSPICIOUS_GENERATED_LABEL | label_intent_token_mismatch |
| `def_026` | 2025 Overview | 2025 & In | alternatives notion | SUSPICIOUS_GENERATED_LABEL | generic_overview_template, numeric_token_label, label_intent_token_mismatch |
| `def_023` | Agency Overview | Agency & Marketing | agency scale | SUSPICIOUS_GENERATED_LABEL | generic_overview_template |

## Final Top20

| Rank | ID | Niche | Subniche | Normalized Intent | Supporting Clusters | Supporting Outliers | Evidence Count |
| ---: | --- | --- | --- | --- | --- | ---: | ---: |
| 1 | `def_015` | Computer Hardware & Operating Systems | PC Hardware & System Optimization | Artificial Intelligence fundamentals | 3, 4, 5, 12, 13, 15, 22, 23, 25, 26, 30, 32 | 184 | 2298 |
| 2 | `def_046` | Crear Overview | Crear & Curso | de en | 29 | 66 | 670 |
| 3 | `def_055` | Cybersecurity | Cybersecurity Education | information security fundamentals | 15, 23, 25, 30 | 53 | 650 |
| 4 | `def_036` | Artificial Intelligence | AI Safety & Risk Analysis | beginners recording | 23 | 50 | 597 |
| 5 | `def_024` | Computer Hardware & Operating Systems | PC Hardware & System Optimization | ai automation autonomous agents | 0, 6, 13 | 26 | 319 |
| 6 | `def_057` | De Overview | De & De Software | pc hardware system optimization | 11, 16, 26 | 24 | 376 |
| 7 | `def_045` | De Overview | De & De Software | de de software | 11 | 23 | 204 |
| 8 | `def_030` | Azure Overview | Azure & Azure Devops | azure azure devops | 6 | 20 | 254 |
| 9 | `def_004` | Computer Hardware & Operating Systems | PC Hardware & System Optimization | 101 de | 0 | 20 | 267 |
| 10 | `def_038` | Bootstrap Overview | Bootstrap & Bootstrap Saas | bootstrap dashboard | 1 | 16 | 223 |
| 11 | `def_052` | De Overview | De & Hotmart | es la | 8 | 16 | 234 |
| 12 | `def_020` | Agencia Overview | Agencia & Agencia De | agencia de | 31 | 14 | 132 |
| 13 | `def_053` | Computer Hardware & Operating Systems | PC Hardware & System Optimization | finanzas mejorar tus | 2 | 14 | 118 |
| 14 | `def_016` | By Overview | By & By Step | Cybersecurity education | 5, 15, 17 | 14 | 170 |
| 15 | `def_054` | 2025 Overview | 2025 & In | freelance business notion | 7 | 12 | 136 |
| 16 | `def_025` | Backend Overview | Backend & Backend Frontend | al backend | 10 | 10 | 155 |
| 17 | `def_002` | 20 Overview | 20 & Budget | 10 budgeting | 33 | 10 | 183 |
| 18 | `def_009` | Artificial Intelligence | AI Automation & Autonomous Agents | 2026 github | 28 | 10 | 130 |
| 19 | `def_026` | 2025 Overview | 2025 & In | alternatives notion | 7 | 10 | 88 |
| 20 | `def_023` | Agency Overview | Agency & Marketing | agency scale | 24 | 9 | 166 |
