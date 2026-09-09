# PRYTB — MASTER PROMPT
## YouTube Opportunity Hunter — Private Engine

**Versión:** 1.0  
**Ruta raíz obligatoria:** `I:\PRYTB`
**IDE / agente de desarrollo:** TRAE
**Backend de datos principal:** PostgreSQL local (`localhost:5433`, DB `prytb`, User `prytb_app`)
**Backend de datos histórico:** InsForge (fuente de migración legacy únicamente)
**Supabase:** No usado
**Fuente principal de datos:** YouTube Data API v3  
**Proveedor de modelos IA:** OmniRoute  
**Lenguaje principal:** Python 3.12+  
**Dashboard MVP:** Streamlit  
**Repositorio:** Git  

---

# 1. MISIÓN DEL PROYECTO

Construir un sistema privado denominado **YouTube Opportunity Hunter** capaz de detectar oportunidades rentables dentro de YouTube mediante datos reales, análisis estadístico, clustering semántico y modelos IA.

El sistema NO debe limitarse a identificar contenido viral. Debe localizar la intersección entre:

- demanda;
- viralidad;
- potencial de monetización;
- RPM probable;
- facilidad de entrada;
- profundidad temática;
- contenido evergreen;
- costo de producción;
- riesgo de copyright / reused content;
- capacidad de producir Shorts y long-form;
- beneficio esperado.

La finalidad inicial es **uso privado**. El sistema se usará primero para crear, validar y monetizar canales propios. La comercialización del agente queda expresamente fuera de alcance hasta demostrar resultados económicos repetibles.

---

# 2. PRINCIPIO RECTOR

No optimizar por vistas.

Optimizar por:

```text
BENEFICIO ESPERADO
=
DEMANDA
×
POTENCIAL VIRAL
×
VALOR ECONÓMICO DE LA AUDIENCIA
×
EVERGREEN
×
PROBABILIDAD REALISTA DE ENTRADA
÷
COSTO DE PRODUCCIÓN
```

Toda nueva función debe responder:

> ¿Mejora esta función nuestra capacidad de encontrar, validar o explotar una oportunidad rentable en YouTube?

Si la respuesta es no, no se implementa todavía.

---

# 3. REGLAS ESTRICTAS PARA TRAE

1. Trabajar exclusivamente dentro de:
   `C:\Users\JLLV\Desktop\PRYTB`
2. No modificar archivos fuera de esa ruta.
3. No crear tecnologías adicionales sin justificación.
4. No cambiar el stack definido sin autorización explícita.
5. No saltar sprints.
6. No avanzar si el sprint actual tiene errores críticos.
7. Todo cambio funcional debe incluir prueba.
8. Toda integración externa debe tener manejo de errores, timeout y retry controlado.
9. Toda API key debe vivir en `.env`.
10. `.env` nunca debe subir a Git.
11. Nunca hardcodear secretos.
12. Implementar logging desde el inicio.
13. Toda tabla debe tener una finalidad documentada.
14. Toda métrica debe tener definición matemática/documental.
15. No inventar datos ausentes.
16. Toda estimación generada por IA debe incluir nivel de confianza.
17. Separar claramente datos observados de inferencias.
18. Mantener compatibilidad Windows.
19. Cada sprint termina con:
   - tests;
   - validación manual;
   - documentación;
   - commit sugerido.
20. No reescribir componentes estables sin necesidad.
21. Antes de tocar código existente, inspeccionar dependencias y tests.
22. Evitar scripts monolíticos.
23. Mantener arquitectura modular.
24. Prohibido generar archivos tipo `final_v2_fixed_final.py`.
25. Usar nombres claros, consistentes y profesionales.

---

# 4. DEFINICIÓN DE ÉXITO

El proyecto NO está validado porque el software funcione.

Debe pasar estos niveles:

## Nivel 1 — Técnico
El sistema obtiene y persiste datos reales de YouTube.

## Nivel 2 — Analítico
Detecta outliers y subnichos coherentes.

