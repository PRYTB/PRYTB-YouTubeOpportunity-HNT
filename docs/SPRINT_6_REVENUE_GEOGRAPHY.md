# Sprint 6 — Revenue + Geography Engine

## Status

Complete. Sprint 6 adds an in-memory revenue/geography analysis layer over the approved Sprint 5 production clusters. It does not create an Opportunity Score and does not begin Sprint 7.

## Evidence boundaries

Sprint 6 keeps four evidence classes distinct:

- **Observed:** YouTube metadata directly present in stored records, including channel-origin country, duration, and declared video language.
- **Inferred:** Content language and audience-market signals derived from title/description text.
- **Assumed:** Editable market-tier mappings and the internal comparative-value formula.
- **Unknown:** Missing or conflicting evidence remains unknown; it is not replaced with channel country or invented monetary values.

`channel_origin_country` is observed channel metadata. It is never presented as viewer geography. `estimated_audience_market` is inferred separately. `primary_country` is populated only when one explicit country signal is detected in title/description; conflicting signals leave it unknown. A language-derived market such as `English-language markets` is broad and does not make the country known.

## Language method

Language detection is deterministic and local:

1. `default_audio_language` metadata.
2. `default_language` metadata.
3. Title/description token and character heuristics for English, Spanish, Portuguese, French, and German.
4. `OTHER` or `UNKNOWN` when evidence is unsupported, ambiguous, or insufficient.

Metadata results receive higher confidence than text inference. No external language service is called.

## Content format

Classification uses only `duration_seconds`; title, URL, and hashtags are ignored.

- `SHORT`: positive duration at or below the configured cutoff.
- `LONG_FORM`: duration above the cutoff.
- `UNKNOWN`: missing, Boolean, malformed, zero, or negative duration.

The default cutoff is **180 seconds** and can be changed through the engine constructor.

## Market tiers

Tier lookup order is country, region, language, then unknown. Mappings are editable in `config/market_tiers.py` without modifying engine logic.

Tiers are internal assumptions about relative advertiser-market attractiveness. They are not RPM, CPM, creator revenue, purchasing-power guarantees, or universal monetization facts. Language fallback is deliberately lower-specificity evidence. In this production run, all detected languages were English, so the configured English-to-Tier-A fallback compressed every result into Tier A; this is a material limitation of the current comparative output.

## Revenue benchmarks

`RevenueBenchmarkProvider` is the only path by which monetary values can enter an analysis:

- `EmptyBenchmarkProvider` returns no benchmarks and is the production default.
- `ConfiguredBenchmarkProvider` accepts explicit benchmark records with source, market, content type, timestamp, and confidence. For duplicate keys it selects the highest-confidence record.

When no documented benchmark matches:

```text
revenue benchmark = unavailable
```

The low, midpoint, and high monetary fields remain `None`. Sprint 6 does not invent RPM, CPM, creator revenue, country revenue, or currency ranges.

## AudienceEconomicValue

`AudienceEconomicValue` is an internal comparative indicator normalized to 0–100. It is not actual revenue and is not an Opportunity Score.

Formula:

1. Tier base: Tier A = 80, Tier B = 60, Tier C = 40, Unknown = 25.
2. Format adjustment: long form +5, short -5, unknown -10.
3. Supported known language: +5.
4. Documented benchmark available: +10.
5. Clamp to 0–100 and round to increments of five.

The benchmark adjustment indicates stronger evidence availability, not guaranteed earnings.

## Confidence

Video confidence is:

```text
40% geography confidence
20% language confidence
20% known-format evidence
20% benchmark confidence
```

Missing benchmarks contribute zero to the benchmark component. Cluster confidence starts from member mean confidence, applies a sample-size factor, and reduces confidence when inferred audience countries are unknown.

## Cluster aggregation

Sprint 6 consumes the approved Sprint 5 assignments and aggregates:

- Language distribution and dominant language.
- Inferred audience-country distribution.
- Market-tier distribution.
- Long-form, short, and unknown-format counts.
- Benchmark coverage.
- Mean comparative economic value, rounded to five points.
- Confidence and warnings.

When more than half of a cluster has unknown audience country, detailed country distribution is suppressed to avoid misleading precision.

## Data-quality metrics

All rates use the analyzed production-video count as denominator:

- `language_unknown_rate`: primary content language is unknown.
- `geo_unknown_rate`: inferred audience country is unavailable. A broad language market does not count as a known country.
- `content_type_unknown_rate`: duration cannot support classification.
- `benchmark_missing_rate`: no documented monetary benchmark is available.

High unknown rates are reported rather than imputed.

