# SPRINT 13 — GATE 2C: EXTERNAL BENCHMARK ACQUISITION & CALIBRATION

## Executive Summary

- **Gate Status**: **GO**
- **Canonical Top20 Mapped**: 20 / 20 (100% complete)
- **RPM Benchmarks Loaded**: 4 documented categories (vidIQ 2026)
- **Cost Benchmarks Loaded**: 2 labor roles (Upwork rates - VE: $6-$25/hr, CC: $25-$55/hr)
- **Persistence Architecture**: The source registry JSON is the canonical artifact ledger; PostgreSQL persists benchmark and candidate-economics rows.
- **Dual Reread Canonical Hash 1**: `f742841d554b45d3c6677e8292a76f78ae49cdf282aa60046e65a4f5a55c0cc5`
- **Dual Reread Canonical Hash 2**: `f742841d554b45d3c6677e8292a76f78ae49cdf282aa60046e65a4f5a55c0cc5`
- **Hash Match Verified**: `YES`

## External Source Registry

1. **YouTube Analytics - Understand Revenue per 1,000 views (RPM)**
   - **Source ID**: `SRC-YT-DOCS-2026`
   - **URL**: [YouTube Analytics - Understand Revenue per 1,000 views (RPM)](https://support.google.com/youtube/answer/9314357)
   - **Publication Date**: not published on source page
   - **Methodology**: Official RPM semantic definition; no numeric niche range is taken from this source.

2. **RPM on YouTube: Decode Your Channel’s Revenue**
   - **Source ID**: `SRC-VIDIQ-RPM-2026`
   - **URL**: [RPM on YouTube: Decode Your Channel’s Revenue](https://vidiq.com/blog/post/youtube-rpm/)
   - **Publication Date**: 2026-03-13
   - **Methodology**: Use published low/high bounds; derive base strictly as (low + high) / 2.

3. **How Much Does Hiring a Video Editor Cost?**
   - **Source ID**: `SRC-UPWORK-RATES-2026-VE`
   - **URL**: [How Much Does Hiring a Video Editor Cost?](https://www.upwork.com/hire/video-editors/cost/)
   - **Publication Date**: not published on source page
   - **Methodology**: Use the page-level exact overall range; derive base strictly as (6 + 25) / 2.

4. **Content Creators on Upwork Cost $25–$55/hr.**
   - **Source ID**: `SRC-UPWORK-RATES-2026-CC`
   - **URL**: [Content Creators on Upwork Cost $25–$55/hr.](https://www.upwork.com/hire/content-creators/cost/)
   - **Publication Date**: not published on source page
   - **Methodology**: Use the page's exact headline range; derive base strictly as (25 + 55) / 2.

## Top20 Economic Calibration Results

| Rank | ID | Subniche | Benchmark Category | RPM (L/B/H) | Production Cost (L/B/H) | Revenue (L/B/H) | Profit (L/B/H) | Combined Confidence |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | def_015 | AI Development & Software Engineering Workflows | Technology / Software | $4.00 / $7.00 / $10.00 | $30 / $155 / $375 | $4.0 / $14.0 / $30.0 | $-371.0 / $-141.0 / $0.0 | 0.77 |
| 2 | def_046 | Effective Study Methods & AI App Development | Education / How-To | $2.00 / $4.00 / $6.00 | $30 / $155 / $375 | $4.0 / $16.0 / $36.0 | $-371.0 / $-139.0 / $6.0 | 0.68 |
| 3 | def_055 | Cybersecurity Education & Penetration Testing | Technology / Software | $4.00 / $7.00 / $10.00 | $30 / $155 / $375 | $12.0 / $42.0 / $90.0 | $-363.0 / $-113.0 / $60.0 | 0.77 |
| 4 | def_036 | AI Developer Tooling & Financial Investing Tutorials | Finance / Investing | $4.00 / $8.00 / $12.00 | $30 / $155 / $375 | $16.0 / $64.0 / $144.0 | $-359.0 / $-91.0 / $114.0 | 0.72 |
| 5 | def_024 | CI/CD Cloud Deployment & AI Agent Development | Technology / Software | $4.00 / $7.00 / $10.00 | $30 / $155 / $375 | $20.0 / $70.0 / $150.0 | $-355.0 / $-85.0 / $120.0 | 0.77 |
| 6 | def_057 | Software Development Lifecycle & B2B AI Automation | Digital Marketing / Business | $4.00 / $6.50 / $9.00 | $30 / $155 / $375 | $24.0 / $78.0 / $162.0 | $-351.0 / $-77.0 / $132.0 | 0.72 |
| 7 | def_045 | Software Architecture & SaaS Product Management | Technology / Software | $4.00 / $7.00 / $10.00 | $30 / $155 / $375 | $28.0 / $98.0 / $210.0 | $-347.0 / $-57.0 / $180.0 | 0.77 |
| 8 | def_030 | Azure DevOps & CI/CD Pipeline Automation | Technology / Software | $4.00 / $7.00 / $10.00 | $30 / $155 / $375 | $32.0 / $112.0 / $240.0 | $-343.0 / $-43.0 / $210.0 | 0.77 |
| 9 | def_004 | Beginner Tech & Cybersecurity 101 | Technology / Software | $4.00 / $7.00 / $10.00 | $30 / $155 / $375 | $36.0 / $126.0 / $270.0 | $-339.0 / $-29.0 / $240.0 | 0.72 |
| 10 | def_038 | Bootstrapped SaaS & Admin Dashboard UI | Digital Marketing / Business | $4.00 / $6.50 / $9.00 | $30 / $155 / $375 | $40.0 / $130.0 / $270.0 | $-335.0 / $-25.0 / $240.0 | 0.72 |
| 11 | def_052 | Personal Wealth Management & Note-Taking Systems | Finance / Investing | $4.00 / $8.00 / $12.00 | $30 / $155 / $375 | $44.0 / $176.0 / $396.0 | $-331.0 / $21.0 / $366.0 | 0.72 |
| 12 | def_020 | Social Media Marketing Agency (SMMA) Scaling | Digital Marketing / Business | $4.00 / $6.50 / $9.00 | $30 / $155 / $375 | $48.0 / $156.0 / $324.0 | $-327.0 / $1.0 / $294.0 | 0.77 |
| 13 | def_053 | Personal Financial Habits & Expense Tracking | Finance / Investing | $4.00 / $8.00 / $12.00 | $30 / $155 / $375 | $52.0 / $208.0 / $468.0 | $-323.0 / $53.0 / $438.0 | 0.77 |
| 14 | def_016 | Cybersecurity Education & Ethical Hacking Roadmaps | Technology / Software | $4.00 / $7.00 / $10.00 | $30 / $155 / $375 | $56.0 / $196.0 / $420.0 | $-319.0 / $41.0 / $390.0 | 0.77 |
| 15 | def_054 | Notion Workspace & Freelance Operating Systems | Education / How-To | $2.00 / $4.00 / $6.00 | $30 / $155 / $375 | $30.0 / $120.0 / $270.0 | $-345.0 / $-35.0 / $240.0 | 0.68 |
| 16 | def_025 | Backend Engineering & Full-Stack Development | Technology / Software | $4.00 / $7.00 / $10.00 | $30 / $155 / $375 | $64.0 / $224.0 / $480.0 | $-311.0 / $69.0 / $450.0 | 0.77 |
| 17 | def_002 | Budgeting Strategies & Financial Blueprints | Finance / Investing | $4.00 / $8.00 / $12.00 | $30 / $155 / $375 | $68.0 / $272.0 / $612.0 | $-307.0 / $117.0 / $582.0 | 0.77 |
| 18 | def_009 | Developer Frameworks & Tech Stack Comparisons | Technology / Software | $4.00 / $7.00 / $10.00 | $30 / $155 / $375 | $72.0 / $252.0 / $540.0 | $-303.0 / $97.0 / $510.0 | 0.77 |
| 19 | def_026 | Notion Academic & Personal Organization Systems | Education / How-To | $2.00 / $4.00 / $6.00 | $30 / $155 / $375 | $38.0 / $152.0 / $342.0 | $-337.0 / $-3.0 / $312.0 | 0.68 |
| 20 | def_023 | Digital Marketing Agency Scaling & White Labeling | Digital Marketing / Business | $4.00 / $6.50 / $9.00 | $30 / $155 / $375 | $80.0 / $260.0 / $540.0 | $-295.0 / $105.0 / $510.0 | 0.77 |

## Sanity Checks & Invariant Verification

- **Views Bounds Ordering**: `low <= base <= high` verified for all 20 candidates.
- **RPM Bounds Ordering**: `low <= base <= high` verified for all 20 candidates.
- **Cost Bounds Ordering**: `low <= base <= high` verified for all 20 candidates.
- **Revenue Scenarios**: Calculated deterministically via `Views * RPM / 1000`.
- **Profit Scenarios**: Calculated deterministically via `Revenue - Cost` without artificial loss clamping.
- **Zero Hard-Coding**: All values derived from PostgreSQL benchmarks and ProductionRiskEngine labor hours.