## Nivel 3 — Descubrimiento
Encuentra oportunidades que no sean triviales ni listas genéricas.

## Nivel 4 — Validación de canal
Una oportunidad encontrada por el agente genera tráfico orgánico real al ser ejecutada.

## Nivel 5 — Monetización
El canal genera ingresos reales.

## Nivel 6 — Rentabilidad
Ingresos > costos.

## Nivel 7 — Repetibilidad
El proceso vuelve a funcionar con una segunda oportunidad.

Sólo desde Nivel 7 puede evaluarse comercializar el sistema.

---

# 5. ESTRUCTURA DE CARPETAS OBLIGATORIA

```text
C:\Users\JLLV\Desktop\PRYTB
│
├── app\
│   ├── collectors\
│   ├── agents\
│   ├── analytics\
│   ├── scoring\
│   ├── services\
│   ├── database\
│   ├── models\
│   ├── utils\
│   └── orchestrator\
│
├── dashboard\
├── tests\
├── data\
│   ├── raw\
│   ├── processed\
│   └── exports\
├── docs\
├── logs\
├── config\
├── scripts\
├── .env
├── .env.example
├── .gitignore
├── requirements.txt
├── README.md
├── PRYTB_MASTER_PROMPT.md
└── PRYTB_GANTT.md
```

---

# 6. VARIABLES DE ENTORNO

Crear `.env.example` con al menos:

```env
YOUTUBE_API_KEY=
INSFORGE_URL=
INSFORGE_API_KEY=
OMNIROUTE_API_KEY=
OMNIROUTE_BASE_URL=
OMNIROUTE_MODEL_FAST=
OMNIROUTE_MODEL_REASONING=
OMNIROUTE_MODEL_EMBEDDING=
APP_ENV=development
LOG_LEVEL=INFO
```

Los nombres exactos para OmniRoute pueden ajustarse cuando se consulte su documentación real. No asumir endpoints ni modelos sin verificarlos.

---

# 7. COMPONENTES PRINCIPALES

## 7.1 YouTube Collector
Responsable de:

- búsqueda de videos;
- obtención de canales;
- estadísticas públicas;
- fechas;
- duración;
- títulos;
- descripciones;
- likes/comentarios cuando estén disponibles;
- persistencia en InsForge.

Debe respetar cuotas y registrar consumo aproximado.

## 7.2 Historical Metrics Collector
Guardar snapshots históricos sin sobrescribir datos anteriores.

Ejemplo:

```text
video_id | checked_at | views | likes | comments
```

## 7.3 Scout Agent
Descubre:

- canales;
- videos;
- keywords relacionadas;
- nuevos subnichos candidatos.

No decide rentabilidad.

## 7.4 Outlier Engine
Métricas iniciales:

```text
ChannelMedianViews
OutlierRatio = VideoViews / ChannelMedianViews
ViewsPerDay
ViewVelocity
ViewAcceleration
```

Debe priorizar:

```text
small channel + unusually large video
```

## 7.5 Niche Miner
Agrupa títulos y temas mediante embeddings/clustering.

Objetivo:

```text
Nicho
→ Subnicho
→ Micronicho
```

La IA puede etiquetar clusters, pero no inventar clusters sin soporte estadístico.

## 7.6 Viral Engine
Evaluar:

- outlier density;
- velocidad;
- aceleración;
- frescura;
- frecuencia de pequeños canales exitosos;
- replicabilidad temática.

Salida:

```text
ViralScore 0-100
Confidence 0-100
```

## 7.7 Revenue Engine
Evaluar:

- valor publicitario probable;
- intención comercial;
- audiencia objetivo;
- mercado geográfico;
- anunciantes potenciales;
- afiliación posible;
- sponsors;
- servicios/productos relacionados.

Nunca inventar RPM exactos.

Usar:

```text
RPM_LOW
RPM_BASE
RPM_HIGH
Confidence
```

## 7.8 Geography Engine
Comparar al menos:

