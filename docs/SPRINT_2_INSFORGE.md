# SPRINT 2 — INSFORGE PERSISTENCE DOCUMENTATION

Proyecto: `PRYTB-YouTubeOpportunity-HNT`  
Ruta: `I:\PRYTB`  
Fecha de actualización: 2026-09-01  
Estado: **COMPLETADO / GO**

---

## 1. ESQUEMA DE BASE DE DATOS (INSFORGE POSTGRESQL)

El modelo relacional persiste datos recolectados de YouTube API v3 en InsForge PostgreSQL mediante 4 tablas principales con integridad referencial (PK y FK):

```text
  +------------------+             +--------------------+
  |     channels     |             |  channel_metrics   |
  +------------------+             +--------------------+
  | PK: channel_id   |<------------| PK: id (auto)      |
  | title            |             | FK: channel_id     |
  | description      |             | subscriber_count   |
  | published_at     |             | video_count        |
  | country          |             | view_count         |
  +------------------+             | collected_at (UTC) |
          ^                        +--------------------+
          |
          |
  +-------+----------+             +--------------------+
  |      videos      |             |   video_metrics    |
  +------------------+             +--------------------+
  | PK: video_id     |<------------| PK: id (auto)      |
  | FK: channel_id   |             | FK: video_id       |
  | title            |             | view_count         |
  | description      |             | like_count         |
  | published_at     |             | comment_count      |
  | duration         |             | collected_at (UTC) |
  | duration_seconds |             +--------------------+
  | caption          |
  | definition       |
  | licensed_content |
  | default_language |
  | default_audio_lan|
  +------------------+
```

### Relaciones e Índices
* `channels.channel_id` (VARCHAR / TEXT, PK): ID único del canal devuelto por YouTube.
* `videos.video_id` (VARCHAR / TEXT, PK): ID único del video devuelto por YouTube.
* `videos.channel_id` (FK -> `channels.channel_id`): Enlace referencial.
* `channel_metrics.channel_id` (FK -> `channels.channel_id`).
* `video_metrics.video_id` (FK -> `videos.video_id`).

---

## 2. API ENDPOINTS DE INSFORGE UTILIZADOS

InsForge provee una API REST optimizada para PostgreSQL.

* **Endpoint Base de Registros**: `/api/database/records/{table_name}`
* **Headers requeridos**:
  * `Authorization`: `Bearer <INSFORGE_API_KEY>`
  * `Content-Type`: `application/json`
  * `Prefer`: `resolution=merge-duplicates` (Únicamente para operaciones UPSERT).

---

## 3. ESTRATEGIA DE UPSERT E IDEMPOTENCIA

### 3.1 Entidades Primarias (`channels`, `videos`)
Para evitar duplicados en dimensiones primarias (`channels` y `videos`), se utiliza **UPSERT** enviando el header HTTP `Prefer: resolution=merge-duplicates` en las peticiones `POST` de InsForge.
* Si el `channel_id` o `video_id` existe, PostgreSQL ejecuta un `UPDATE/MERGE` actualizando los metadatos.
* Si no existe, ejecuta un `INSERT`.
* **Resultado**: Conteo de duplicados = 0 en re-ejecuciones.

### 3.2 Tablas de Métricas / Snapshots (`channel_metrics`, `video_metrics`)
Para las tablas de métricas históricas se utiliza **INSERT sin upsert**.
* Cada ejecución registra una instantánea (snapshot) asociando la métrica actual con `collected_at` en ISO 8601 UTC.
* Soporta reintentos e idempotencia mediante trazabilidad de timestamps de colección (`checked_at`).

---

## 4. BATCHING Y LOGGING

Las operaciones se ejecutan en llamadas batch oficial a la API REST de InsForge enviando arreglos de objetos JSON:
* `1 HTTP POST` por conjunto de canales (`channels`).
* `1 HTTP POST` por conjunto de videos (`videos`).
* `1 HTTP POST` por conjunto de métricas de canal (`channel_metrics`).
* `1 HTTP POST` por conjunto de métricas de video (`video_metrics`).

Total de operaciones de base de datos por ejecución estándar: **4 DB Operations**.

Métricas capturadas en `PersistenceResult`:
* `channels_received`
* `channels_upserted`
* `videos_received`
* `videos_upserted`
* `channel_metrics_inserted`
* `video_metrics_inserted`
* `db_operations`
* `warnings`
* `elapsed_seconds`

---

## 5. REPOSITORY CLASS: `YouTubeRepository`

Ubicación: `app/database/repositories.py`

Métodos implementados:
```python
upsert_channels(channels: List[YouTubeChannel]) -> int
upsert_videos(videos: List[YouTubeVideo]) -> int
insert_channel_metrics(channels: List[YouTubeChannel], checked_at: Optional[str] = None) -> int
insert_video_metrics(videos: List[YouTubeVideo], checked_at: Optional[str] = None) -> int
persist_collection(collection_result: CollectionResult, checked_at: Optional[str] = None) -> PersistenceResult
```

---

## 6. RESULTADOS DE VERIFICACIÓN END-TO-END (LIVE DB)

### Run #1 (`artificial intelligence`, max 50)
* **Videos recolectados**: 50
* **Canales recolectados**: 42
* **Videos persistidos**: 50
* **Canales persistidos**: 42
* **DB Operations**: 4

### Run Idempotencia (Re-ejecución)
* Re-ejecución inmediata de la misma consulta.
* **Canales duplicados**: 0
* **Videos duplicados**: 0

### Run #2 (`cybersecurity`, max 15)
* **Videos adicionales recolectados**: 15
* **Canales adicionales recolectados**: 12

### Estado Acumulado Final en Base de Datos Real
* `videos`: **83**
* `channels`: **63**
* `video_metrics`: **115**
* `channel_metrics`: **98**
* **FK Errors**: 0
* **Duplicados**: 0

---

## 7. SUITE DE TESTING

* **Unit Tests (`tests/unit/test_repositories.py`)**: Cobertura completa con mocks para upserts, insert de métricas, manejo de nulos, estructura `PersistenceResult`, idempotencia, timeouts HTTP (504), fallos de autenticación (401) y violaciones de restricciones FK/constraints (400).
* **Integration Tests (`tests/integration/test_insforge_persistence.py`)**: Validado contra la instancia en vivo de InsForge PostgreSQL usando `@pytest.mark.integration`.

---

## 8. MANEJO DE ERRORES Y LIMITACIONES CONOCIDAS

* Si la API Key de InsForge no está presente o es inválida, `YouTubeRepository` eleva `InsForgeClientError`.
* Si un video intenta insertarse con un `channel_id` inexistente, InsForge responde HTTP 400 y se cancela la transacción manteniendo integridad FK.
