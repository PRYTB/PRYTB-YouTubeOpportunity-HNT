# Sprint 8 — Production Feasibility + Risk Engine

## Estado

Completo. Sprint 8 analiza la viabilidad de producción y el riesgo de los clusters aprobados en Sprint 5. Añade complejidad de producción, estimación de horas, costos de producción y análisis de riesgo (copyright, contenido reutilizado, exposición regulatoria). Persistencia opcional en InsForge con read-back exacto. No calcula Opportunity Score ni rentabilidad.

## Límites de evidencia

El resultado mantiene separadas cuatro clases de información:

- **Observada:** membresía del cluster, títulos, descripciones y duraciones de videos disponibles en InsForge.
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

## Análisis de riesgo

Tres dimensiones de riesgo a partir de señales de texto:

- **Copyright:** términos como "music", "song", "film", "movie", "trailer", "clip", "copyright", "licensed"
- **Contenido reutilizado:** términos como "compilation", "reaction", "reacts", "mashup", "remix", "highlights"
- **Exposición regulatoria/sensible:** términos como "finance", "financial", "medical", "health", "legal", "politics", "war", "weapon", "violence", "suicide", "drug", "investment", "crypto", "trading"

Cada dimensión se puntúa 0–100. El **Overall Risk Score** combina:

```text
40% Copyright
30% Contenido reutilizado
30% Exposición regulatoria
```

El **Risk Level** clasifica el Overall Risk Score:

- `LOW`: < 35
- `MEDIUM`: 35–64
- `HIGH`: ≥ 65
- `UNKNOWN`: evidencia insuficiente

## Confianza

Combina completitud de datos (títulos, descripciones, duraciones) y tamaño de muestra del cluster. Acotada 0–100.

- Clusters con < 5 videos: penalización de confianza (90% base)
- Campos desconocidos reducen confianza proporcionalmente

## Contrato aprobado de Sprint 5

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

## Persistencia InsForge

Primero se aplica la migración controlada:

```powershell
.\.venv\Scripts\python.exe scripts\migrate_sprint8_schema.py
```

Crea tabla `production_risk_analyses` con unicidad `(run_id, cluster_id)`.

Persistencia explícita:

```powershell
.\.venv\Scripts\python.exe scripts\analyze_production_risk.py --json --persist
```

Se escribe un registro por cluster con payload completo en JSONB. Antes del POST se verifica el esquema. Después se leen todos los registros del `run_id` y se exige igualdad exacta: cantidad, clusters únicos, duplicados, orphans, missing y payload normalizado. Una discrepancia hace fallar la ejecución.

## Métricas reportadas por cluster

- `cluster_id`, `microniche`, `video_count`
- `production_complexity` (LOW/MEDIUM/HIGH/UNKNOWN)
- `production_feasibility` (inverso de complejidad: HIGH/MEDIUM/LOW)
- `cost_class` (VERY_LOW/LOW/MEDIUM/HIGH/VERY_HIGH/UNKNOWN) — derivada de production_cost_score
- `faceless_feasibility` — UNKNOWN (no implementado en Sprint 8)
- `ai_assistance_potential` — UNKNOWN (no implementado en Sprint 8)
- `expertise_requirement` — UNKNOWN (no implementado en Sprint 8)
- `copyright_risk` (LOW/MEDIUM/HIGH/UNKNOWN) — derivada de copyright_risk_score
- `platform_policy_risk` — UNKNOWN (no implementado en Sprint 8)
- `accuracy_risk` — UNKNOWN (no implementado en Sprint 8)
- `update_burden` — UNKNOWN (no implementado en Sprint 8)
- `source_dependency` — UNKNOWN (no implementado en Sprint 8)
- `repeatability` — UNKNOWN (no implementado en Sprint 8)
- `overall_risk` (LOW/MEDIUM/HIGH/UNKNOWN) — derivada de overall_risk_score
- `production_attractiveness` — no implementado en Sprint 8 (ver limitaciones)
- `confidence` (0–100)
- `warnings`

## Limitaciones conocidas

1. **Producción atractiva (production_attractiveness):** No existe score nativo en Sprint 8. El ranking de "Top 5 Production Candidates" usa proxy: menor Production Cost Score + menor Overall Risk Score.
2. **Campos UNKNOWN:** `faceless_feasibility`, `ai_assistance_potential`, `expertise_requirement`, `platform_policy_risk`, `accuracy_risk`, `update_burden`, `source_dependency`, `repeatability` no están implementados en Sprint 8 y se reportan como `UNKNOWN`.
3. **Costos monetarios:** No se inventan. `cost_class` es derivada ordinal del Production Cost Score.
3. **Tabla InsForge:** Nombre real `production_risk_analyses` (no `cluster_production_risk_analyses`).
4. **Múltiples runs persistidos:** Durante validación se crearon varios runs. El run de referencia para este reporte es `sprint8-334b32bc-5143-42be-bbdd-3481b9779f21`.

## Pruebas

```powershell
.\.venv\Scripts\python.exe -m pytest -m "not integration" -v
.\.venv\Scripts\python.exe -m pytest -m integration -v
```

Cubren validación de modelos, configuración, clasificación complejidad/riesgo, estimación horas, señales de texto, persistencia, read-back exacto, validación funcional, contrato Sprint 5, exclusión test record, fallos HTTP/JSON/semánticos.