- English / USA;
- English / Canada;
- English / UK;
- English / Australia;
- Spanish / Spain;
- Spanish / LATAM.

## 7.9 Competition Analyst
Medir:

- número de canales;
- concentración;
- tamaño promedio;
- edad de canales;
- nuevos entrantes;
- Small Channel Success Rate.

## 7.10 Content Depth Agent
Estimar cuántos videos razonablemente distintos puede soportar el subnicho.

Objetivo ideal:

```text
100+ ideas útiles
```

## 7.11 Evergreen Analyst
Clasificar:

```text
TREND
SEMI_EVERGREEN
EVERGREEN
```

## 7.12 Production Analyst
Estimar:

- research;
- guion;
- voz;
- visuales;
- edición;
- thumbnail;
- duración;
- costo por video;
- horas humanas.

## 7.13 Risk Analyst
Evaluar:

- copyright;
- reused content;
- dependencia de footage protegido;
- música;
- regulaciones;
- contenido sensible;
- riesgo de desmonetización.

## 7.14 Shorts Engine
No tratar Shorts como fuente principal de ingresos.

Funciones:

- detectar temas virales;
- testear demanda;
- generar audiencia;
- identificar temas que conviene expandir a long-form;
- estimar ingreso adicional por volumen.

## 7.15 Long-Form Engine
Prioridad económica principal.

Medir:

- views esperadas;
- RPM probable;
- duración;
- evergreen;
- profundidad;
- costo;
- beneficio esperado.

## 7.16 Profitability Engine
Calcular:

```text
ExpectedRevenue = ExpectedViews × EstimatedRPM / 1000
ExpectedProfit = ExpectedRevenue - EstimatedProductionCost
```

Debe manejar escenarios:

```text
Pessimistic
Base
Optimistic
```

## 7.17 Validator Agent
Función adversarial.

Debe intentar destruir la oportunidad buscando:

- saturación;
- falsos outliers;
- dependencia de un único canal;
- modas pasajeras;
- costos ocultos;
- copyright;
- baja profundidad;
- bajo valor comercial.

## 7.18 Opportunity Orchestrator
Consolidar todos los scores.

Salida mínima:

```text
Niche
Subniche
Market
Language
ViralScore
RevenueScore
CompetitionScore
EvergreenScore
ProductionScore
RiskScore
ShortScore
LongFormScore
ProfitabilityScore
ConfidenceScore
ExpectedViewsRange
RPMRange
ExpectedRevenueRange
ExpectedCostRange
ExpectedProfitRange
EvidenceSummary
CounterEvidence
Recommendation
```

---

# 8. PROFITABILITY SCORE — VERSIÓN INICIAL

Pesos iniciales:

```text
Demand              15%
Outliers            15%
Revenue Potential   20%
Competition         10%
Geography           10%
Evergreen           10%
Production          10%
Content Depth        5%
Short Potential      5%
```

Luego aplicar penalización por RiskScore.

Los pesos son configurables y deben almacenarse fuera del código duro.

---

# 9. CLASIFICACIÓN DE OPORTUNIDADES

```text
0-49   DESCARTAR
50-69  OBSERVAR
70-79  INTERESANTE
80-89  FUERTE
90-100 EXCEPCIONAL
```

No seleccionar automáticamente una oportunidad sólo por score.

Top 3 siempre requiere revisión humana.

---

# 10. DASHBOARD MVP

Streamlit debe mostrar:

## Overview
- videos analizados;
- canales analizados;
- subnichos;
- outliers;
- oportunidades fuertes;
- consumo de API;
- costo IA estimado.

## Opportunities
Tabla ordenable por:

- Profitability Score;
- Revenue Score;
- Viral Score;
- Long-form Score;
- Risk;
- Confidence.

## Opportunity Detail
Mostrar evidencia completa.

## Outliers
Videos fuera de baseline.

## Channels
Canales emergentes.

## Costs
Costos API/IA/producción.

---

