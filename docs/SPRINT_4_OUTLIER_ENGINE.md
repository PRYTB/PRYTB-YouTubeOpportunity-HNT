# PRYTB — SPRINT 4: OUTLIER ENGINE

## 1. Description
The Outlier Engine detects YouTube videos that perform abnormally better than their channel's real baseline median performance. It provides statistical signal metrics to surface opportunity candidates, with special emphasis on small channels producing unusually high-performing videos.

## 2. Key Metrics & Definitions

### Channel Baseline
- **ChannelMedianViews**: The median view count across all known videos of the channel (excluding the target video being evaluated to avoid reference pollution).
- **ChannelMeanViews**: Arithmetic mean views across known channel videos.
- **ChannelMedianViewsPerDay**: Median views per day across known channel videos.
- **ChannelMedianLatestVelocity**: Median view velocity across known channel videos.

### Outlier Ratios
- **OutlierRatio**:
  $$\text{OutlierRatio} = \frac{\text{VideoViews}}{\text{ChannelMedianViews}}$$
  *Interpretations*: 1X = normal, 2X = superior, 5X = strong outlier, 10X = major outlier, 25X+ = extreme outlier.
  *Zero Division*: If `ChannelMedianViews` is 0, `OutlierRatio` is `None` and a warning is logged.

- **AgeNormalizedOutlierRatio**:
  $$\text{AgeNormalizedOutlierRatio} = \frac{\text{VideoLifetimeViewsPerDay}}{\text{ChannelMedianLifetimeViewsPerDay}}$$
  Normalizes performance across videos of different ages.

- **VelocityRatio**:
  $$\text{VelocityRatio} = \frac{\text{VideoLatestVelocity}}{\text{ChannelMedianLatestVelocity}}$$

- **ViewsToSubscribersRatio**:
  $$\text{ViewsToSubscribersRatio} = \frac{\text{VideoViews}}{\text{SubscriberCount}}$$
  Calculated when subscriber count is available and $> 0$.

### Small Channel Outlier Signal
Identifies small channels producing large outlier videos:
- `is_small_channel`: `True` if `subscriber_count <= 50,000`, `False` if greater, `None` if hidden.
- `small_channel_outlier`: `True` if `is_small_channel` is `True` and `outlier_ratio >= 5.0`.

### Noise Controls
- **Acceleration**: Ignored for primary ranking signals if `snapshot_count < 3` or interval $< 1.0$ hour (`MIN_ACCELERATION_INTERVAL_HOURS`).

## 3. Confidence & Ranking Formula

### Statistical Confidence (0 - 100)
Pure statistical score based on data completeness:
- **Baseline Sample Size** (Up to 40 pts): 10+ vids = 40, 5-9 = 30, 3-4 = 20, 1-2 = 10.
- **Views Availability** (20 pts).
- **Video Age Stability** (Up to 15 pts): $\ge 24\text{h} = 15$, $\ge 1\text{h} = 10$, $< 1\text{h} = 5$.
- **Historical Snapshots** (Up to 15 pts): 3+ = 15, 2 = 10, 1 = 5.
- **Subscriber Visibility** (10 pts).

### OutlierRankScore
Explicit formula to rank anomalies:
$$\text{RankScore} = (0.35 \times 2 \times \min(\text{OutlierRatio}, 50)) + (0.30 \times 2 \times \min(\text{AgeNormRatio}, 50)) + (0.15 \times 15 \times \text{SmallChannel}) + (0.10 \times 0.5 \times \min(\text{VelocityRatio}, 20)) + (0.10 \times \text{Confidence})$$

## 4. Configuration
Defined centrally in `config/outlier_config.py`:
- `OUTLIER_STRONG_MIN = 5.0`
- `OUTLIER_MAJOR_MIN = 10.0`
- `OUTLIER_EXTREME_MIN = 25.0`
- `SMALL_CHANNEL_SUBSCRIBERS_MAX = 50000`
- `MIN_ACCELERATION_INTERVAL_HOURS = 1.0`
- `MIN_ACCELERATION_SNAPSHOT_COUNT = 3`

## 5. Usage
```powershell
python scripts/rank_outliers.py --limit 20
```
