# Sprint 8 — Production Feasibility + Risk Engine

## Estado

Completo. Sprint 8 analiza la viabilidad de producción y el riesgo de los clusters aprobados en Sprint 5. Añade complejidad de producción, estimación de horas, costos de producción, **faceless feasibility, AI assistance potential, expertise requirement, repeatability**, análisis de riesgo completo (copyright, plataforma, precisión, carga de actualización, dependencia de fuentes) y **Production Attractiveness Score**. Persistencia opcional en PostgreSQL con read-back exacto. No calcula Opportunity Score ni rentabilidad.

## Límites de evidencia

El resultado mantiene separadas cuatro clases de información:

- **Observada:** membresía del cluster, títulos, descripciones y duraciones de videos disponibles en PostgreSQL.
- **Inferida:** scores de complejidad (investigación, footage, edición), costos de producción, horas estimadas, scores de riesgo y clasificaciones.
- **Supuestos:** umbrales y pesos editables en `app/config/production_risk_config.py`. Los scores son heurísticas basadas en señales de texto en metadatos, no costos cotizados ni análisis legal.
- **Desconocida:** evidencia ausente, inválida o insuficiente permanece como `UNKNOWN` o warning; no se imputa.

Los scores son indicadores comparativos internos de 0 a 100. No representan costos monetarios reales, horas confirmadas, riesgo legal garantizado ni probabilidad de éxito.

## Complejidad de producción

Por cluster se calculan tres dimensiones a partir de señales de texto en títulos y descripciones:

- **Investigación (Research):** términos como "research", "analysis", "explained", "tutorial", "science", "history", "why", "facts", "review"
- **Footage:** términos como "footage", "film", "movie", "music", "trailer", "gameplay", "football", "match"
- **Edición:** términos como "editing", "compilation", "top 10", "animation", "documentary", "explained", "montage"

Cada dimensión se puntúa 0–100 por frecuencia de términos coincidentes. El **Production Cost Score** combina:

```text
40% Investigación
30% Footage
30% Edición
```

La **Production Complexity** clasifica el Production Cost Score:

- `LOW`: < 40
- `MEDIUM`: 40–69
- `HIGH`: ≥ 70
- `UNKNOWN`: evidencia insuficiente

## Estimación de horas

```text
horas_base = minutos_mediana × horas_por_minuto_salida
factor_esfuerzo = 1 + (Production Cost Score / 100)
horas_low = horas_base × factor_esfuerzo × 0.5
horas_high = horas_base × factor_esfuerzo × 1.0
```

`horas_por_minuto_salida` configurable (default 0.5). Los rangos son orientativos, no cotizaciones.

**Cluster 9 (Cybersecurity Education):** Median duration 636.43 min (long-form tutorials/certification content). Production cost score 67.9. Calculated range 337.7–675.3 hours. Root cause: legitimate long median duration × effort factor. Not a unit conversion bug.

## Faceless Feasibility

Clasificación real basada en evidencia textual:

- `HIGH`: tutorial/explainer, screen recording, narration, slides/graphics, documentary style
- `MEDIUM`: mix of faceless-friendly and camera-dependent signals
- `LOW`: interview dependency, on-camera personality dependence, physical demonstration, third-party footage
- `UNKNOWN`: evidencia insuficiente

Exposes: observed evidence, inferred evidence, confidence, warnings.

## AI Assistance Potential

Clasificación real evaluando dimensiones separadas:

- `HIGH`: research, outline/script, translation, voice suitability, graphics, editing assistance, metadata/title assistance, fact-check burden
- `MEDIUM`: partial coverage of above dimensions
- `LOW`: minimal AI applicability
- `UNKNOWN`: evidencia insuficiente

High NO significa completamente automatizado.

## Expertise Requirement

Clasificación real usando semántica de contenido y requisitos de producción:

- `LOW`: contenido general, introductorio
- `MEDIUM`: conocimiento intermedio, guías técnicas
- `HIGH`: especialización técnica avanzada
- `SPECIALIST`: certificaciones, ingeniería, legal, médico, financiero
- `UNKNOWN`: evidencia insuficiente

NO se infiere solo de etiqueta de nicho.

## Repeatability

- **repeatability_score 0–100** basado en señales positivas/negativas
- **repeatability_band**: `HIGH` / `MEDIUM` / `LOW` / `UNKNOWN`

Evidencia positiva:
- repeatable script structure, screen recording, narration + graphics, stable research template, repeatable editing format

Evidencia negativa:
- exclusive interviews, field production, travel, one-off events, unique footage

NO usa profundidad Sprint 7 como prueba de volumen de ideas.

## Análisis de riesgo completo

Seis dimensiones de riesgo a partir de señales de texto:

- **Copyright:** términos como "music", "song", "film", "movie", "trailer", "clip", "copyright", "licensed"
- **Contenido reutilizado:** términos como "compilation", "reaction", "reacts", "mashup", "remix", "highlights"
- **Exposición regulatoria/sensible:** términos como "finance", "financial", "medical", "health", "legal", "politics", "war", "weapon", "violence", "suicide", "drug", "investment", "crypto", "trading"
- **Platform Policy:** exposición a políticas de plataforma (ej. armas, contenido regulado)
- **Accuracy:** riesgo de información desactualizada o incorrecta (términos temporales, tecnologías cambiantes)
- **Update Burden:** frecuencia esperada de actualizaciones necesarias
- **Source Dependency:** dependencia de fuentes externas, entrevistas, footage de terceros

Cada dimensión se puntúa 0–100. El **Overall Risk Score** combina:

```text
25% Copyright
20% Contenido reutilizado
20% Exposición regulatoria
15% Platform Policy
10% Accuracy
10% Update Burden
```

El **Risk Level** clasifica el Overall Risk Score:

- `LOW`: < 35
- `MEDIUM`: 35–64
- `HIGH`: ≥ 65
- `UNKNOWN`: evidencia insuficiente

Cada dimensión expone: level, score, confidence, observed evidence, inferred evidence, warnings.

**Regla:** `UNKNOWN != LOW`, `UNKNOWN != 0`, no observed signal != zero risk.

## Production Attractiveness

Score 0–100 usando componentes conocidos únicamente:

```text
Inputs:
- production_feasibility (inverse production complexity)
- inverse cost index (inverse production_cost_score)
- faceless_feasibility
- AI assistance potential
- repeatability
- inverse overall risk

Component coverage: % of inputs available (not UNKNOWN)
Confidence: coverage-weighted confidence
Warnings: coverage gaps
```

If coverage below 50%:
- `available = false`
- `score = None`

UNKNOWN inputs do NOT improve score.

## Confianza

Combina completitud de datos (títulos, descripciones, duraciones) y tamaño de muestra del cluster. Acotada 0–100.

- Clusters con < 5 videos: penalización de confianza (90% base)
- Campos desconocidos reducen confianza proporcionalmente

## Contrato approved de Sprint 5

La CLI reutiliza sin modificar el pipeline determinista aprobado:

- videos de producción: **83**
- clusters: **10**
- dataset hash: `4d81c80e8da54b371c7eb969957ea347fc632d82abd737719141c866f4bfe9ad`
- assignments hash: `6c0e7bb6aeec75985664becb05f7c61cbfec874c15a6ec7395d60c2996436288`
- silhouette: `0.2468982051367785`

Cualquier desviación detiene la ejecución.

## Exclusión de test records

`VID_TEST_INTEGRATION_99` se excluye explícitamente del dataset de producción. Verificado ausente en cada ejecución.

## Ejecución

Análisis read-only por defecto:

```powershell
$env:PYTHONIOENCODING='utf-8'
.\.venv\Scripts\python.exe scripts\analyze_production_risk.py --json
```