# 11. CONTROL DE COSTOS

Registrar:

```text
provider
model
input_tokens
output_tokens
estimated_cost
operation
agent
created_at
```

Crear alertas cuando el gasto estimado supere presupuesto configurado.

Presupuesto inicial recomendado del motor:

```text
máximo operativo mensual inicial: 30.000 CLP aprox.
```

No bloquear desarrollo por este valor; usarlo como alerta.

---

# 12. USO DE OMNIROUTE

OmniRoute será la capa de acceso a modelos IA.

Crear abstracción:

```text
LLMProvider
```

Funciones mínimas:

```text
generate_fast()
generate_reasoning()
embed()
```

Nunca acoplar agentes directamente a un modelo específico.

Permitir cambiar modelo por configuración.

Registrar:

- modelo;
- latencia;
- tokens;
- errores;
- costo estimado.

Implementar fallback sólo si está explícitamente configurado.

---

# 13. BASE DE DATOS — INSFORGE

InsForge será la fuente de verdad principal.

Tablas mínimas iniciales:

```text
channels
videos
channel_metrics
video_metrics
search_terms
outliers
clusters
subniches
opportunities
agent_runs
llm_usage
costs
```

Futuras:

```text
our_channels
our_videos
experiments
revenues
production_costs
predictions
prediction_results
```

---

# 14. SPRINT GATES

Cada sprint debe terminar con:

## Gate técnico
- sin errores críticos;
- tests pasan;
- datos coherentes.

## Gate funcional
- función cumple objetivo.

## Gate documental
- README / docs actualizados.

## Gate económico
- costo registrado.

## Gate de decisión

```text
GO
FIX
STOP
```

No usar "más adelante" para dejar defectos críticos abiertos.

---

# 15. CRITERIOS DE CALIDAD

Código:

- modular;
- tipado cuando aporte claridad;
- funciones pequeñas;
- manejo de errores;
- docstrings útiles;
- logging estructurado;
- sin secretos;
- sin duplicación innecesaria.

Datos:

- IDs originales preservados;
- timestamps UTC;
- snapshots históricos;
- evitar duplicados;
- constraints e índices donde corresponda.

IA:

- prompts versionados;
- outputs estructurados;
- schema validation;
- confidence;
- evidencia;
- evitar respuestas libres cuando se pueda usar JSON estructurado internamente.

---

# 16. TESTING

Mínimo:

```text
unit tests
integration tests
API mocks
DB tests
scoring tests
```

Casos límite:

- canal sin subscriber count;
- video sin likes;
- video reciente de horas;
- canales con muy pocos videos;
- division por cero;
- API quota exceeded;
- timeout;
- modelo IA no disponible;
- respuesta IA inválida.

---

# 17. LOGGING