## Approved production contract

The CLI reuses the approved Sprint 5 deterministic production pipeline:

- Production videos: **83**.
- Clusters: **10**.
- Dataset hash: `4d81c80e8da54b371c7eb969957ea347fc632d82abd737719141c866f4bfe9ad`.
- Assignment hash: `6c0e7bb6aeec75985664becb05f7c61cbfec874c15a6ec7395d60c2996436288`.
- Silhouette: `0.2468982051367785`.

Run:

```powershell
$env:PYTHONIOENCODING='utf-8'
.\.venv\Scripts\python.exe scripts\analyze_revenue_geography.py --json
```

## Production results

| Metric | Result |
|---|---:|
| Videos | 83 |
| Clusters | 10 |
| Languages detected | 83 |
| `language_unknown_rate` | 0.0% |
| Observed channel-country signals | 67 |
| Inferred audience-market signals | 83 |
| Unknown inferred audience countries | 49 |
| `geo_unknown_rate` | 59.0% |
| Long form | 74 |
| Shorts | 9 |
| Unknown format | 0 |
| `content_type_unknown_rate` | 0.0% |
| Benchmark coverage | 0.0% |
| `benchmark_missing_rate` | 100.0% |
| Fabricated monetary values | 0 |
| Economic-value range | 80–90 |
| Economic-value median | 90 |
| Median confidence | 63.3 |

Revenue benchmark: **unavailable**.

## Ten-video validation

Ten real production records were reviewed through the deterministic validation section. Each check verifies channel-origin/audience separation, absence of monetary values without a benchmark, and duration-warning behavior when applicable.

| Video ID | Channel origin | Estimated audience market | Format | Benchmark | Status |
|---|---|---|---|---|---|
| `-9bo8HlSxwQ` | US | English-language markets | LONG_FORM | unavailable | PASS |
| `-sB12gk9ESA` | US | US | LONG_FORM | unavailable | PASS |
| `0Tch0N5nsRU` | CA | English-language markets | LONG_FORM | unavailable | PASS |
| `1Qm_RgejEHg` | IN | US | LONG_FORM | unavailable | PASS |
| `1X-rr1DKSbY` | GB | English-language markets | LONG_FORM | unavailable | PASS |
| `1bEZblgDG5M` | US | English-language markets | LONG_FORM | unavailable | PASS |
| `4gr5m1xz0Ds` | AU | US | LONG_FORM | unavailable | PASS |
| `5KmopXwjXik` | UNKNOWN | US | LONG_FORM | unavailable | PASS |
| `5MWT_doo68k` | US | English-language markets | LONG_FORM | unavailable | PASS |
| `5NgNicANyqM` | US | English-language markets | LONG_FORM | unavailable | PASS |

Country signals inferred from title/description are heuristic and should not be treated as observed audience measurements.

## Top-five comparative candidates

| Cluster | Niche | Videos | Language | Tier distribution | Long | Shorts | Value | Confidence | Warnings |
|---:|---|---:|---|---|---:|---:|---:|---:|---|
| 3 | Artificial Intelligence | 17 | en | Tier A: 17 | 16 | 1 | 90 | 46.6 | Country distribution suppressed; no benchmarks; generic subniche fallback |
| 6 | Artificial Intelligence | 5 | en | Tier A: 5 | 5 | 0 | 90 | 46.2 | No benchmarks; weak title support for label |
| 8 | Artificial Intelligence | 8 | en | Tier A: 8 | 7 | 1 | 90 | 44.9 | No benchmarks |
| 1 | Artificial Intelligence | 20 | en | Tier A: 20 | 16 | 4 | 90 | 44.3 | Country distribution suppressed; no benchmarks |
| 7 | Artificial Intelligence | 4 | en | Tier A: 4 | 4 | 0 | 90 | 41.8 | Small sample; no benchmarks; generic subniche fallback |

Ties are ordered by confidence and video count. These are comparative economic-value candidates, not revenue rankings.

## Persistence

Sprint 6 is intentionally in memory:

- Sprint 6 tables: none.
- Sprint 6 writes: 0.
- Read-back/count verification: not applicable.
- Backend migration: not required.

The integration test reads real InsForge production data and patches HTTP POST to assert that Sprint 6 performs no writes.

## Tests

Coverage includes language precedence and ambiguity, duration boundaries and invalid values, channel-origin/audience separation, explicit and conflicting geography signals, tier lookup, empty and configured benchmark providers, provenance, no fabricated monetary fields, confidence/value bounds, quality rates, cluster aggregation, small samples, high-unknown suppression, and the exact approved production hashes.
