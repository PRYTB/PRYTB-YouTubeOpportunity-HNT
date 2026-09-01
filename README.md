# PRYTB-YouTubeOpportunity-HNT

## Misión Resumida

Motor privado de inteligencia para descubrir, analizar y validar oportunidades rentables dentro de YouTube en nichos en español e internacionales.

## Estado Actual

```text
Sprint 0: Environment / Infrastructure (READY)
Sprint 1: YouTube Data Collector (COMPLETE)
Next: Sprint 2 — InsForge Persistence
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
.\.venv\Scripts\python run_healthcheck.py
```

## Tests

Tests unitarios (sin llamadas a APIs reales ni consumo de cuotas):

```powershell
.\.venv\Scripts\python -m pytest -m "not integration" -v
```

Tests de integración (conectividad real):

```powershell
.\.venv\Scripts\python -m pytest -m integration -v
```

## Estructura del Proyecto

```text
I:\PRYTB
│
├── app\
│   ├── agents\        # Agentes de inteligencia
│   ├── analytics\     # Motores estadísticos
│   ├── collectors\    # YouTubeClient y colectores
│   ├── database\      # InsForgeClient y persistencia
│   ├── models\        # Modelos de datos
│   ├── orchestrator\  # Orquestador del sistema
│   ├── scoring\       # Motores de scoring
│   ├── services\      # Servicios de negocio
│   └── utils\         # Configuración y Logging centralizados
├── dashboard\         # Interfaz visual (Streamlit)
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

* El archivo `.env` está estricta y permanentemente en `.gitignore` y des-trackeado de Git.
* Todas las API Keys se manejan de forma enmascarada usando `pydantic.SecretStr`.
* Nunca se imprimen claves ni secretos en consola ni en logs.

## Siguiente Sprint

* **Sprint 1:** YouTube Data Collector (COMPLETADO)
* **Sprint 2:** InsForge Persistence