Guardar en `logs\`.

Niveles:

```text
DEBUG
INFO
WARNING
ERROR
CRITICAL
```

Cada ejecución de agente debe tener:

```text
run_id
agent_name
started_at
finished_at
status
items_processed
errors
cost
```

---

# 18. GIT

Commits sugeridos por sprint:

```text
feat: initialize PRYTB project structure
feat: add YouTube API collector
feat: persist YouTube data to InsForge
feat: add outlier detection engine
feat: add niche clustering
feat: add profitability scoring
feat: add Streamlit opportunity dashboard
```

Nunca incluir `.env`.

---

# 19. ROADMAP OPERATIVO

## Sprint 0 — Setup
Crear estructura, entorno, Git, configuración y conectividad.

## Sprint 1 — YouTube API
Traer datos reales.

## Sprint 2 — InsForge
Persistir y consultar.

## Sprint 3 — Historical Metrics
Snapshots y velocity.

## Sprint 4 — Outlier Engine
Encontrar anomalías.

## Sprint 5 — Niche Miner
Clusters y subnichos.

## Sprint 6 — Revenue / Geography
Potencial económico.

## Sprint 7 — Competition / Depth / Evergreen
Calidad estructural de la oportunidad.

## Sprint 8 — Production / Risk
Costo y viabilidad.

## Sprint 9 — Profitability Engine
Score final.

## Sprint 10 — Validator
Contraprueba.

## Sprint 11 — Dashboard MVP
Top oportunidades.

## Sprint 12 — Primera corrida seria
10.000–20.000 videos.

## Sprint 13 — Top 100 → Top 3
Selección humana.

## Sprint 14 — Canal piloto
Crear canal y contenido inicial.

## Sprint 15 — Feedback Loop
Cruzar predicción vs resultado real.

---

# 20. PRIMERA META REAL

El primer hito útil es:

```text
keyword
↓
YouTube API
↓
50+ videos
↓
canales
↓
InsForge
↓
outlier ratios
↓
Top 20 outliers
```

No avanzar a IA sofisticada hasta que esto funcione correctamente.

---

# 21. SEGUNDA META REAL

Con 10.000–20.000 videos:

```text
Top 100 Outliers
↓
Top 30 Clusters
↓
Top 20 Subnichos
↓
Top 5 Opportunities
↓
Top 3 Human Review
```

---

# 22. FASE DE CANAL

Sólo después de obtener Top 3:

1. seleccionar mercado;
2. seleccionar idioma;
3. definir subnicho;
4. crear nombre;
5. crear cuenta/canal;
6. branding mínimo;
7. crear 30 ideas;
8. seleccionar primeros 10 contenidos;
9. mezclar Shorts y long-form;
10. medir.

---

# 23. ESTRATEGIA SHORTS + LONG-FORM

## Shorts
Función:

- testing;
- alcance;
- suscriptores;
- ingreso adicional;
- identificación rápida de temas ganadores.

## Long-form
Función:

- monetización principal;
- biblioteca evergreen;
- mayor RPM;
- beneficio recurrente.

Flujo:

```text
SHORT TEST
↓
TEMA GANADOR
↓
LONG-FORM
↓
MONETIZACIÓN
↓
SHORTS DERIVADOS
↓
NUEVA AUDIENCIA
```

---

# 24. FEEDBACK LOOP

Registrar para contenido propio:

```text
predicted_score
predicted_views
predicted_revenue
actual_views
actual_rpm
actual_revenue
actual_cost
actual_profit
```

Calcular error de predicción.

El objetivo futuro es añadir:

```text
ExecutionFit
```

para personalizar oportunidades según nuestra capacidad real de ejecución.

---

# 25. CRITERIO DE MUERTE

El proyecto debe permitir detener hipótesis malas.

Ejemplos:

- clusters inútiles tras iteraciones razonables;
- API/infraestructura demasiado costosa;
- scores sin correlación con resultados;
- oportunidades triviales;
- incapacidad de superar investigación manual.

No mantener componentes sólo porque ya fueron desarrollados.

---

# 26. COMERCIALIZACIÓN — FUERA DE ALCANCE ACTUAL

No construir todavía:

- login multiusuario;
- Stripe;
- planes;
- SaaS;
- onboarding;
- API pública;
- billing;
- portal cliente.

Sólo reconsiderar cuando:

```text
Canal 1 rentable
+
Canal 2 validado
+
proceso repetible
```

---

# 27. INSTRUCCIÓN FINAL A TRAE

Trabaja como un equipo senior de:

- Product Manager;
- Data Engineer;
- Python Engineer;
- Data Scientist;
- ML/AI Engineer;
- DBA;
- QA Engineer;
- DevOps;
- FinOps.

Pero ejecuta **un sprint a la vez**.

Antes de cada sprint:

1. inspecciona estado actual;
2. define objetivo;
3. identifica archivos afectados;
4. implementa;
5. prueba;
6. corrige;
7. documenta;
8. entrega estado GO / FIX / STOP.

Nunca avances ocultando errores.

La prioridad actual es:

# HACER FUNCIONAR EL MOTOR DE DESCUBRIMIENTO RENTABLE.
