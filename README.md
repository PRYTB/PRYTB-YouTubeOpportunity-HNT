# PRYTB-YouTubeOpportunity-HNT

## Misión Resumida

Motor privado de inteligencia para descubrir, analizar y validar oportunidades rentables dentro de YouTube en nichos en español e internacionales.

## Estado Actual

```text
Sprint 0: Environment / Infrastructure (COMPLETE)
Sprint 1: YouTube Data Collector (COMPLETE)
Sprint 2: InsForge Persistence (COMPLETE)
Sprint 3: Historical Metrics (COMPLETE)
Sprint 4: Outlier Engine (COMPLETE)
Sprint 5: Niche Miner (COMPLETE)
Sprint 6: Revenue + Geography (COMPLETE)
Sprint 7: Competition + Depth + Evergreen (COMPLETE)
Sprint 8: Production Feasibility + Risk (COMPLETE)
```

Ruta raíz oficial y definitiva: `I:\PRYTB`

## Stack Definitivo

```text
Python 3.12+
YouTube Data API v3
InsForge Backend
OmniRoute (Administrado vía entorno TRAE)
Streamlit (Futuro Dashboard)
Pytest (Testing suite)
```

## Creación del Entorno Virtual (.venv)

El proyecto requiere **Python 3.12+**. Para recrear o configurar el entorno virtual oficial:

```powershell
py -3.12 -m venv .venv
```

Activar entorno:

```powershell
.\.venv\Scripts\activate
```

## Instalación de Dependencias

Actualizar herramientas básicas e instalar dependencias justificadas:

```powershell
.\.venv\Scripts\python.exe -m pip install --upgrade pip setuptools wheel
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip check
```

## Configuración (.env)

Copiar `.env.example` a `.env` y configurar las claves necesarias:

```env
YOUTUBE_API_KEY=
INSFORGE_URL=
INSFORGE_API_KEY=
INSFORGE_ANON_KEY=

APP_ENV=development
LOG_LEVEL=INFO
```

> **Nota sobre OmniRoute:** OmniRoute se encuentra gestionado directamente por la integración interna del entorno TRAE. No se requiere ni debe definirse `OMNIROUTE_API_KEY` en `.env`.

## Healthcheck

Para validar el entorno completo, configuración, seguridad e integraciones:

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
$env:PYTHONIOENCODING='utf-8'
.\.venv\Scripts\python.exe run_healthcheck.py
```

## Tests

Tests unitarios y de regresión local:

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
$env:PYTHONIOENCODING='utf-8'
.\.venv\Scripts\python.exe -m compileall app tests scripts
.\.venv\Scripts\python.exe -m pytest -m "not integration" -q
```

Tests de integración (conectividad real):

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
$env:PYTHONIOENCODING='utf-8'
.\.venv\Scripts\python.exe -m pytest -m integration -q
```

## Sprint 7

El análisis de competencia, accesibilidad de entrada, profundidad de contenido y evergreen es read-only por defecto:

```powershell
.\.venv\Scripts\python.exe scripts\analyze_market_structure.py --json
```

Para habilitar persistencia explícita en InsForge, aplicar primero la migración y usar `--persist`; la ejecución exige read-back exacto:

```powershell
.\.venv\Scripts\python.exe scripts\migrate_sprint7_schema.py
.\.venv\Scripts\python.exe scripts\analyze_market_structure.py --json --persist
```

Metodología y límites de evidencia: [docs/SPRINT_7_COMPETITION_DEPTH_EVERGREEN.md](docs/SPRINT_7_COMPETITION_DEPTH_EVERGREEN.md).

## Sprint 8

Sprint 8 completa el motor de **Production Feasibility + Risk** sobre el dataset aprobado de Sprint 5:

- **83 videos de producción**
- **10 clusters aprobados**
- **sin reclustering**
- exclusión explícita de `VID_TEST_INTEGRATION_99`
- persistencia opcional en `production_risk_analyses` con **read-back exacto**

### Qué calcula Sprint 8

Por cluster reporta:

- `production_complexity`
- `production_feasibility`
- `production_cost_score`
- `estimated_hours_low` / `estimated_hours_high`
- `faceless_feasibility`
- `ai_assistance_potential`
- `expertise_requirement`
- `repeatability_score` / `repeatability_band`
- `copyright_risk`
- `platform_policy_risk`
- `accuracy_risk`
- `update_burden`
- `source_dependency`
- `overall_risk`
- `production_attractiveness_score`
- `coverage`, `confidence`, `warnings`

### Reglas de Sprint 8

- `UNKNOWN != LOW`
- `UNKNOWN != 0`
- un input `UNKNOWN` no mejora `production_attractiveness_score`
- si cobertura < 50%, `production_attractiveness_available = false`
- quality metrics se calculan desde los outputs finales reales por cluster

### Fórmula de horas

```text
horas_base = minutos_mediana × horas_por_minuto_salida
factor_esfuerzo = 1 + (production_cost_score / 100)
horas_low = horas_base × factor_esfuerzo × 0.5
horas_high = horas_base × factor_esfuerzo × 1.0
```

Las horas son estimaciones comparativas, no costos monetarios.

### Ejecución Sprint 8

Read-only:

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
$env:PYTHONIOENCODING='utf-8'
.\.venv\Scripts\python.exe scripts\analyze_production_risk.py --json
```

Persistencia explícita:

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
$env:PYTHONIOENCODING='utf-8'
.\.venv\Scripts\python.exe scripts\migrate_sprint8_schema.py
.\.venv\Scripts\python.exe scripts\analyze_production_risk.py --json --persist
```

Metodología, fórmulas, confidence, UNKNOWN handling, coverage y limitaciones: [docs/SPRINT_8_PRODUCTION_RISK.md](docs/SPRINT_8_PRODUCTION_RISK.md).

## Estructura del Proyecto

```text
I:\PRYTB
│
├── app\
│   ├── agents\        # Agentes de inteligencia
│   ├── analytics\     # Motores estadísticos
│   ├── collectors\    # YouTubeClient y colectores
│   ├── config\        # Configuración analítica
│   ├── database\      # InsForgeClient y persistencia
│   ├── models\        # Modelos de datos
│   ├── scoring\       # Motores de scoring
│   ├── services\      # Servicios de negocio
│   └── utils\         # Configuración y logging centralizados
├── tests\
│   ├── unit\          # Unit tests aislados
│   └── integration\   # Pruebas de integración
├── data\              # Almacenamiento local (raw, processed, exports)
├── docs\              # Documentación de sprints y decisiones
├── config\            # Archivos de configuración
├── scripts\           # Scripts utilitarios
├── logs\              # Logs de la aplicación (prytb.log)
├── .env.example
├── .gitignore
├── requirements.txt
├── README.md
├── pytest.ini
├── run_healthcheck.py
├── PRYTB_MASTER_PROMPT.md
└── PRYTB_GANTT.md
```

## Seguridad

- El archivo `.env` está estricta y permanentemente en `.gitignore` y des-trackeado de Git.
- Todas las API keys se manejan de forma enmascarada usando `pydantic.SecretStr`.
- Nunca se imprimen claves ni secretos en consola ni en logs.

## Sprints completados

- **Sprint 1:** YouTube Data Collector
- **Sprint 2:** InsForge Persistence
- **Sprint 3:** Historical Metrics & Velocity
- **Sprint 4:** Outlier Engine
- **Sprint 5:** Niche Miner
- **Sprint 6:** Revenue + Geography
- **Sprint 7:** Competition + Depth + Evergreen
- **Sprint 8:** Production Feasibility + Risk
