# Sprint 7 — Competition, Accessibility, Depth + Evergreen

## Estado

Completo. Sprint 7 analiza la estructura de mercado de los clusters de producción aprobados en Sprint 5. Añade competencia, accesibilidad realista de entrada, profundidad de contenido y persistencia opcional en InsForge. No calcula Opportunity Score, costos ni riesgo.

## Límites de evidencia

El resultado mantiene separadas cuatro clases de información:

- **Observada:** membresía del cluster, distribución de canales, vistas, suscriptores y fechas disponibles en InsForge.
- **Inferida:** scores, bandas de profundidad, clasificación evergreen y clasificación funcional.
- **Supuestos:** umbrales y pesos editables en `app/config/market_structure_config.py`.
- **Desconocida:** evidencia ausente, inválida, futura o insuficiente permanece como `None`, `UNKNOWN` o warning; no se imputa.

Los scores son indicadores comparativos internos de 0 a 100. No representan rentabilidad, probabilidad garantizada de éxito ni un Opportunity Score.

## Competencia

Por cluster se observan:

- número de canales;
- participación del canal dominante;
- HHI de canales, expresado de 0 a 100;
- suscriptores medios conocidos;
- edad mediana conocida de los canales;
- tasa de canales nuevos.

El Competition Score combina:

```text
30% cantidad de canales
35% concentración
20% tamaño medio de canales
15% madurez de canales
```

Cuando falta tamaño o antigüedad se usan componentes neutrales explícitos; la confianza y los warnings reflejan la falta de evidencia.

## Accesibilidad de entrada

Small Channel Success Rate mide videos de canales con hasta 50.000 suscriptores cuyo desempeño alcanza el ratio configurado respecto de la mediana de otros videos del mismo canal. El video evaluado se excluye por `video_id`, no por igualdad de vistas. Se requieren al menos dos videos válidos de baseline y una mediana mayor que cero.

El Accessibility Score combina:

```text
50% Small Channel Success Rate
25% tasa de nuevos entrantes
25% baja concentración
```

Se clasifica como `LOW`, `MEDIUM`, `HIGH` o `UNKNOWN`. Una muestra insuficiente no se transforma en éxito observado.

## Profundidad de contenido

La profundidad usa únicamente títulos observados y firmas deterministas de sus primeras palabras relevantes. No genera ni inventa listas de ideas. La capacidad se comunica como banda conservadora:

- `BELOW_20`;
- `20_PLUS`;
- `50_PLUS`;
- `100_PLUS`;
- `UNKNOWN` cuando no existen títulos utilizables.

La falta de títulos no clasifica automáticamente un nicho como limitado.

## Evergreen

Se usan edades válidas de publicación y amplitud temporal del cluster:

- `TREND`: predominio reciente sin evidencia madura;
- `EVERGREEN`: tasa madura y amplitud temporal suficientes;
- `SEMI_EVERGREEN`: evidencia temporal intermedia;
- `UNKNOWN`: fechas ausentes, inválidas o futuras.

Evergreen Score combina 60% de tasa de videos maduros y 40% de amplitud temporal normalizada.

## Clasificación funcional

La clasificación final distingue:

- `VIRAL_SATURATED`: competencia alta y mediana de vistas sobre el umbral viral;
- `CONTENT_CONSTRAINED`: evidencia de profundidad presente pero score insuficiente;
- `SUSTAINABLE_ACCESSIBLE`: accesibilidad media/alta y comportamiento no puramente trend;
- `UNCERTAIN`: evidencia o condiciones insuficientes.

El orden es deliberado: saturación viral tiene precedencia, seguida por limitación demostrable de profundidad. No se introduce un score compuesto de oportunidad.

## Calidad y confianza

Se reportan tasas de desconocidos para suscriptores, vistas y fechas de publicación, además de clusters sin muestra elegible de canales pequeños. Booleanos, negativos y valores no finitos no se aceptan como métricas. Fechas futuras o inválidas son desconocidas.

La confianza combina completitud de suscriptores, edades de canal, fechas de video y vistas, con un factor por tamaño de muestra. Todos los scores y porcentajes están acotados a 0–100.

## Contrato aprobado de Sprint 5

La CLI reutiliza sin modificar el pipeline determinista aprobado:

- videos de producción: **83**;
- clusters: **10**;
- dataset hash: `4d81c80e8da54b371c7eb969957ea347fc632d82abd737719141c866f4bfe9ad`;
- assignments hash: `6c0e7bb6aeec75985664becb05f7c61cbfec874c15a6ec7395d60c2996436288`;
- silhouette: `0.2468982051367785`.

Cualquier desviación detiene la ejecución.

## Ejecución

Análisis read-only por defecto:

```powershell
$env:PYTHONIOENCODING='utf-8'
.\.venv\Scripts\python.exe scripts\analyze_market_structure.py --json
```

La ejecución reúne metadatos estáticos y selecciona el snapshot cronológicamente más reciente de `video_metrics` y `channel_metrics`. Sin `--persist` no realiza escrituras.

## Persistencia InsForge

Primero se aplica la migración controlada:

```powershell
.\.venv\Scripts\python.exe scripts\migrate_sprint7_schema.py
```

Persistencia explícita:

```powershell
.\.venv\Scripts\python.exe scripts\analyze_market_structure.py --json --persist
```

Se escribe un registro por cluster en `market_structure_analyses`, con unicidad `(run_id, cluster_id)`, scores desnormalizados y payload completo en JSONB. Antes del POST se verifica el esquema. Después se leen todos los registros del `run_id` y se exige igualdad exacta, incluyendo cantidad, clusters únicos, duplicados y payload normalizado. Una discrepancia hace fallar la ejecución.

## Pruebas

Las pruebas cubren validación de modelos y configuración, HHI y concentración, baseline por identidad, muestra insuficiente, bandas 20/50/100+, fechas inválidas/futuras, clasificaciones evergreen y funcionales, unknowns, snapshots ISO/UTC, enriquecimiento sin mutación, persistencia por cluster, preflight, read-back exacto, diferencias de integridad, endpoint de migración y fallos HTTP, JSON, semánticos o de red. La integración usa datos reales aprobados y verifica cero POST en modo read-only.

```powershell
.\.venv\Scripts\python.exe -m pytest -m "not integration" -v
.\.venv\Scripts\python.exe -m pytest -m integration -v
```
