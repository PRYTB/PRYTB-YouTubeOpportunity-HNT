# PRYTB — CARTA GANTT MAESTRA
## YouTube Opportunity Hunter

**Ruta del proyecto:** `I:\PRYTB`
**Base de datos única:** PostgreSQL local (`localhost:5433`, DB `prytb`, User `prytb_app`)
**Inicio:** Sprint 0  
**Metodología:** Sprint gated — no avanzar con defectos críticos  

> Las duraciones son estimaciones de esfuerzo relativo, no compromisos de calendario. Cada fase sólo avanza si pasa su Gate.

---

# 1. RESUMEN EJECUTIVO

| Fase | Sprint | Entregable principal | Gate |
|---|---:|---|---|
| Setup | 0 | Entorno PRYTB operativo | GO/FIX |
| Datos | 1 | YouTube API funcionando | GO/FIX |
| Datos | 2 | PostgreSQL conectado | GO/FIX |
| Datos | 3 | Históricos + velocity | GO/FIX |
| Inteligencia | 4 | Outlier Engine | GO/FIX |
| Inteligencia | 5 | Niche Miner | GO/FIX |
| Monetización | 6 | Revenue + Geography | GO/FIX |
| Mercado | 7 | Competition + Depth + Evergreen | GO/FIX |
| Viabilidad | 8 | Production + Risk | GO/FIX |
| Scoring | 9 | Profitability Engine | GO/FIX |
| Validación | 10 | Validator adversarial | GO/FIX |
| UI | 11 | Dashboard MVP | GO/FIX |
| Data Run | 12 | 10K–20K videos analizados (Gate 1 GO, Gate 1A GO, Gate 2A GO) | GO/FIX |
| Selección | 13 | Top 3 oportunidades | GO/FIX |
| Ejecución | 14 | Canal piloto + 10 contenidos | GO/FIX |
| Aprendizaje | 15 | Feedback Loop | GO/FIX |
| Escala | 16 | Segunda oportunidad | GO/FIX |
| Validación fuerte | 17 | Segundo caso económico | GO/FIX |

---

# 2. GANTT VISUAL

```text
SPRINT / BLOQUE                               01 02 03 04 05 06 07 08 09 10 11 12 13 14 15 16 17
------------------------------------------------------------------------------------------------
S0  Setup                                   ██
S1  YouTube API                                ██
S2  PostgreSQL                                    ██
S3  Historical Metrics                              ██
S4  Outlier Engine                                    ██
S5  Niche Miner                                          ██
S6  Revenue + Geography                                    ██
S7  Competition + Depth + Evergreen                           ██
S8  Production + Risk                                           ██
S9  Profitability Engine                                           ██
S10 Validator                                                        ██
S11 Dashboard MVP                                                       ██
S12 10K–20K Data Run                                                      ██
S13 Top 100 → Top 3                                                          ██
S14 Canal piloto                                                                 ███
S15 Feedback Loop                                                                   ██
S16 Segunda oportunidad                                                               ███
S17 Validación económica fuerte                                                          ███
```

---

# 3. SPRINT 0 — SETUP

## Objetivo
Dejar TRAE y el entorno preparados para desarrollar sin deuda estructural.

## Tareas

- [ ] Crear `C:\Users\JLLV\Desktop\PRYTB`
- [ ] Abrir carpeta como workspace en TRAE
- [ ] Instalar/verificar Python 3.12+
- [ ] Crear `.venv`
- [ ] Crear estructura de carpetas
- [ ] Inicializar Git
- [ ] Crear `.gitignore`
- [ ] Crear `.env`
- [ ] Crear `.env.example`
- [ ] Crear `requirements.txt`
- [ ] Configurar logging
- [ ] Crear README inicial
- [ ] Copiar Master Prompt y Gantt a raíz/docs

## Criterio de aceptación

```text
python --version OK
venv OK
Git OK
estructura OK
secrets fuera del repo
app inicia sin error
```

## Gate
`GO` sólo si no existen errores de configuración críticos.

---

# 4. SPRINT 1 — YOUTUBE DATA API

## Objetivo
Conectar con YouTube Data API v3 y traer datos reales.

## Dependencias humanas

- [ ] Crear cuenta Google dedicada
- [ ] Crear proyecto Google Cloud
- [ ] Activar YouTube Data API v3
- [ ] Crear API Key
- [ ] Guardar `YOUTUBE_API_KEY` en `.env`

## Desarrollo

- [ ] Cliente YouTube API
- [ ] Search videos
- [ ] Get video details
- [ ] Get channel details
- [ ] Manejo cuota
- [ ] Retry controlado
- [ ] Logging
- [ ] Test con keyword `artificial intelligence`

## Criterio de aceptación
Traer al menos 50 videos reales y sus canales asociados sin errores críticos.

---

# 5. SPRINT 2 — POSTGRESQL

## Objetivo
Persistir datos reales.

