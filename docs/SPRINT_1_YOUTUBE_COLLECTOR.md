# SPRINT 1: YOUTUBE DATA COLLECTOR

## Objetivo
Construir un **YouTube Data Collector robusto, modular y testeable** utilizando exclusivamente la API v3 oficial de YouTube Data API, orquestando el flujo completo de adquisición:
`keyword` → `search.list` → `video IDs` → `videos.list` (batches) → `channel IDs` → `channels.list` (batches) → `normalización` → `CollectionResult`.

---

## Arquitectura

```text
app/
├── collectors/
│   ├── youtube_client.py   # Comunicación HTTP de bajo nivel con retries y exception mapping
│   ├── youtube_collector.py# Orquestador del flujo de colección
│   └── quota_tracker.py    # Estimación y observabilidad de consumo de cuota API
└── models/
    └── youtube.py          # Dataclass / Pydantic models (YouTubeVideo, YouTubeChannel, CollectionResult)

scripts/
└── collect_youtube_sample.py # CLI para ejecutar recolección y exportar JSON opcional
```

---

## Operaciones API v3 y Batching

1. **search.list** (`part=snippet`, `type=video`):
   - Soporta paginación continua mediante `nextPageToken` hasta alcanzar el límite solicitado (`max_results`).
   - Evita peticiones innecesarias tras satisfacer la cantidad requerida.

2. **videos.list** (`part=snippet,statistics,contentDetails,status`):
   - Deduplica los IDs de video manteniendo el orden de relevancia.
   - Ejecuta peticiones en batches de máximo 50 IDs por request (`chunked(video_ids, 50)`).

3. **channels.list** (`part=snippet,statistics`):
   - Extrae los IDs de canal únicos asociados a los videos resueltos.
   - Ejecuta peticiones en batches de máximo 50 IDs por request (`chunked(channel_ids, 50)`).

---

## Normalización de Datos

- **Duraciones ISO 8601:** Conversión de patrones tipo `PT45S`, `PT8M30S`, `PT1H2M5S` a segundos enteros (`duration_seconds`).
- **Métricas Numéricas:** Conversión segura de strings a `int | None` (view_count, like_count, comment_count, subscriber_count, video_count).
- **Hidden Subscriber Count:** Cuando `hiddenSubscriberCount == True`, se preserva `subscriber_count = None` y `hidden_subscriber_count = True` sin inventar métricas.
- **Campos Ausentes / Respuestas Parciales:** Videos eliminados o privados o ausencias de datos se registran como `warnings` en `CollectionResult` sin interrumpir la ejecución global.

---

## Observabilidad y Quota Tracker

Consumo centralizado estimado:
- `search.list`: 100 unidades por página
- `videos.list`: 1 unidad por batch
- `channels.list`: 1 unidad por batch

`QuotaTracker` registra cada operación y proporciona un resumen estructurado en `CollectionStats`.

---

## Manejo de Errores y Retries

Se definen excepciones especializadas:
- `YouTubeAuthError`: Errores 401/403 de autenticación o API key inválida (sin retries).
- `YouTubeQuotaExceededError`: Superación de la cuota oficial (sin retries).
- `YouTubeRateLimitError`: Respuestas 429 de rate limiting (reintentables).
- `YouTubeAPIError`: Errores de red o de servidor 5xx (reintentables con backoff exponencial, máximo 3 intentos).
- `InvalidResponseError`: Respuestas JSON corruptas o malformadas.

---

## Ejecución del Script de Muestra

Ejecutar recolección desde la línea de comandos:

```powershell
.\.venv\Scripts\python scripts/collect_youtube_sample.py --query "artificial intelligence" --max-videos 50 --export
```

Salida esperada:

```text
==================================================
PRYTB — YOUTUBE COLLECTION
==================================================
Query: artificial intelligence
Requested: 50
Videos collected: 50
Channels collected: XX
API requests: X
Estimated quota: X
Elapsed: X.Xs

Status: OK
==================================================
```

Los exportaciones de prueba se almacenan en `data/exports/` en formato JSON no trackeado por git.
