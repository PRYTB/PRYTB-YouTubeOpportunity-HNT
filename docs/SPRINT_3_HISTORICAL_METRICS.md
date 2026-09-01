# SPRINT 3 — HISTORICAL METRICS & VELOCITY

## Overview

Sprint 3 implements the historical layer for YouTube Opportunity Hunter (`PRYTB`). This layer allows calculating metrics evolution, view velocity, and view acceleration across temporal snapshots stored in InsForge PostgreSQL without mutating database schemas or saving unneeded derived columns.

---

## Metric Definitions & Formulas

### 1. ViewDelta ($\Delta V$)
Difference in view count between two consecutive snapshots ($S_{prev}$ and $S_{curr}$):
$$\text{ViewDelta} = \text{current\_view\_count} - \text{previous\_view\_count}$$
* **Rules**: If either value is `None`, $\text{ViewDelta} = \text{None}$. Negative deltas are preserved and logged as warnings (e.g., YouTube audit adjustments).

### 2. Elapsed Time ($\Delta t$)
Time difference calculated using UTC timestamps:
$$\text{elapsed\_seconds} = \text{timestamp}_{curr} - \text{timestamp}_{prev}$$
$$\text{elapsed\_hours} = \frac{\text{elapsed\_seconds}}{3600}$$
$$\text{elapsed\_days} = \frac{\text{elapsed\_seconds}}{86400}$$

### 3. ViewsPerDay
Daily view rate over an interval:
$$\text{ViewsPerDay} = \frac{\text{ViewDelta}}{\text{elapsed\_days}}$$
* **Rules**: Returns `None` if $\text{elapsed\_seconds} \le 0$ or $\text{ViewDelta}$ is `None`.

### 4. ViewVelocity ($V$)
Hourly view velocity:
$$\text{ViewVelocity} = \frac{\text{ViewDelta}}{\text{elapsed\_hours}} \quad (\text{unit: views/hour})$$

### 5. ViewAcceleration ($A$)
View acceleration across 2 consecutive intervals (requires 3+ snapshots):
$$A = \frac{V_2 - V_1}{\text{elapsed\_hours\_between\_interval\_midpoints}} \quad (\text{unit: views/hour}^2)$$
* **Rules**: Returns `None` if fewer than 3 snapshots exist or if velocities cannot be calculated.

### 6. Video Age & Lifetime Views Per Day
Video age in real fractional days from publication date to latest snapshot:
$$\text{video\_age\_days} = \frac{\text{latest\_snapshot\_timestamp} - \text{published\_at}}{86400}$$
$$\text{LifetimeViewsPerDay} = \frac{\text{latest\_view\_count}}{\text{video\_age\_days}} \quad (\text{if } \text{video\_age\_days} > 0)$$

---

## Edge Case & Anomaly Handling

1. **NULL values**: `NULL != 0`. Missing metrics remain `None`.
2. **Negative deltas**: Kept as-is, warning attached to model output.
3. **Duplicate timestamps**: Deduplicated deterministically by timestamp string without removing database records.
4. **Out of order timestamps**: Automatically sorted by `collected_at ASC`.

---

## Scripts & CLI Tools

- **Update Snapshots**: `python scripts/update_metrics_snapshot.py --limit 50`
  * Uses batching via `videos.list` and `channels.list` (no `search.list` quota waste).
- **Analyze Video History**: `python scripts/analyze_video_history.py --video-id <ID>`