La ejecución audita videos de producción, valida el contrato de Sprint 5, enriquece con métricas de Sprint 7, ejecuta el motor de riesgo y valida funcionalmente. Sin `--persist` no realiza escrituras.

## Persistencia PostgreSQL

Primero se aplica la migración controlada:

```powershell
.\.venv\Scripts\python.exe scripts\migrate_sprint8_schema.py
```

Crea tabla `production_risk_analyses` con unicidad `(run_id, cluster_id)`.

Persistencia explícita:

```powershell
.\.venv\Scripts\python.exe scripts\analyze_production_risk.py --json --persist
```

Se escribe un registro por cluster con payload completo en JSONB. Antes de la transacción se verifica el esquema. Después se leen todos los registros del `run_id` y se exige igualdad exacta: cantidad, clusters únicos, duplicados, orphans, missing y payload normalizado. Una discrepancia hace fallar la ejecución.

## Métricas reportadas por cluster

- `cluster_id`, `microniche`, `video_count`
- `production_complexity` (LOW/MEDIUM/HIGH/UNKNOWN)
- `production_feasibility` (inverso de complejidad: HIGH/MEDIUM/LOW)
- `cost_class` (VERY_LOW/LOW/MEDIUM/HIGH/VERY_HIGH/UNKNOWN) — derivada de production_cost_score
- `faceless_feasibility` (HIGH/MEDIUM/LOW/UNKNOWN) — con evidencia y confidence
- `ai_assistance_potential` (HIGH/MEDIUM/LOW/UNKNOWN) — con evidencia y confidence
- `expertise_requirement` (LOW/MEDIUM/HIGH/SPECIALIST/UNKNOWN) — con evidencia y confidence
- `copyright_risk` (LOW/MEDIUM/HIGH/UNKNOWN) — derivada de copyright_risk_score
- `platform_policy_risk` (LOW/MEDIUM/HIGH/UNKNOWN) — con score y confidence
- `accuracy_risk` (LOW/MEDIUM/HIGH/UNKNOWN) — con score y confidence
- `update_burden` (LOW/MEDIUM/HIGH/UNKNOWN) — con score y confidence
- `source_dependency` (LOW/MEDIUM/HIGH/UNKNOWN) — con score y confidence
- `repeatability_score` (0–100)
- `repeatability_band` (HIGH/MEDIUM/LOW/UNKNOWN)
- `overall_risk` (LOW/MEDIUM/HIGH/UNKNOWN) — derivada de overall_risk_score
- `production_attractiveness_score` (0–100, available/unavailable, coverage, confidence)
- `confidence` (0–100)
- `warnings`

## Métricas de calidad (Sprint8QualityMetrics)

- `faceless_unknown_rate` — % clusters con faceless_feasibility = UNKNOWN
- `ai_assistance_unknown_rate` — % clusters con ai_assistance_potential = UNKNOWN
- `expertise_unknown_rate` — % clusters con expertise_requirement = UNKNOWN
- `platform_risk_unknown_rate` — % clusters con platform_policy_risk = UNKNOWN
- `accuracy_risk_unknown_rate` — % clusters con accuracy_risk = UNKNOWN
- `update_burden_unknown_rate` — % clusters con update_burden = UNKNOWN
- `source_dependency_unknown_rate` — % clusters con source_dependency = UNKNOWN
- `repeatability_unknown_rate` — % clusters con repeatability_band = UNKNOWN
- `attractiveness_unavailable_rate` — % clusters con production_attractiveness_available = false

Calculadas desde outputs finales reales. 10/10 UNKNOWN reporta 100.0%, no 0%.

## Limitaciones conocidas

1. **Costos monetarios:** No se inventan. `cost_class` es derivada ordinal del Production Cost Score.
2. **Tabla PostgreSQL:** Nombre real `production_risk_analyses` (no `cluster_production_risk_analyses`).
3. **Múltiples runs persistidos:** Durante validación se crearon varios runs.