## Tareas

- [ ] Crear base local `prytb`
- [ ] Configurar `localhost:5433` y usuario `prytb_app`
- [ ] Crear esquema inicial
- [ ] Crear tablas `channels`
- [ ] Crear tablas `videos`
- [ ] Crear tablas `video_metrics`
- [ ] Crear tablas `channel_metrics`
- [ ] Implementar upsert
- [ ] Evitar duplicados
- [ ] Crear índices básicos

## Criterio de aceptación
Los 50+ videos del Sprint 1 quedan almacenados y consultables.

---

# 6. SPRINT 3 — HISTORICAL METRICS

## Objetivo
Medir evolución temporal.

## Tareas

- [ ] Snapshot de métricas
- [ ] `checked_at`
- [ ] Views per day
- [ ] View velocity
- [ ] View acceleration
- [ ] Scheduler manual/local inicial

## Criterio de aceptación
Dos snapshots del mismo video producen diferencias calculables.

---

# 7. SPRINT 4 — OUTLIER ENGINE

## Objetivo
Detectar videos anormalmente exitosos respecto de su canal.

## Tareas

- [ ] Mediana de views por canal
- [ ] Outlier Ratio
- [ ] Normalización por edad
- [ ] Small Channel Outlier
- [ ] Ranking Top 20
- [ ] Tests matemáticos

## Criterio de aceptación
El sistema identifica correctamente ejemplos 5X, 10X, 25X+.

---

# 8. SPRINT 5 — NICHE MINER

## Objetivo
Convertir títulos/videos en clusters temáticos útiles.

## Tareas

- [ ] Integrar OmniRoute
- [ ] Crear `LLMProvider`
- [ ] Configurar modelo rápido
- [ ] Configurar reasoning
- [ ] Configurar embeddings si OmniRoute lo soporta
- [ ] Embeddings de títulos
- [ ] Clustering
- [ ] Etiquetado semántico
- [ ] Jerarquía nicho/subnicho/micronicho

## Criterio de aceptación
Los clusters deben ser coherentes y accionables, no categorías genéricas.

---

# 9. SPRINT 6 — REVENUE + GEOGRAPHY

## Objetivo
Distinguir audiencia viral de audiencia económicamente valiosa.

## Tareas

- [ ] Revenue Score
- [ ] RPM Low/Base/High
- [ ] Market Value Score
- [ ] Geography Score
- [ ] English vs Spanish
- [ ] USA/Canada/UK/Australia/Spain/LATAM
- [ ] Confidence

## Criterio de aceptación
El sistema no entrega un RPM exacto como hecho sin evidencia.

---

# 10. SPRINT 7 — COMPETITION + DEPTH + EVERGREEN

## Objetivo
Medir si realmente podemos entrar y sostener contenido.

## Tareas

- [ ] Competition Score
- [ ] Small Channel Success Rate
- [ ] Content Depth
- [ ] Estimación 20/50/100+ ideas
- [ ] Evergreen classification

## Criterio de aceptación
Diferenciar correctamente:

```text
viral pero saturado
rentable pero sin contenido suficiente
oportunidad sostenible
```

---

# 11. SPRINT 8 — PRODUCTION + RISK

## Objetivo
Evitar oportunidades económicamente atractivas pero impracticables.

## Tareas

- [ ] Production Cost Score
- [ ] Tiempo estimado
- [ ] Research complexity
- [ ] Footage complexity
- [ ] Copyright Risk
- [ ] Reused Content Risk
- [ ] Regulatory/Sensitive Risk

## Criterio de aceptación
Generar costo y riesgo razonables con evidencia y confidence.

---

# 12. SPRINT 9 — PROFITABILITY ENGINE

## Objetivo
Crear ranking económico final.

## Tareas

- [ ] Expected views range
- [ ] RPM range
- [ ] Revenue pessimistic/base/optimistic
- [ ] Production cost
- [ ] Expected profit
- [ ] Profitability Score
- [ ] Configurable weights

## Criterio de aceptación
El ranking puede favorecer un nicho con menos views pero mayor beneficio esperado.

---

# 13. SPRINT 10 — VALIDATOR

## Objetivo
Intentar invalidar cada oportunidad fuerte.

## Tareas

- [ ] Counter-evidence
- [ ] Saturation test
- [ ] Trend decay test
- [ ] Copyright challenge
- [ ] Cost challenge
- [ ] Outlier concentration test
- [ ] Confidence adjustment

## Criterio de aceptación
El Validator debe ser capaz de bajar scores cuando encuentra evidencia contraria.

---

# 14. SPRINT 11 — DASHBOARD MVP

## Objetivo
Visualizar el sistema sin consultar la BD manualmente.

## Pantallas

- [ ] Overview
- [ ] Opportunities
- [ ] Opportunity Detail
- [ ] Outliers
- [ ] Channels
- [ ] Costs

## Criterio de aceptación
Desde Streamlit se puede llegar desde overview hasta evidencia de una oportunidad.

---

# 15. SPRINT 12 — PRIMERA CORRIDA SERIA

## Objetivo
Obtener dataset suficiente para juzgar el motor.

## Meta

```text
10.000–20.000 videos
500–1.000 canales
English + Spanish
```

## Salidas

- [ ] Top 100 Outliers
- [ ] Top 30 clusters
- [ ] Top 20 subnichos
- [ ] Top 10 oportunidades
- [ ] costos de ejecución

## Gate crítico
Si sólo devuelve nichos obvios, `FIX`.

---

# 16. SPRINT 13 — TOP 100 → TOP 3

## Objetivo
Selección humana asistida.

## Tareas

- [ ] Revisar Top 20
- [ ] Reducir a Top 10
- [ ] Reducir a Top 5
- [ ] Revisar evidencia manualmente
- [ ] Seleccionar Top 3

## Criterio de aceptación
Cada finalista tiene:

```text
Profitability >80 ideal
Viral >60
Revenue >70
Risk controlado
100+ ideas potenciales
entrada plausible
```

---

# 17. SPRINT 14 — CANAL PILOTO

## Objetivo
Ejecutar una oportunidad real.

## Tareas

- [ ] Elegir subnicho ganador
- [ ] Elegir mercado
- [ ] Elegir idioma
- [ ] Elegir nombre de canal
- [ ] Crear canal
- [ ] Branding mínimo
- [ ] Crear 30 ideas
- [ ] Seleccionar 10 contenidos
- [ ] Definir mezcla Shorts/long-form
- [ ] Publicar

## Estrategia inicial sugerida

```text
Shorts = testing + audiencia + ingreso adicional
Long-form = monetización principal
```

## Gate
No escalar producción si no aparecen señales orgánicas.

---

# 18. SPRINT 15 — FEEDBACK LOOP

## Objetivo
Cruzar predicción del agente con resultados propios.

## Guardar

- [ ] predicted views
- [ ] predicted RPM
- [ ] predicted revenue
- [ ] actual views
- [ ] actual RPM
- [ ] actual revenue
- [ ] cost
- [ ] profit
- [ ] CTR
- [ ] retention

## Criterio de aceptación
Calcular error de predicción y comenzar `ExecutionFit`.

---

# 19. SPRINT 16 — SEGUNDA OPORTUNIDAD

## Objetivo
Demostrar que el motor puede volver a encontrar una oportunidad.

## Gate
No vender el agente todavía.

---

# 20. SPRINT 17 — VALIDACIÓN ECONÓMICA FUERTE

## Objetivo
Determinar si existe repetibilidad.

## Validación fuerte

```text
Opportunity Hunter
↓
Canal 1 rentable
↓
Canal 2 con evidencia económica
↓
proceso repetible
```

Sólo entonces abrir documento de comercialización futura.

---

# 21. RIESGOS Y MITIGACIONES

| Riesgo | Mitigación |
|---|---|
| Cuota YouTube API | cache, batches, control quota |
| Capacidad PostgreSQL local limitada | esquema compacto, ampliar recursos sólo con necesidad real |
| Costos IA | OmniRoute abstraction + tracking |
| Clustering mediocre | iterar embeddings/features |
| Nichos triviales | Validator + data thresholds |
| Falsos RPM | rangos + confidence |
| Overengineering | sprint gates |
| Código roto por IA | tests + commits + no saltar sprints |
| Copyright | Risk Agent |
| Contenido sin tracción | pivot gate |

---

# 22. KPIs DEL PROYECTO

## Técnicos

```text
API success rate
DB error rate
LLM error rate
cost/run
processing time
```

## Analíticos

```text
outliers detected
cluster coherence
number of strong opportunities
confidence
```

## Económicos futuros

```text
cost/video
revenue/video
profit/video
RPM
channel revenue
channel profit
ROI
payback
```

---

# 23. DEFINICIÓN DE TERMINADO

PRYTB V1 se considera terminado cuando:

1. analiza datos reales;
2. detecta outliers;
3. descubre subnichos;
4. estima rentabilidad;
5. genera Top Opportunities;
6. entrega evidencia y counter-evidence;
7. permite seleccionar Top 3;
8. almacena todo reproduciblemente.

El producto económico se considera validado únicamente con ingresos reales.

---

# 24. SIGUIENTE ACCIÓN

La siguiente acción operativa es exclusivamente:

```text
SPRINT 0
↓
abrir C:\Users\JLLV\Desktop\PRYTB en TRAE
↓
crear estructura
↓
crear cuenta Google dedicada
↓
crear Google Cloud Project
↓
activar YouTube Data API v3
↓
configurar PostgreSQL local
↓
configurar OmniRoute
```

No desarrollar Niche Miner ni dashboard antes de validar Collector + DB.
